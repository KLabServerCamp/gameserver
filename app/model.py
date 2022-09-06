# api.pyからimport、参照しないようにしてみる

import json
from urllib import request
import uuid
from enum import Enum, IntEnum
from typing import Optional, Tuple

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

# Enum


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


# Class


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


# 部屋の最大人数
MAX_USER_COUNT = 4


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:  # トランザクション開始！
        result = conn.execute(  # 第1引数でSQL,第2引数で値提供
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    conn = engine.connect()
    result = conn.execute(
        text("SELECT * FROM user WHERE token=:token"),
        dict(token=token),
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
        result = conn.execute(  # 第1引数でSQL,第2引数で値提供
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id WHERE token=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )


def create_room(
    live_id: int, user_data: SafeUser, select_difficulty: LiveDifficulty
) -> int:
    with engine.begin() as conn:  # トランザクション開始！
        # roomデータ追加
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner, status, joined_user_count) VALUES (:live_id, :owner, :status, 1)"
            ),
            {
                "live_id": live_id,
                "owner": user_data.id,
                "status": WaitRoomStatus.Waiting,
            },
        )

        # room_id取得
        result2 = conn.execute(
            text("SELECT `room_id` FROM room WHERE `owner`=user_data.id"),
        )
        try:
            room_id = result.one().room_id
        except NoResultFound:
            return None

        # room_memberデータ追加
        result3 = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, name, leader_card_id, select_difficulty, is_host) \
                    VALUES (:room_id, :user_id, name, :leader_card_id, :select_difficulty, :is_host)"
            ),
            {
                "room_id": room_id,
                "user_id": user_data.id,
                "name": user_data.name,
                "leader_card_id": user_data.leader_card_id,
                "select_difficulty": select_difficulty,
                "is_host": True,
            },
        )

    return room_id


def get_room_list(live_id: int) -> list[RoomInfo]:
    result = None
    room_list = None
    with engine.begin() as conn:
        if live_id == 0:
            # live_idが0の場合は、どの曲の部屋も取得対象とする
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count` \
                    FROM room \
                    WHERE joined_user_count<:max_user_count"
                ),
                {"max_user_count": MAX_USER_COUNT},
            )
        else:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count` \
                    FROM room \
                    WHERE joined_user_count<:max_user_count AND live_id=:live_id"
                ),
                {"max_user_count": MAX_USER_COUNT, "live_id": live_id},
            )

        room_list = [
            RoomInfo(
                room_id=row.room_id,
                live_id=row.live_id,
                joined_user_count=row.joined_user_count,
                max_user_count=MAX_USER_COUNT,
            )
            for row in result.all()
        ]
    return room_list


def join_room(
    room_id: int, user_data: SafeUser, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `joined_user_count` FROM room \
                        WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )

        # 解散済みであった場合の処理
        try:
            joined_user_count = result.one().joined_user_count
        except NoResultFound:
            return JoinRoomResult.Disbanded

        # 満員であった場合の処理
        if joined_user_count >= 4:
            return JoinRoomResult.RoomFull

        # 入場処理
        result2 = conn.execute(
            text(
                "UPDATE `room` \
                        SET joined_user_count=:joined_user_count \
                        WHERE room_id=:room_id"
            ),
            {"joined_user_count": joined_user_count + 1, "room_id": room_id},
        )

        result3 = conn.execute(
            text(
                "INSERT INTO `room_member` (room_id, user_id, name, leader_card_id, select_difficulty, is_host) \
                    VALUES (:room_id, :user_id, name, :leader_card_id, :select_difficulty, :is_host)"
            ),
            {
                "room_id": room_id,
                "user_id": user_data.id,
                "name": user_data.name,
                "leader_card_id": user_data.leader_card_id,
                "select_difficulty": select_difficulty,
                "is_host": False,
            },
        )
    return JoinRoomResult.Ok


def get_wait_room_status(
    room_id: int, request_user_id: int
) -> Tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `status` FROM room \
                        WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            status = result.one().status
        except NoResultFound:
            return WaitRoomStatus.Dissolution, []

        result2 = conn.execute(
            text(
                "SELECT `user_id`, `name`, `leader_card_id`, `select_difficulty`, `is_host`, \
                         FROM room \
                        WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        room_user_list = [
            RoomUser(
                user_id=row.user_id,
                name=row.name,
                leader_card_id=row.leader_card_id,
                select_difficulty=row.select_difficulty,
                is_me=(row.user_id == request_user_id),
                is_host=row.is_host,
            )
            for row in result.all()
        ]
    return status, room_user_list


def room_start_(room_id: int) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room` \
                SET status=:status \
                WHERE room_id=:room_id"
            ),
            {"status": WaitRoomStatus.LiveStart, "room_id": room_id},
        )
    return


def list_to_str(list_data: list[int]) -> str:
    return ",".join(str(data) for data in list_data)


def str_to_list(str_data: str) -> list[int]:
    return [int(data) for data in str_data.split(",")]


def room_end_(
    request_user_id: int, room_id: int, score: int, judge_count_list: list[int]
) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "UPDATE `room_member` \
                SET score=:score, judge=:judge \
                WHERE room_id=:room_id AND user_id=:user_id"
            ),
            {
                "score": score,
                "judge": list_to_str(judge_count_list),
                "room_id": room_id,
                "user_id": request_user_id,
            },
        )
    return


def get_room_result(room_id: int) -> list[ResultUser]:
    room_result = []
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `user_id`, `score`, 'judge' \
                FROM room_member \
                WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        for row in result.all():
            # 全員分揃っていない場合は空リストを返す
            if row.score == None:
                return []
            room_result.append(
                ResultUser(
                    user_id=row.user_id,
                    judge_count_list=str_to_list(row.judge),
                    score=row.score,
                )
            )
    return room_result


def room_leave_(room_id: int, request_user_id: int) -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "DELETE FROM room_member \
                WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )

        result2 = conn.execute(
            text(
                "SELECT joined_user_count \
                FROM room \
                WHERE room_id=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            joined_user_count = result2.one().joined_user_count
        except NoResultFound:
            return

        #最後の1人の場合は部屋を削除
        if joined_user_count <= 1:
            result3 = conn.execute(
                text(
                    "DELETE FROM room \
                    WHERE room_id=:room_id"
                ),
                {"room_id": room_id},
            )
        else:
            result3 = conn.execute(
                text(
                    "UPDATE `room` \
                    SET joined_user_count=:joined_user_count \
                    WHERE room_id=:room_id"
                ),
                {
                    "joined_user_count": joined_user_count - 1,
                    "room_id": room_id
                },
            )
    return
