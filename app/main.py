from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="MiniShop")
app.include_router(
    api_router,
    prefix="/api/v1",
)


@app.get("/")
async def root():
    return {"message": "MiniShop API is running"}
