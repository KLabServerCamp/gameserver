import json
import logging
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) \
                    VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        logging.log(logging.DEBUG, result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    query_str: str = "SELECT `id`, `name`, `leader_card_id` \
            FROM `user` \
            WHERE `token`=:token"

    result = conn.execute(text(query_str), {"token": token})
    try:
        return SafeUser.from_orm(result.one())
    except NoResultFound:
        return None


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        query_str: str = "UPDATE `user` \
            SET `name` = :name, `leader_card_id` = :leader_id \
            WHERE `token` = :token"

        result = conn.execute(
            text(query_str),
            {"name": name, "leader_id": leader_card_id, "token": token},
        )
        logging.log(logging.DEBUG, result)


# Room


class LiveDifficulty(IntEnum):
    """ライブの難易度"""

    EASY = 1
    NORMAL = 2


class JoinRoomResult(Enum):
    """部屋に参加した結果"""

    OK = 1
    ROOM_FULL = 2
    DISBANDED = 3
    OTHER_ERROR = 4


class WaitRoomStatus(Enum):
    """待機部屋の状態"""

    WAITING = 1
    STARTED = 2
    DISSOLUTION = 3


class RoomInfo(BaseModel):
    """部屋の情報"""

    room_id: int  # 部屋識別子
    live_id: int  # プレイ対象の楽曲識別子
    joined_user_count: int  # 部屋に参加しているユーザー数
    max_user_count: int  # 部屋の最大参加人数


def create_room(token: str, live_id: int, difficulty: LiveDifficulty) -> int:
    raise NotImplementedError


def get_rooms(token: str, live_id: int) -> list[RoomInfo]:
    raise NotImplementedError


def join_room(token: str, room_id: int, difficulty: LiveDifficulty) -> JoinRoomResult:
    raise NotImplementedError


def leave_room(token: str, room_id: int) -> None:
    raise NotImplementedError


class RoomUser(BaseModel):
    """部屋に参加しているユーザーの情報"""

    user_id: int  # ユーザー識別子
    name: str  # ユーザー名
    leader_card_id: int  # リーダーカードの識別子
    selected_difficulty: LiveDifficulty  # 選択難易度
    is_me: bool  # リクエストを投げたユーザーか
    is_host: bool  # 部屋を立てた人か


class ResultUser(BaseModel):
    """結果画面に表示するユーザーの情報"""

    user_id: int  # ユーザー識別子
    judge_count_list: list[int]  # 各判定の数 ()
    score: int  # 獲得スコア


def get_room_result(token: str, room_id: int) -> list[ResultUser]:
    raise NotImplementedError
