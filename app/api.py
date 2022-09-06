from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import SafeUser

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


# Room APIs


class LiveDifficulty(Enum):
    normal = 1
    hard = 2

class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Wating = 1
    LiveStart = 2
    Dissolution = 3

class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    owner: int
    joined_user_count: int
    max_user_count: int
    
class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool
    
class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int
    


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


@app.get("/room/list", response_model=list[RoomInfo])
def room_list(live_id: int):
    room_list = model.get_room_list(live_id)
    return room_list


@app.post("/room/join", response_model=JoinRoomResult)
def room_join(room_id: int, select_difficutly: LiveDifficulty, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    join_room_result = model.join_room(room_id, select_difficutly, user)
    return join_room_result
    

class RoomWaitResponse(BaseModel):
    wait_room_status: WaitRoomStatus
    room_member_list: list[RoomUser]

@app.get("/room/wait", response_model=RoomWaitResponse)
def wait_room(room_id: int):
    res = model.get_room_wait(room_id)
    return res


@app.post("/room/start")
def room_start(room_id: int, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.start_room(room_id, user)
    # model.update_wait_room_status(room_id, WaitRoomStatus.LiveStart)


class RoomEndRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: list[int]

@app.post("/room/end")
def room_end(req: RoomEndRequest):
    model.end_room()


@app.get("/room/result", response_model=list[ResultUser])
def room_result(room_id: int, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    res = model.get_result_user_list(room_id, user)
    return res


@app.post("/room/leave")
def room_leave(room_id: int, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.leave_room(room_id, user)