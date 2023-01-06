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
    SafeUser,
    WaitRoomResult,
)

app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
    return {"message": "Hello World"}


# User APIs
#    user/create
class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(name=req.user_name, leader_card_id=req.leader_card_id)
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
    model.update_user(
        token=token, name=req.user_name, leader_card_id=req.leader_card_id
    )
    return {}


#    room/create
class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    room_id = model.create_room(
        token=token, live_id=req.live_id, select_difficulty=req.select_difficulty
    )
    return RoomCreateResponse(room_id=room_id)


#   room/list
class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest, token: str = Depends(get_auth_token)):
    room_info_list = model.list_room(live_id=req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


#   room/join
class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    join_room_result = model.join_room(
        token=token, room_id=req.room_id, select_difficulty=req.select_difficulty
    )
    return RoomJoinResponse(join_room_result=join_room_result)


#   room/wait
class RoomWaitRequest(BaseModel):
    room_id: int


@app.post("/room/wait", response_model=WaitRoomResult)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    return model.wait_room(token=token, room_id=req.room_id)


#    room/start
class RoomStartRequest(BaseModel):
    room_id: int


@app.post("/room/start", response_model=Empty)
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    model.start_room(token=token, room_id=req.room_id)
    return {}


#    room/end
class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    model.end_room(
        token=token,
        room_id=req.room_id,
        judge_count_list=req.judge_count_list,
        score=req.score,
    )
    return {}


#   room/result
class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest, token: str = Depends(get_auth_token)):
    result_user_list = model.result_room(
        token=token,
        room_id=req.room_id,
    )
    return RoomResultResponse(result_user_list=result_user_list)


#   room/leave
class RoomLeaveRequest(BaseModel):
    room_id: int


@app.post("/room/leave", response_model=Empty)
def room_result(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    model.leave_room(
        token=token,
        room_id=req.room_id,
    )
    return {}
