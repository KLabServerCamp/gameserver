import json
import uuid
from enum import IntEnum
from typing import Optional

import sqlalchemy.engine.base
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine
from .exceptions import InvalidToken

MAX_USER_COUNT = 4


class LiveDifficulty(IntEnum):
    """プレイする楽曲の難易度"""

    NORMAL = 1
    """ノーマル難易度"""
    HARD = 2
    """ハード難易度"""


class JoinRoomResult(IntEnum):
    """ルームに参加した結果"""

    OK = 1
    """入場OK"""
    ROOM_FULL = 2
    """満員"""
    DISBANDED = 3
    """解散済み"""
    OTHER_ERROR = 4
    """その他エラー"""


class WaitRoomStatus(IntEnum):
    """ルーム待機中の状態"""

    WAITING = 1
    """ホストがライブ開始ボタン押すのを待っている"""
    LIVE_START = 2
    """ライブ画面遷移OK"""
    DISSOLUTION = 3
    """解散された"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


class RoomUser(BaseModel):
    """ルームに参加しているユーザー

    Attributes
    ----------
    user_id: int
        ユーザー識別子
    name: str
        ユーザ名
    leader_card_id: int
        設定アバター
    select_difficulty: LiveDifficulty
        選択難易度
    is_me: bool
        リクエストを投げたユーザと同じか
    is_host: bool
        部屋を立てた人か
    """

    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool

    class Config:
        orm_mode = True


class ResultUser(BaseModel):
    """ユーザのスコア情報

    Attributes
    ----------
    user_id: int
        ユーザー識別子
    judge_count_list: list[int]
        各判定数（良い判定から昇順）
    score: int
        スコア
    """

    user_id: int
    judge_count_list: list[int]
    score: int

    class Config:
        orm_mode = True


class RoomInfo(BaseModel):
    """ルーム情報

    Attributes
    ----------
    room_id: int
        部屋識別子
    live_id: int
       プレイ対象の楽曲識別子
    joined_user_count: int
        部屋に入っている人数
    max_user_count: int
        部屋の最大人数
    """

    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        _ = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(result)
    return token


def _get_user_by_token(
    conn: "sqlalchemy.engine.base.Connection", token: str
) -> Optional[SafeUser]:
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token` = :token"
        ),
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
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken()
        conn.execute(
            text(
                "UPDATE `user` SET `name` = :name, `leader_card_id` = :leader_card_id WHERE `token` = :token"
            ),
            dict(name=name, leader_card_id=leader_card_id, token=token),
        )


def create_room(token: str, live_id: int) -> int:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken()
        # NOTE:room_idは一意になるようにしたい
        res = conn.execute(text("SELECT COUNT(*) FROM `room`"))
        room_id = int(res.one()[0] + 1)
        conn.execute(
            text(
                """
                INSERT INTO `room` (
                    room_id,
                    live_id,
                    status,
                    max_user_count
                ) VALUES (
                    :room_id,
                    :live_id,
                    :status,
                    :max_user_count
                )"""
            ),
            dict(
                room_id=room_id,
                live_id=live_id,
                status=int(WaitRoomStatus.WAITING),
                max_user_count=MAX_USER_COUNT,
            ),
        )

    return room_id


def insert_room_member(
    room_id: int, user_id: int, live_difficulty: LiveDifficulty, is_owner: bool
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO `room_member` (
                    room_id,
                    user_id,
                    live_difficulty,
                    is_owner, is_end,
                    score,
                    judge
                ) VALUES (
                    :room_id,
                    :user_id,
                    :live_difficulty,
                    :is_owner,
                    false,
                    0,
                    '')
                """,
            ),
            dict(
                room_id=room_id,
                user_id=user_id,
                live_difficulty=int(live_difficulty),
                is_owner=is_owner,
            ),
        )


def _get_room_list_all() -> list[RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.status = :status
                GROUP BY
                    room.room_id
                HAVING
                    joined_user_count < max_user_count
            """
            ),
            dict(status=int(WaitRoomStatus.WAITING)),
        )
    res = res.fetchall()
    if len(res) == 0:
        return []
    return [RoomInfo.from_orm(row) for row in res]


def _get_room_list_by_live_id(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.live_id = :live_id
                    AND room.status = :status
                GROUP BY
                    room.room_id
                HAVING
                    joined_user_count < max_user_count
            """
            ),
            dict(live_id=live_id, status=int(WaitRoomStatus.WAITING)),
        )

    res = res.fetchall()
    if len(res) == 0:
        return []
    return [RoomInfo.from_orm(row) for row in res]


def get_room_list(live_id: int) -> list[RoomInfo]:
    # NOTE:
    # SQLでは全部取ってきて、Pythonで絞り込むようにしてもいいかも
    if live_id == 0:
        return _get_room_list_all()
    else:
        return _get_room_list_by_live_id(live_id)


def get_room_info_by_room_id(room_id: int) -> Optional[RoomInfo]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room.room_id,
                    room.live_id,
                    count(room_member.user_id) as joined_user_count,
                    max_user_count
                FROM
                    room
                    JOIN room_member
                        ON room.room_id = room_member.room_id
                WHERE
                    room.room_id = :room_id
            """
            ),
            dict(room_id=room_id),
        )
        try:
            row = res.one()
        except NoResultFound:
            return None
        return RoomInfo.from_orm(row)


def join_room(
    room_id: int, user_id: int, live_difficulty: LiveDifficulty
) -> JoinRoomResult:
    room_info = get_room_info_by_room_id(room_id)

    if room_info is None or room_info.joined_user_count == 0:
        return JoinRoomResult.DISBANDED

    if room_info.joined_user_count >= room_info.max_user_count:
        return JoinRoomResult.ROOM_FULL

    # TODO:
    # すでに他のRoomに参加していたらエラーにするか、別の部屋に移動させる

    insert_room_member(room_id, user_id, live_difficulty, False)
    return JoinRoomResult.OK


def get_room_user_list(room_id: int, user_id: int) -> list[RoomUser]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    room_member.user_id,
                    user.name,
                    user.leader_card_id,
                    room_member.live_difficulty AS select_difficulty,
                    user.id = :user_id AS is_me,
                    room_member.is_owner AS is_host
                FROM
                    room_member
                    JOIN user
                        ON room_member.user_id = user.id
                WHERE
                    room_id = :room_id
                """
            ),
            dict(room_id=room_id, user_id=user_id),
        )
    res = res.fetchall()

    if len(res) == 0:
        return []
    return [RoomUser.from_orm(row) for row in res]


def get_room_status(room_id: int) -> WaitRoomStatus:
    with engine.begin() as conn:
        res = conn.execute(
            text("SELECT status FROM room WHERE room_id = :room_id"),
            dict(room_id=room_id),
        )

    try:
        status = res.one()
    except NoResultFound:
        raise Exception("room not found")

    return WaitRoomStatus(status[0])


def start_room(room_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE room SET status = :status WHERE room_id = :room_id"),
            dict(room_id=room_id, status=int(WaitRoomStatus.LIVE_START)),
        )


def store_score(
    room_id: int, user_id: int, judge_count_list: list[int], score: int
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE room_member
                SET
                    is_end = true,
                    score = :score,
                    judge = :judge_count_list
                WHERE
                    room_id = :room_id
                    AND user_id = :user_id
            """
            ),
            dict(
                room_id=room_id,
                user_id=user_id,
                score=score,
                judge_count_list=json.dumps(judge_count_list),
            ),
        )


def get_room_result(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        res = conn.execute(
            text(
                """
                SELECT
                    user_id,
                    judge AS judge_count_list,
                    score
                FROM
                    room_member
                WHERE
                    room_id = :room_id
                    AND is_end = true
                """
            ),
            dict(room_id=room_id),
        )
    res = res.fetchall()

    if len(res) == 0:
        return []

    return [
        ResultUser(
            user_id=row.user_id,
            judge_count_list=json.loads(row.judge_count_list),
            score=row.score,
        )
        for row in res
    ]


def leave_room(room_id: int, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM room_member WHERE room_id = :room_id AND user_id = :user_id"
            ),
            dict(room_id=room_id, user_id=user_id),
        )


def move_owner_to(room_id: int, user_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE
                    room_member
                SET
                    is_owner = true
                WHERE room_id = :room_id AND user_id = :user_id
            """
            ),
            dict(room_id=room_id, user_id=user_id),
        )


def delete_room(room_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM room WHERE room_id = :room_id"),
            dict(room_id=room_id),
        )
        conn.execute(
            text("DELETE FROM room_member WHERE room_id = :room_id"),
            dict(room_id=room_id),
        )
