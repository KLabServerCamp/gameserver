from fastapi import APIRouter, HTTPException, status

from ..auth import UserToken
from ..db import SqlConnection
from ..schemas.structures import Empty, SafeUser, UserCreateRequest, UserCreateResponse
from ..services import user_service as service

router = APIRouter()


@router.post("/create")
def user_create(conn: SqlConnection, req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = service.create_user(conn, req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証動作確認用のサンプルAPI
# ゲームアプリは使わない
@router.get("/me")
def user_me(conn: SqlConnection, token: UserToken) -> SafeUser:
    user = service.get_user_by_token(conn, token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


@router.post("/update")
def update(conn: SqlConnection, token: UserToken, req: UserCreateRequest) -> Empty:
    """Update user attributes"""
    service.update_user(conn, token, req.user_name, req.leader_card_id)
    return Empty()
