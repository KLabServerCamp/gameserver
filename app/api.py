from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import LiveDifficulty

app = FastAPI(debug=True)


# Sample API
@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create")
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証のサンプルAPI
# ゲームでは使わない
@app.get("/user/me")
def user_me(token: UserToken) -> model.SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update")
def update(req: UserCreateRequest, token: UserToken) -> Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class RoomID(BaseModel):
    room_id: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def list(live_id: int) -> list[RoomInfo]:
    rows = model.get_room_list(live_id)
    room_list = []
    for row in rows:
        room_list.append(
            RoomInfo(
                room_id=row.room_id,
                live_id=row.live_id,
                joined_user_count=row.joined_user_count,
                max_user_count=row.max_user_count,
            )
        )

    return room_list


@app.post("/room/join")
def join(token: UserToken, room_id: int, difficulty: int) -> int:
    result = model.join_room(token, room_id, difficulty)
    return result
