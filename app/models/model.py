from enum import Enum, IntEnum

# from fastapi import HTTPException
from pydantic import BaseModel

from ..config import MAX_USER_COUNT

# from sqlalchemy.exc import NoResultFound


"""
Enums
"""


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


"""
Exceptions
"""


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


"""
Classes
"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    """
    Attributes:
        room_id(int): 部屋識別子
        live_id(int): プレイ対象の楽曲識別子
        joined_user_count(int): 部屋に入っている人数
        max_user_count(int): 部屋の最大人数
    """

    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int = MAX_USER_COUNT

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    """
    Attributes
        user_id(int): ユーザー識別子
        name(str): ユーザー名
        leader_card_id(int): 設定アバター
        select_difficulty(LiveDifficulty): 選択難易度
        is_me(bool): リクエスト投げたユーザーと同じか
        is_host(bool): 部屋を立てた人か
    """

    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool = False
    is_host: bool = False

    class Config:
        orm_mode = True


class RoomMember(BaseModel):
    name: str
    room_id: int
    token: str
    is_host: bool = False
    select_difficulty: LiveDifficulty

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    """
    Attributes
        user_id(int): ユーザー識別子
        judge_count_list(list[int]): 各判定数（良い判定から昇順）
        score(int): 獲得スコア
    """

    user_id: int
    judge_count_list: list[int]
    score: int

    class Config:
        orm_mode = True
