from enum import IntEnum

from pydantic import BaseModel

from .live import LiveDifficulty


class RoomInfo(BaseModel, strict=True):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = 4


class RoomID(BaseModel):
    room_id: int


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class RoomUser(BaseModel, strict=True):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class ResultUser(BaseModel):
    user_id: int
    score: int
    judge_count_list: list[int]


class SafeRoom(BaseModel, strict=True):
    room_id: int
    owner_id: int
    live_id: int
    max_user_count: int
    status: int


class SafeRoomMember(BaseModel, strict=True):
    room_id: int
    user_id: int
    difficulty: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class ListRoomRequest(BaseModel):
    live_id: int


class ListRoomResponse(BaseModel):
    room_info_list: list


class JoinRoomRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class JoinRoomResponse(BaseModel):
    join_room_result: JoinRoomResult


class WaitRoomRequest(BaseModel):
    room_id: int


class WaitRoomResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class StartRoomRequest(BaseModel):
    room_id: int


class EndRoomRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: list[int]


class ResultRoomRequest(BaseModel):
    room_id: int


class ResultRoomResponse(BaseModel):
    result_user_list: list[ResultUser]


class LeaveRoomRequest(BaseModel):
    room_id: int
