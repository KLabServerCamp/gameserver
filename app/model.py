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
from .config import JUDGE_COLUMNS, MAX_USER_COUNT


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


def commit(conn):
    conn.execute(text("COMMIT"))


def rollback(conn):
    conn.execute(text("ROLLBACK"))


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        while not (_get_user_by_token(conn, token) is None):
            token = str(uuid.uuid4())
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
    # room_idも衝突を回避する必要がある
    room_id = random.randint(0, 1000000000)
    while not (_get_room_by_room_id(conn, room_id) is None):
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
            "INSERT INTO `room_member` (name, room_id, user_id, token, is_host, select_difficulty) VALUES (:name, :room_id, :user_id, :token, :is_host, :select_difficulty)"
        ),
        {
            "name": user.name,
            "room_id": room_id,
            "user_id": user.id,
            "token": token,
            "is_host": True,
            "select_difficulty": select_difficulty.value,
        },
    )
    return room_id


def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        return _get_room_list(conn, live_id)


def _get_room_list(conn, live_id: int) -> list[RoomInfo]:
    if live_id == 0:
        result = conn.execute(
            text(
                "SELECT `live_id`, `room_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `status` = :status AND `joined_user_count` < `max_user_count`"
            ),
            {"status": WaitRoomStatus.Waiting.value},
        )
    else:
        result = conn.execute(
            text(
                "SELECT `live_id`, `room_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id` = :live_id AND `status` = :status AND `joined_user_count` < `max_user_count`"
            ),
            {"live_id": live_id, "status": WaitRoomStatus.Waiting.value},
        )
    try:
        rows = result.all()
    except NoResultFound:
        return None
    return [RoomInfo.from_orm(row) for row in rows]


def _get_room_by_room_id(conn, room_id: int, rock: bool = False) -> Optional[RoomInfo]:
    query = "SELECT `live_id`, `room_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `room_id` = :room_id"
    if rock:
        query += " FOR UPDATE"
    result = conn.execute(
        text(query),
        {"room_id": room_id},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return RoomInfo.from_orm(row)


def join_room(
    room_id: int, select_difficulty: LiveDifficulty, token: str
) -> JoinRoomResult:
    with engine.begin() as conn:
        return _join_room(conn, room_id, select_difficulty, token)


def _join_room(
    conn, room_id: int, select_difficulty: LiveDifficulty, token: str
) -> JoinRoomResult:
    room = _get_room_by_room_id(conn, room_id, rock=True)
    if room is None:
        commit(conn)
        return JoinRoomResult.Disbanded

    if room.joined_user_count >= room.max_user_count:
        commit(conn)
        return JoinRoomResult.RoomFull

    if room.status != WaitRoomStatus.Waiting.value:
        commit(conn)
        return JoinRoomResult.OtherError

    # you are already in the room
    if not (_get_room_member_by_room_id_and_token(conn, room_id, token) is None):
        commit(conn)
        return JoinRoomResult.OtherError

    user = _get_user_by_token(conn, token)
    _ = conn.execute(
        text(
            "INSERT INTO `room_member` (name, room_id, user_id, token, is_host, select_difficulty) VALUES (:name, :room_id, :user_id, :token, :is_host, :select_difficulty)"
        ),
        {
            "name": user.name,
            "room_id": room_id,
            "user_id": user.id,
            "token": token,
            "is_host": False,
            "select_difficulty": select_difficulty.value,
        },
    )

    _ = conn.execute(
        text(
            "UPDATE `room` SET `joined_user_count` = `joined_user_count` + 1 WHERE `room_id` = :room_id"
        ),
        {
            "room_id": room_id,
        },
    )

    commit(conn)

    return JoinRoomResult.Ok


def _get_room_member_by_room_id_and_token(
    conn, room_id: int, token: str
) -> Optional[RoomMember]:
    result = conn.execute(
        text(
            "SELECT `name`, `room_id`, `token`, `token`, `is_host`, `select_difficulty` FROM `room_member` WHERE `room_id` = :room_id AND `token` = :token"
        ),
        {
            "room_id": room_id,
            "token": token,
        },
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return RoomMember.from_orm(row)


def get_room_wait(room_id: int, token: str) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        return _get_room_wait(conn, room_id, token)


def _get_room_wait(
    conn, room_id: int, token: str
) -> tuple[WaitRoomStatus, list[RoomUser]]:
    status = _get_room_status(conn, room_id)
    if status != WaitRoomStatus.Waiting.value:
        return status, []

    result = conn.execute(
        text(
            "SELECT `name`, `room_id`, `token`, `is_host`, select_difficulty FROM `room_member` WHERE `room_id` = :room_id"
        ),
        {
            "room_id": room_id,
        },
    )
    try:
        rows = result.all()
    except NoResultFound:
        return WaitRoomStatus.Dissolution, []
    room_user_list = []
    for row in rows:
        this_member = RoomMember.from_orm(row)
        this_user = convert_room_member_to_room_user(
            conn, this_member, is_me=(this_member.token == token)
        )
        room_user_list.append(this_user)

    return WaitRoomStatus.Waiting, room_user_list


def convert_room_member_to_room_user(
    conn, room_member: RoomMember, is_me=True
) -> RoomUser:
    user = _get_user_by_token(conn, room_member.token)
    return RoomUser(
        user_id=user.id,
        name=room_member.name,
        leader_card_id=user.leader_card_id,
        select_difficulty=room_member.select_difficulty,
        is_host=room_member.is_host,
        is_me=is_me,
    )


def _get_room_status(conn, room_id: int) -> WaitRoomStatus:
    room = _get_room_by_room_id(conn, room_id)
    if room is None:
        return WaitRoomStatus.Dissolution

    result = conn.execute(
        text("SELECT `status` FROM `room` WHERE `room_id` = :room_id"),
        {
            "room_id": room_id,
        },
    )
    try:
        row = result.one()
    except NoResultFound:
        return WaitRoomStatus.OtherError
    return WaitRoomStatus(row[0])


def room_start(room_id: int, token: str) -> None:
    with engine.begin() as conn:
        _room_start(conn, room_id, token)


def _room_start(conn, room_id: int, token: str) -> None:
    member = _get_room_member_by_room_id_and_token(conn, room_id, token)

    if member is None:
        return
    
    if not member.is_host:
        return

    _ = conn.execute(
        text("UPDATE `room` SET `status` = :status WHERE `room_id` = :room_id"),
        {
            "status": WaitRoomStatus.LiveStart.value,
            "room_id": room_id,
        },
    )
    return


def room_end(room_id: int, judge_count_list: list[int], score: int, token: str) -> None:
    with engine.begin() as conn:
        _room_end(conn, room_id, judge_count_list, score, token)


def _room_end(
    conn, room_id: int, judge_count_list: list[int], score: int, token: str
) -> None:
    user = _get_user_by_token(conn, token)
    
    result = conn.execute(
        text(
            "SELECT `score` FROM `room_score` WHERE `room_id` = :room_id AND `user_id` = :user_id"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    # すでにスコアが登録されている場合はreturn(一人を保証)
    # UPDATE実装でも良い
    if result.rowcount > 0:
        return

    query1 = "INSERT INTO `room_score` (`score`, `room_id`, `user_id`"
    query2 = "VALUES (:score, :room_id, :user_id"
    d1 = {"score": score, "room_id": room_id, "user_id": user.id}

    for column, judge_count in zip(JUDGE_COLUMNS, judge_count_list):
        query1 += ", `" + column + "`"
        query2 += ", :" + column
        d1[column] = judge_count

    query1 += ") "
    query2 += ")"
    query = query1 + query2
    _ = conn.execute(text(query), d1)
    return


def get_room_score(room_id: int, token: str) -> list[ResultUser]:
    with engine.begin() as conn:
        return _get_room_score(conn, room_id, token)


"""
room_scoreについて、各判定ごとに数が分かれているのでそれぞれ取得してまとめる必要がある
また、tokenがroom_memberじゃない場合にどうするかを考える必要がある(他の人が取得して問題ないのか)
room_scoreがroomの人数分じゃない時には[]を返す(同じ人が間違って複数回登録してしまった場合、揃わずにできてしまう場合がある->room/endで対応)
"""
def _get_room_score(conn, room_id: int, token: str) -> list[ResultUser]:
    return []