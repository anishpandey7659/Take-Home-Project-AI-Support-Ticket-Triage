from src.api.route import router
from fastapi import FastAPI



@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


app = FastAPI(title="Support Triage API", version="1.0.0")
app.include_router(router)

# Run with: uvicorn src.main:app --reload