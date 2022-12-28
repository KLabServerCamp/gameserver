from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model, room_model
from .model import SafeUser
from .room_model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    WaitRoomStatus,
)

app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
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


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """ルーム作成"""
    # print(req)
    room_id = room_model.create_room(req.live_id, req.select_difficulty, token)

    # if room_id == -1:
    #     raise HTTPException(status_code=)
    return room_id


class RoomListRequest(BaseModel):
    live_id: int


@app.post("/room/list", response_model=list[RoomInfo])
def room_list(req: RoomListRequest):
    """ルームリストの取得"""
    # print(req)
    room_info_list = room_model.get_room_list(req.live_id)

    if room_info_list is None:
        raise HTTPException(status_code=404)

    return room_info_list


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


@app.post("/room/join", response_model=JoinRoomResult)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    """ルームへの参加"""
    # print(req)
    room_info_list = room_model.room_join(req.room_id, req.select_difficulty, token)
    return room_info_list


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    """ルーム内待機"""
    # print(req)
    (status, room_user_list) = room_model.room_wait(req.room_id, token)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int


@app.post("/room/start", response_model=Empty)
def room_start(req: RoomStartRequest):
    """ライブモードへの遷移OK"""
    # print(req)
    room_model.room_start(req.room_id)
    return {}


class RoomEndRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: list[int]


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    """ライブが終了し、データベースに結果を登録する"""
    # print(req)
    room_model.room_end(req.judge_count_list, req.score, token)
    return {}
