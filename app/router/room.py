from enum import Enum
from typing import List

from fastapi import APIRouter, Depends
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .. import model
from ..model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomUser,
    SafeUser,
    WaitRoomStatus,
)
from .user import Empty, get_auth_token

router = APIRouter()

# room APIs
class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


@router.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """create room"""
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int = -1


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@router.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    print(req.live_id)
    if req.live_id == 0:
        rooms = model.get_rooms()
    else:
        rooms = model.get_rooms(req.live_id)
    tmp = []
    for room in rooms.all():
        tmp.append(
            RoomInfo(
                room_id=room.room_id,
                live_id=room.live_id,
                joined_user_count=room.joined_user_count,
                max_user_count=room.max_user_count,
            )
        )
    return RoomListResponse(room_info_list=tmp)


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@router.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    status, room_users = model.get_room_users(token, req.room_id)
    return RoomWaitResponse(status=status, room_user_list=room_users)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@router.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    res = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=res)


class RoomStartRequest(BaseModel):
    room_id: int


@router.post("/room/start", response_model=Empty)
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    model.start_room(token, req.room_id)
    return {}


class RoomEndRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: List[int]


@router.post("/room/end", response_model=Empty)
def room_start(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    print(req)
    model.end_room(token, req.room_id, req.score, req.judge_count_list)
    return {}


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: List[ResultUser]


@router.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    res = model.get_results(req.room_id)
    return RoomResultResponse(result_user_list=res)


class RoomLeaveRequest(BaseModel):
    room_id: int


@router.post("/room/leave", response_model=Empty)
def room_result(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    model.leave_room(token, req.room_id)
    return {}
