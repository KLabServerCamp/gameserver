from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app import schemas
from app.auth import UserToken
from app.models import User

router = APIRouter()

# User APIs


@router.post("/user/create")
def user_create(req: schemas.UserCreateRequest) -> schemas.UserCreateResponse:
    """新規ユーザー作成"""
    token = User.create(req.user_name, req.leader_card_id)
    return schemas.UserCreateResponse(user_token=token)


# 認証動作確認用のサンプルAPI
# ゲームアプリは使わない
@router.get("/user/me")
def user_me(token: UserToken) -> schemas.SafeUser:
    user = User.get_user_by_token(token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


class Empty(BaseModel):
    pass


@router.post("/user/update")
def update(req: schemas.UserCreateRequest, token: UserToken) -> Empty:
    """Update user attributes"""
    # print(req)
    User.update(token, req.user_name, req.leader_card_id)
    return Empty()
