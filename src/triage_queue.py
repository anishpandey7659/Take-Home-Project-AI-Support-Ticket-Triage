import asyncio
from typing import cast, overload
from functools import lru_cache
from langchain_groq import ChatGroq
from pydantic import SecretStr
from .config import get_settings
from .prompt import PROMPT
from .schema import TriageResult



def make_slot(api_key: SecretStr, model: str):
    """One API key + model = (structured-output chain, semaphore)."""
    s = get_settings()
    llm = ChatGroq(
        model=model,
        api_key=api_key,
        temperature=s.default_temperature,
        max_retries=0,  # retries are handled below
    )
    chain = PROMPT | llm.with_structured_output(TriageResult)
    return chain, asyncio.Semaphore(s.max_concurrency)



class TriageQueue:
    def __init__(self):
        s = get_settings()
        self.max_concurrency = s.max_concurrency
        self.cooldown = s.cooldown
        self.max_attempts = s.max_attempts

        self.slots = [
            make_slot(s.groq_api_key, s.groq_model),   
            make_slot(s.groq_api_key2, s.groq_model2), 
        ]
        self.queue: asyncio.Queue = asyncio.Queue()
        self.workers: list[asyncio.Task] = []


    @overload
    async def classify(self, messages: str) -> TriageResult: ...
    @overload
    async def classify(
        self, messages: list[str]
    ) -> list[TriageResult | BaseException]: ...
    
    async def classify(self, messages: str | list[str]):
        """Accepts one message or a list. Everything goes through the queue."""
        single = isinstance(messages, str)
        items = [messages] if single else messages

        if not self.workers:  # start workers on first use
            self.workers = [
                asyncio.create_task(self._worker()) for _ in range(self.max_concurrency)
            ]

        futures = []
        for m in items:
            fut = asyncio.get_running_loop().create_future()
            self.queue.put_nowait((m, fut))
            futures.append(fut)

        results = await asyncio.gather(*futures, return_exceptions=not single)
        return results[0] if single else results

    async def _worker(self):
        while True:
            message, fut = await self.queue.get()
            try:
                fut.set_result(await self._process(message))
            except Exception as e:
                fut.set_exception(e)

    async def _process(self, message: str) -> TriageResult:
        for attempt in range(self.max_attempts):
            chain, sem = self.slots[attempt % 2]  # even: primary, odd: fallback
            await sem.acquire()
            try:
                result = await chain.ainvoke({"message": message})
                return cast(TriageResult, result)
            except Exception:
                await asyncio.sleep(attempt)  # backoff, then try the other model
            finally:
                # Rate limit: free the slot only after the cooldown.
                asyncio.get_running_loop().call_later(self.cooldown, sem.release)
        raise RuntimeError("Primary and fallback both failed")


@lru_cache(maxsize=1)
def get_triage_queue() -> TriageQueue:
    """Singleton TriageQueue for the app."""
    return TriageQueue()  # singleton for the app


async def main():
    llm = get_triage_queue()

    print(await llm.classify("The pill scanner stopped recognising my father's medications after the latest update. It worked fine last week."))  # single message

    # messages = [f"Test message {i}" for i in range(1, 21)]  # list of messages
    # results = await llm.classify(messages)
    # for msg, res in zip(messages, results):
    #     if isinstance(res, BaseException):
    #         print(msg, "FAILED:", res)
    #     else:
    #         print(msg, "->", res)


if __name__ == "__main__":
    asyncio.run(main())

# python -m src.triage_queue