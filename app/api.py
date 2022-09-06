
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import SafeUser
from .model import (
    RoomInfo, RoomUser, JoinRoomResult, 
    LiveDifficulty, ResultUser, RoomInfo, WaitRoomStatus
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


def get_auth_token(
    cred: HTTPAuthorizationCredentials = Depends(bearer)
    ) -> str:
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
    live_id: int
    select_difficulty: LiveDifficulty

class RoomCreateResponse(BaseModel):
    room_id: int

@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    room_id = model.create_room(req.live_id, user)
    model.join_room(room_id, req.select_difficulty, user)
    return RoomCreateResponse(room_id=room_id)

class RoomListRequest(BaseModel):
    live_id: int

class RoomListResponse(BaseModel):
    room_list: list[RoomInfo]

@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    room_list = model.get_room_list(req.live_id)
    return RoomListResponse(room_list=room_list)

class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty

@app.post("/room/join", response_model=JoinRoomResult)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    join_room_result = \
        model.join_room(req.room_id, req.select_difficulty, user)
    return join_room_result
    
class RoomWaitRequest(BaseModel):
    room_id: int

class RoomWaitResponse(BaseModel):
    wait_room_status: WaitRoomStatus
    room_member_list: list[RoomUser]

@app.post("/room/wait", response_model=RoomWaitResponse)
def wait_room(req: RoomWaitRequest):
    res = model.get_room_wait(req.room_id)
    return RoomWaitResponse(
        wait_room_status=res[0],
        room_member_list=res[1]
    )

class RoomStartRequest(BaseModel):
    room_id: int

@app.post("/room/start")
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.start_room(req.room_id, user)

class RoomEndRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: list[int]

@app.post("/room/end")
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.end_room(user.id, req.room_id, req.judge_count_list, req.score)

class RoomResultRequest(BaseModel):
    room_id: int

@app.post("/room/result", response_model=list[ResultUser])
def room_result(req: RoomResultRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    res = model.get_result_user_list(req.room_id, user)
    return res

class RoomLeaveRequest(BaseModel):
    room_id: int

@app.post("/room/leave")
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.leave_room(req.room_id, user)