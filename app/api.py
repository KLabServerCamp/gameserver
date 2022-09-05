from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    SafeUser,
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


# UserCreateRequestは型ヒント
# JSONの型をクラスで表現してヒントとして渡している
# というより，プログラム内でそのクラスで扱っている
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


# Rooms APIs

# /room/create
class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


# /room/list
class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


# /room/join
class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


# /room/wait
class RoomWaitRequest(BaseModel):
    room_id: int
    room_user_list: list[RoomUser]


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus


# /room/start
class RoomStartRequest(BaseModel):
    room_id: int


# /room/end
class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


# /room/result
class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


# /room/leave
class RoomLeaveRequest(BaseModel):
    room_id: int


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """新規ルーム作成"""
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    room_info_list = model.get_room_list(req.live_id)
    if room_info_list is None:
        raise HTTPException(status_code=404)
    return RoomListResponse(room_info_list=room_info_list)
