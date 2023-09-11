from pydantic import BaseModel, Field
from enum import IntEnum


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    LiveStarted = 3
    Dismissed = 4
    OtherError = 5


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dismissed = 3
    ResultSent = 4


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


# FastAPI 0.100 は model_validate_json() を使わないので、 strict モードにすると
# EnumがValidationエラーになってしまいます。
class UserCreateRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


# Responseの方は strict モードを利用できます
class UserCreateResponse(BaseModel, strict=True):
    user_token: str


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


# 仕様に載ってないので、もしかすると単一の変数のときは構造体の定義が要らない
# いい感じの書き方がある？ (直に room_id を渡すと JSON にならないので一旦このまま)
class RoomLeaveRequest(BaseModel):
    room_id: int


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    room_id: int


class RoomEndRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: list[int]


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]
