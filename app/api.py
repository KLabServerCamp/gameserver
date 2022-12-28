# from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import MAX_USER_COUNT

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


# response_model で Type Hintをつけるのは、空のDictを返すときに便利
@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# room APIs
class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: int


class RoomCreateResponse(BaseModel):
    room_id: int


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """Create a new room"""
    id = model.create_room(token, req.live_id, req.select_difficulty)

    if id is None:
        raise HTTPException(status_code=404)

    return RoomCreateResponse(room_id=id)


class RoomListRequest(BaseModel):
    live_id: int


@app.post("/room/list", response_model=list[RoomInfo])
def room_list(req: RoomListRequest):
    """List all rooms"""
    rooms = model.get_room_list(req.live_id)
    res = []
    for r in rooms:
        users = model.get_room_members(r.id)
        res.append(
            RoomInfo(room_id=r.id, live_id=r.live_id, joined_user_count=len(users), max_user_count=MAX_USER_COUNT)
        )
    return res


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: model.LiveDifficulty


@app.post("/room/join", response_model=model.JoinRoomResult)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    """Join a room"""
    res = model.join_room(token, req.room_id, req.select_difficulty)
    return res
