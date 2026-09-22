from fastapi import APIRouter

router = APIRouter()


@router.get("", summary="获取用户列表")
async def list_users():
    return {"users": [{"id": 1, "name": "demo"}]}


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(user_id: int):
    return {"id": user_id, "name": "demo"}


@router.post("", summary="创建用户")
async def create_user(payload: dict):
    return {"message": "user created", "data": payload}
