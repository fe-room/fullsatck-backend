from fastapi import FastAPI

from api.router import api_router

app = FastAPI(title="MiniShop")
app.include_router(api_router)


@app.get("/")
async def root():
    return {"message": "MiniShop API is running"}



