from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import LiveDifficulty, SafeUser

app = FastAPI()

# Sample APIs


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# Room APIs


class RoomCreateRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty  # 難易度


class RoomCreateResponse(BaseModel):
    room_id: int  # 発行されたルームのID（以後の通信はこのiDを添える）


@app.post("/room/create", response_model=RoomCreateResponse)
def create_room(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    """ルームを作成する"""
    # print(req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID


class RoomListResponse(BaseModel):
    room_info_list: list[model.RoomInfo]  # 入場可能なルームのリスト


@app.post("/room/list", response_model=RoomListResponse)
def list_room(req: RoomListRequest) -> RoomListResponse:
    """ルーム一覧を表示する"""
    # print(req)
    room_info_list = model.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)
