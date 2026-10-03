import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import cast, overload

from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain_groq import ChatGroq
from pydantic import SecretStr

from .config import get_settings
from .prompt import PROMPT
from .schema import TriageResult

logger = logging.getLogger(__name__)


# failure tracking 
@dataclass
class FailureRecord:
    request_id: int
    message: str
    worker: str
    model: str
    stage: str          # "primary" | "fallback" | "final"
    error_type: str
    error: str
    ts: float = field(default_factory=time.time)


class Stats:
    def __init__(self):
        self.total = 0
        self.succeeded = 0
        self.failed = 0              # requests that failed after ALL attempts
        self.fallback_used = 0       # primary failed, fallback saved it
        self.records: list[FailureRecord] = []

    def record(self, rec: FailureRecord):
        self.records.append(rec)

    @property
    def failed_requests(self) -> list[FailureRecord]:
        """Requests that ended in a final failure (which ones failed)."""
        return [r for r in self.records if r.stage == "final"]

    def summary(self) -> dict:
        return {
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "fallback_used": self.fallback_used,
            "errors_by_type": dict(Counter(r.error_type for r in self.records)),
            "errors_by_worker": dict(Counter(r.worker for r in self.records)),
            "failed_ids": [r.request_id for r in self.failed_requests],
        }


def _tracked(chain: Runnable, *, worker: str, model: str, stage: str, stats: Stats) -> Runnable:
    """Wrap a chain so every failure is recorded before with_fallbacks swallows it."""

    async def run(inp: dict, config: RunnableConfig):
        meta = (config or {}).get("metadata", {})
        try:
            result = await chain.ainvoke(inp, config)
        except Exception as e:
            stats.record(FailureRecord(
                request_id=meta.get("request_id", -1),
                message=inp["message"],
                worker=worker,
                model=model,
                stage=stage,
                error_type=type(e).__name__,
                error=str(e)[:300],
            ))
            logger.warning("[%s/%s] req=%s failed: %s", worker, stage, meta.get("request_id"), e)
            raise
        if stage == "fallback":
            stats.fallback_used += 1
        return result

    return RunnableLambda(run)


# one worker slot = one API key + primary model + fallback model 

class Slot:
    def __init__(self, name: str, api_key: SecretStr, primary_model: str,
                 fallback_model: str, stats: Stats):
        s = get_settings()
        self.name = name

        def build(model: str, stage: str) -> Runnable:
            llm = ChatGroq(
                model=model,
                api_key=api_key,
                temperature=s.default_temperature,
                max_retries=0,
            )
            chain = PROMPT | llm.with_structured_output(TriageResult)
            return _tracked(chain, worker=name, model=model, stage=stage, stats=stats)

        primary = build(primary_model, "primary")
        fallback = build(fallback_model, "fallback")
        self.chain: Runnable = primary.with_fallbacks([fallback])  # LangChain fallback

        self.sem = asyncio.Semaphore(s.max_concurrency)


# queue 
class TriageQueue:
    def __init__(self):
        s = get_settings()
        self.cooldown = s.cooldown
        self.max_attempts = s.max_attempts
        self.concurrency = s.max_concurrency
        self.stats = Stats()

        # Different API key per worker; both fall back to Qwen on their own key.
        self.slots = [
            Slot("worker-1", s.groq_api_key,  s.groq_model, s.fallback_model1, self.stats),
            Slot("worker-2", s.groq_api_key2, s.groq_model2, s.fallback_model2, self.stats),
        ]
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1000)  # backpressure
        self.tasks: list[asyncio.Task] = []
        self._next_id = 0

    @overload
    async def classify(self, messages: str) -> TriageResult: ...
    @overload
    async def classify(self, messages: list[str]) -> list[TriageResult | BaseException]: ...

    async def classify(self, messages: str | list[str]):
        single = isinstance(messages, str)
        items = [messages] if single else messages

        if not self.tasks:
            self.tasks = [
                asyncio.create_task(self._worker(slot))
                for slot in self.slots
                for _ in range(self.concurrency)
            ]

        loop = asyncio.get_running_loop()
        futures = []
        for m in items:
            rid, self._next_id = self._next_id, self._next_id + 1
            self.stats.total += 1
            fut = loop.create_future()
            await self.queue.put((rid, m, fut, 0))
            futures.append(fut)

        results = await asyncio.gather(*futures, return_exceptions=not single)
        return results[0] if single else results

    async def _worker(self, slot: Slot):
        loop = asyncio.get_running_loop()
        while True:
            rid, message, fut, attempt = await self.queue.get()
            try:
                if fut.cancelled():
                    continue

                await slot.sem.acquire()
                try:
                    result = await slot.chain.ainvoke(
                        {"message": message},
                        config={"metadata": {"request_id": rid, "worker": slot.name}},
                    )
                except Exception as e:
                    # primary AND fallback both failed on this worker
                    if attempt + 1 < self.max_attempts:
                        await asyncio.sleep(attempt)  # backoff
                        self.queue.put_nowait((rid, message, fut, attempt + 1))  # other worker may take it
                    else:
                        self.stats.failed += 1
                        self.stats.record(FailureRecord(
                            rid, message, slot.name, "primary+fallback", "final",
                            type(e).__name__, str(e)[:300],
                        ))
                        if not fut.done():
                            fut.set_exception(e)
                else:
                    self.stats.succeeded += 1
                    if not fut.done():
                        fut.set_result(cast(TriageResult, result))
                finally:
                    loop.call_later(self.cooldown, slot.sem.release)
            finally:
                self.queue.task_done()

    async def close(self):
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()


@lru_cache(maxsize=1)
def get_triage_queue() -> TriageQueue:
    """Get a singleton TriageQueue instance, cached for the lifetime of the process."""
    return TriageQueue()



async def main():
    messages = [
        "I can't log in to my account. It says my password is incorrect.",
        "The app crashes every time I try to upload a photo.",
        "I was charged twice for my subscription this month.",
        "The website is very slow and sometimes doesn't load at all.",
    ]
    q = get_triage_queue()
    results = await q.classify(messages[0])
    print("Output:",results)
    print("\n\n")

    print(q.stats.summary())

    for r in q.stats.failed_requests:       # which requests failed, and why
        print(r.request_id, r.worker, r.error_type, r.message[:60])

    # in the batch result, failures are exceptions at the same index:
    bad = [(i, m) for i, (m, r) in enumerate(zip(messages, results)) if isinstance(r, BaseException)]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

# python -m src.triage_queue