from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import SafeUser
from . import room_controler as room
from .room_controler import LiveDifficulty, JoinRoomResult, WaitRoomStatus, RoomUser, ResultUser

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
    print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# NOTE:ROOM category

class RoomID(BaseModel):
    room_id: int


class RoomInfo():
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class CreateRoomResponse(BaseModel):
    room_id: int


class RoomListRequest(BaseModel):
    live_id: int


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    result: JoinRoomResult


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    room_id: int


@app.post("/room/create", response_model=CreateRoomResponse)
def room_create(req: CreateRoomRequest, token: str = Depends(get_auth_token)):
    room_id = room.create_room(req.live_id, req.select_difficulty, token)
    return CreateRoomResponse(room_id=room_id)


@app.post("/room/list")
def list_room(req: RoomListRequest):
    rooms = room.room_list(req.live_id)
    return rooms


@app.post("/room/join")
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)) -> RoomJoinResponse:
    return RoomJoinResponse(result=JoinRoomResult(room.room_join(req.room_id, req.select_difficulty, token)))


@app.post("/room/wait")
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)) -> RoomWaitResponse:
    status, member = room.room_wait(room_id=req.room_id, token=token)
    return RoomWaitResponse(status=status, room_user_list=member)


@app.post("/room/start")
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    room.room_start(req.room_id, token)
    pass


@app.post("/room/end")
def room_end():
    pass


@app.post("/room/result")
def room_result():
    pass

@app.post("/room/leave")
def room_leave():
    pass