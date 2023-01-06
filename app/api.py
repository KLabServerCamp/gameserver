from enum import Enum
from functools import wraps
from typing import Callable, ParamSpec, TypeAlias, TypeVar

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import (
    InvalidToken,
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


P = ParamSpec("P")
R = TypeVar("R")


def handle_invalid_token(func: Callable[P, R]) -> Callable[P, R]:
    @wraps(func)
    def _wrapper(*args: P.args, **kwargs: P.kwargs):
        try:
            return func(*args, **kwargs)
        except InvalidToken:
            raise HTTPException(status_code=404)

    return _wrapper


@app.get("/user/me", response_model=SafeUser)
@handle_invalid_token
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
@handle_invalid_token
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
@handle_invalid_token
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    room_info_list = model.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@app.post("/room/join", response_model=RoomJoinResponse)
@handle_invalid_token
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    join_room_result = model.join_room(token, req.room_id, req.select_difficulty)
    if join_room_result is None:
        raise HTTPException(status_code=404)
    return RoomJoinResponse(join_room_result=join_room_result)


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait", response_model=RoomWaitResponse)
@handle_invalid_token
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    status_and_list = model.wait_room(token, req.room_id)
    if status_and_list is None:
        raise HTTPException(status_code=404)

    status, room_user_list = status_and_list
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomLeaveRequest(BaseModel):
    room_id: int


@app.post("/room/leave", response_model=Empty)
@handle_invalid_token
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    model.leave_room(token, req.room_id)
    return {}


RoomStartRequest: TypeAlias = RoomLeaveRequest


@app.post("/room/start", response_model=Empty)
@handle_invalid_token
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    model.start_room(token, req.room_id)
    return {}


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/end", response_model=Empty)
@handle_invalid_token
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    model.end_room(token, req.room_id, req.judge_count_list, req.score)
    return {}


RoomResultRequest: TypeAlias = RoomLeaveRequest


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result", response_model=RoomResultResponse)
@handle_invalid_token
def room_result(req: RoomResultRequest, token: str = Depends(get_auth_token)):
    result_user_list = model.get_result(token, req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)
