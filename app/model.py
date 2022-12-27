import json
import random
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

"""
Constants
"""


MAX_USER_COUNT = 4


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


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


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
    max_user_count: int


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
    is_me: bool
    is_host: bool


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


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token` = :token"
        ),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    # このコードを実装してもらう
    with engine.begin() as conn:
        # TODO: 実装
        return _update_user(conn, token, name, leader_card_id)


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    result = conn.execute(
        text(
            "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE `token` = :token"
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )
    print(result)
    return


def create_room(live_id: int, select_difficulty: LiveDifficulty, token: str) -> int:
    with engine.begin() as conn:
        return _create_room(conn, live_id, select_difficulty, token)


def _create_room(
    conn, live_id: int, select_difficulty: LiveDifficulty, token: str
) -> int:
    room_id = random.randint(0, 1000000000)

    _ = conn.execute(
        text(
            "INSERT INTO `room` (live_id, room_id, joined_user_count, max_user_count, status) VALUES (:live_id, :room_id, :joined_user_count, :max_user_count, :status)"
        ),
        {
            "live_id": live_id,
            "room_id": room_id,
            "joined_user_count": 1,
            "max_user_count": MAX_USER_COUNT,
            "status": WaitRoomStatus.Waiting.value,
        },
    )

    user = _get_user_by_token(conn, token)
    _ = conn.execute(
        text(
            "INSERT INTO `room_member` (name, room_id, is_host) VALUES (:name, :room_id, :is_host)"
        ),
        {"name": user.name, "room_id": room_id, "is_host": True},
    )
    return room_id
