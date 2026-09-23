from api.router import api_router
from fastapi import FastAPI

app = FastAPI(title="MiniShop")
app.include_router(api_router)


@app.get("/")
async def root():
    return {"message": "MiniShop API is running"}
