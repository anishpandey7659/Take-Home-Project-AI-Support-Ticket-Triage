from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq

from .config import Settings, get_settings
from .prompt import PROMPT
from .schema import TriageResult


class LLM:

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()

        # Primary Openai/oss Groq model for structured output.
        self._primary: BaseChatModel = ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=settings.default_temperature,
        )
        # Secondary Groq model Qwen for fallback, if specified in settings.
        self._primary2: BaseChatModel = ChatGroq(
            model=settings.groq_model2,
            api_key=settings.groq_api_key2,
            temperature=settings.default_temperature,
        )

        # Same structured-output schema on both models; Groq falls back to Gemini.
        self._structured_llm: Runnable = self._primary.with_structured_output(
            TriageResult
        ).with_fallbacks(
            [
                self._primary2.with_structured_output(TriageResult),
            ]
        )

        self._chain: Runnable = PROMPT | self._structured_llm

    @property
    def llm(self) -> BaseChatModel:
        """The primary Groq LLM."""
        return self._primary

    @property
    def structured_llm(self) -> Runnable:
        """Structured-output LLM with fallback."""
        return self._structured_llm

    @property
    def chain(self) -> Runnable:
        """Prompt + structured LLM chain."""
        return self._chain

    async def ainvoke(self, message: str) -> TriageResult:
        """Asynchronously classify a single support message."""
        return await self._chain.ainvoke(
            {"message": message}
        )

@lru_cache(maxsize=1)
def get_llm_instance() -> LLM:
    """Return a cached, shared LLM instance."""
    return LLM()