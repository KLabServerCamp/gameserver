import json
import uuid
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

MAX_USER = 4

# Enums
class LiveDifficulty(IntEnum):
    normal = 1
    hard = 2


class WaitRoomStatus(IntEnum):
    waiting = 1
    liveStart = 2
    dissolution = 3


class JoinRoomResult(IntEnum):
    ok = 1
    roomFull = 2
    disbanded = 3
    otherError = 4


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: List[int]
    score: int
