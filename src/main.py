from src.api.route import router
from fastapi import FastAPI


app = FastAPI(title="Support Triage API", version="1.0.0")

@app.get("/api/hello")
async def hello():
    return {"message": "Hello from FastAPI!"}


app.include_router(router)

# Run with: uvicorn src.main:app --reload

