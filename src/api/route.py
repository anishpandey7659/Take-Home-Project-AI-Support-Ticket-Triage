import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from src.triage_queue import TriageQueue, get_triage_queue
from src.schema import TriageResult,TriageRequest

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1", tags=["triage"])


@router.post(
    "/triage",
    response_model=TriageResult,
    status_code=status.HTTP_200_OK,
    summary="Classify a support message",
)
async def triage(
    payload: TriageRequest,
    llm: Annotated[TriageQueue, Depends(get_triage_queue)],
) -> TriageResult:
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not be blank.",
        )
 
    try:
        return await llm.classify(message)  # goes through the shared queue
    except Exception:
        # Primary and fallback both failed (rate limit, bad output, etc.)
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
    llm: Annotated[TriageQueue, Depends(get_triage_queue)],
) -> list[TriageResult]:
    # Validate everything up front, before spending any LLM calls
    messages = [p.message.strip() for p in payloads]
    if any(not m for m in messages):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must not be blank.",
        )
 
    # All messages go through the same shared queue; results keep input order
    results = await llm.classify(messages)
 
    classified: list[TriageResult] = []
    for message, result in zip(messages, results):
        if isinstance(result, BaseException):
            logger.error(
                "Triage LLM call failed for message: %s", message, exc_info=result
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to classify the message: {message}. Please try again.",
            )
        classified.append(result)
    logger.info("triage stats: %s", llm.stats.summary())
    return classified