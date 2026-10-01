import logging
import asyncio
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from src.config import get_settings
from src.llm import LLM, get_llm_instance
from src.schema import TriageResult,TriageRequest

logger = logging.getLogger(__name__)

settings = get_settings()
MAX_CONCURRENCY = settings.max_concurrency

router = APIRouter(prefix="/api/v1", tags=["triage"])

@router.post(
    "/triage",
    response_model=TriageResult,
    status_code=status.HTTP_200_OK,
    summary="Classify a support message",
)
async def triage(
    payload: TriageRequest,
    llm: Annotated[LLM, Depends(get_llm_instance)],
) -> TriageResult:
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not be blank.",
        )

    try:
        return await llm.ainvoke(message)
    except Exception:
        # Both primary and fallback models failed (rate limit, bad output, etc.)
        logger.exception("Triage LLM call failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to classify the message. Please try again.",
        )
    
@router.post(
    "/triage_all",
    response_model=list[TriageResult],
    status_code=status.HTTP_200_OK,
    summary="Classify a list of support messages",
)
async def triage_all(
    payloads: list[TriageRequest],
    llm: Annotated[LLM, Depends(get_llm_instance)],
) -> list[TriageResult]:
    # 1. Validate everything up front, before spending any LLM calls
    messages = [p.message.strip() for p in payloads]
    if any(not m for m in messages):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not be blank.",
        )

    # 2. Limit how many calls are in flight at once
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def classify(message: str) -> TriageResult:
        async with semaphore:
            try:
                return await llm.ainvoke(message)
            except Exception:
                logger.exception("Triage LLM call failed for message: %s", message)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to classify the message: {message}. Please try again.",
                )

    # 3. Run them concurrently; results keep the same order as the input
    return await asyncio.gather(*(classify(m) for m in messages))