# from enum import Enum

import json
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


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: model.LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: model.LiveDifficulty


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


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    """List all rooms"""
    rooms = model.get_room_list(req.live_id)
    res = []
    for r in rooms:
        if r.live_status != model.WaitRoomStatus.Waiting:
            continue

        users = model.get_room_members(r.id)
        if users is None:
            return HTTPException(status_code=404)

        if len(users) >= MAX_USER_COUNT:
            continue

        res.append(
            RoomInfo(room_id=r.id, live_id=r.live_id, joined_user_count=len(users), max_user_count=MAX_USER_COUNT)
        )
    return RoomListResponse(room_info_list=res)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: model.LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: model.JoinRoomResult


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    """Join a room"""
    res = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=res)


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: model.WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    """Wait for a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=404)

    status = model.get_room_status(req.room_id)
    if status is None:
        raise HTTPException(status_code=404)

    members = model.get_room_members(req.room_id)
    if members is None:
        raise HTTPException(status_code=404)

    room_user_list = []

    for m in members:
        user = model.get_user_by_id(m.user_id)
        room_user_list.append(
            RoomUser(
                user_id=user.id,
                name=user.name,
                leader_card_id=user.leader_card_id,
                select_difficulty=m.select_difficulty,
                is_me=(me.id == user.id),
                is_host=m.is_host,
            )
        )

    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int


@app.post("/room/start", response_model=Empty)
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    """Start a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=404)

    res = model.start_room(req.room_id, me.id)
    if not res:
        raise HTTPException(status_code=404)

    return {}


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    """End a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=404)

    res = model.store_result(req.room_id, me.id, req.score, req.judge_count_list)
    if not res:
        raise HTTPException(status_code=404)

    return {}


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    """Get result of a room"""

    res = model.get_result(req.room_id)
    if res is None:
        raise HTTPException(status_code=404)

    # FIXME : json.loads で壊れる
    res = [ResultUser(user_id=r.user_id, judge_count_list=json.loads(r.judge_count_list), score=r.score) for r in res]

    return RoomResultResponse(result_user_list=res)
