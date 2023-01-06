import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
import time

from .db import engine

MAX_ROOM_USER_COUNT = 4
LIVE_ID_NULL = 0
ROOM_MATCHING_TIME_OUT = 5*60  # マッチング部屋のタイムアウト
ROOM_LIVE_TIME_OUT = 5*60       # ライブのタイムアウト
ROOM_WAIT_TIME_OUT = 10          # マッチング部屋でのroom/waitのタイムアウト
ROOM_END_TIME_OUT = 10              # endが呼び出されてからのタイムアウト



class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class InvalidId(Exception):
    """指定されたIdが不正だったときに投げる"""


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
    # TODO: エラー時リトライ
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {
                "name": name, 
                "token": token,
                "leader_card_id": leader_card_id,
            },
        )
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # SELECT * FROM `user` WHERE `token`={token}
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
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


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    # UPDATE `user` SET name={name}, leader_card_id={leader_card_id} WHERE token={token}
    conn.execute(
        text(
            "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE `token`=:token"
        ),
        {
            "name": name, 
            "token": token, 
            "leader_card_id": leader_card_id,
        },
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        _update_user(conn=conn, token=token, name=name, leader_card_id=leader_card_id)


class LiveDifficulty(IntEnum):
    Normal = 1
    Hard = 2


def _create_room(
    conn, token: str, live_id: int, select_difficulty: LiveDifficulty
) -> Optional[int]:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken

    now = int(time.time())

    # roomテーブルに部屋追加
    result = conn.execute(
        text(
            "INSERT INTO `room` SET `live_id`=:live_id, `max_user_count`=:max_user_count, `time_to_live`=:time_to_live",
        ),
        {
            "live_id": live_id, 
            "max_user_count": MAX_ROOM_USER_COUNT, 
            "time_to_live": now+ROOM_MATCHING_TIME_OUT
        },
    )

    room_id = result.lastrowid
    user_id = user.id

    # room_userテーブルにユーザー追加
    result = conn.execute(
        text(
            "INSERT INTO `room_user` SET `room_id`=:room_id, `user_id`=:user_id, `select_difficulty`=:select_difficulty, `is_host`=true, `time_to_live`=:time_to_live"
        ),
        {
            "room_id": room_id,
            "user_id": user_id,
            "select_difficulty": int(select_difficulty),
            "time_to_live": now+ROOM_WAIT_TIME_OUT
        },
    )
    return room_id


def create_room(
    token: str, live_id: int, select_difficulty: LiveDifficulty
) -> Optional[int]:
    with engine.begin() as conn:
        return _create_room(
            conn=conn, token=token, live_id=live_id, select_difficulty=select_difficulty
        )


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

    class Config:
        orm_mode = True


def _list_room(conn, live_id: int) -> list[RoomInfo]:
    """ルーム一覧を取得 live_id=LIVE_ID_NULLで全部屋"""
    now = int(time.time())
    if live_id == LIVE_ID_NULL:
        _update_joined_user_count_all(conn=conn, now=now)
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `is_playing`=false AND `time_to_live`>:time_to_live AND `joined_user_count` BETWEEN 1 AND `max_user_count`"
            ),
            {
                "time_to_live": now,
            }
        )
    else:
        _update_joined_user_count_by_live_id(conn=conn, live_id=live_id, now=now)
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE live_id=:live_id AND `is_playing`=false AND `time_to_live`>:time_to_live AND `joined_user_count` BETWEEN 1 AND `max_user_count`"
            ),
            {
                "live_id": live_id,
                "time_to_live": now,
            },
        )

    rows = result.fetchall()
    return list[int](map(RoomInfo.from_orm, rows))


def list_room(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        return _list_room(conn, live_id=live_id)


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3  # 解散
    OtherError = 4


def _join_room(
    conn, token: str, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken

    now = int(time.time())
    # 抜けた部屋への再入場対策
    result = conn.execute(
        text(
            "DELETE FROM `room_user` WHERE `user_id`=:user_id"
        ),
        {
            "user_id": user.id,
            "time_to_live": now,
        },
    )

    _update_joined_user_count_by_room_id(conn=conn, room_id=room_id, now=now)

    # 空きがあるか確認
    result = conn.execute(
        text(
            "SELECT `joined_user_count`, `max_user_count` FROM `room` WHERE `room_id`=:room_id AND `is_playing`=FALSE FOR UPDATE"
        ),
        {
            "room_id": room_id,
            "time_to_live": now,
        },
    )

    try:
        row = result.one()
    except NoResultFound:
        return JoinRoomResult.Disbanded

    if row["joined_user_count"] >= row["max_user_count"]:
        conn.rollback()
        return JoinRoomResult.RoomFull

    # 部屋に追加
    result = conn.execute(
        text(
            "INSERT INTO `room_user` SET `room_id`=:room_id, `user_id`=:user_id, `select_difficulty`=:select_difficulty, `is_host`=FALSE, `time_to_live`=:time_to_live"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
            "select_difficulty": int(select_difficulty),
            "time_to_live": now+ROOM_WAIT_TIME_OUT,
        },
    )
    result = conn.execute(
        text(
            "UPDATE `room` SET `joined_user_count`=`joined_user_count`+1, `time_to_live`=:time_to_live WHERE `room_id`=:room_id"
        ),
        {
            "room_id": room_id,
            "time_to_live": now+ROOM_MATCHING_TIME_OUT,
        },
    )

    return JoinRoomResult.Ok


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        return _join_room(
            conn, token, room_id=room_id, select_difficulty=select_difficulty
        )


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3  # 解散


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int  # 設定アバター
    select_difficulty: LiveDifficulty
    is_me: bool  # リクエストを投げたユーザーと同じか
    is_host: bool  # 部屋を立てた人か

    class Config:
        orm_mode = True


class WaitRoomResult(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


def _wait_room(conn, token: str, room_id: int) -> WaitRoomResult:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken

    now = int(time.time())

    result = conn.execute(
        text("SELECT `is_playing` FROM `room` WHERE `room_id`=:room_id AND `time_to_live`>:time_to_live FOR UPDATE"),
        {
            "room_id": room_id,
            "time_to_live": now,
        },
    )
    try:
        row = result.one()
    except NoResultFound:
        return WaitRoomResult(status=WaitRoomStatus.Dissolution, room_user_list=[])

    is_playing = row["is_playing"]

    # ホストの確認
    result = conn.execute(
        text(
            "SELECT `user_id`, `is_host` FROM `room_user` WHERE `room_id`=:room_id AND `time_to_live`>:time_to_live FOR UPDATE"
        ),
        {
            "room_id": room_id,
            "time_to_live": now,
        }
    )
    rows = result.fetchall()

    exist_host = False
    for _, row in enumerate(rows):
        if row["is_host"]:
            if row["user_id"] == user.id:
                _update_joined_user_count_by_room_id(conn, room_id=room_id, now=now)
            exist_host = True
            break

    if not exist_host:
        # ホスト更新
        result = conn.execute(
            text(
                "UPDATE `room_user` SET `is_host`=TRUE WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
                "user_id": user.id,
                "room_id": room_id,
            },
        )

    # ユーザー情報
    result = conn.execute(
        text(
            "SELECT `user_id`, `name`, `leader_card_id`, `select_difficulty`, `is_host`, `user_id`=:user_id AS `is_me` FROM `room_user` JOIN `user` ON `user_id`=`id` WHERE `room_id`=:room_id AND `time_to_live`>:time_to_live"
        ),
        {
            "user_id": user.id,
            "room_id": room_id,
            "time_to_live": now,
        },
    )
    rows = result.fetchall()

    room_user_list = list(map(RoomUser.from_orm, rows))

    # プレイ開始
    if is_playing:
        conn.execute(
            text(
                "UPDATE `room_user` SET `time_to_live`=:time_to_live WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
                "time_to_live": now+ROOM_LIVE_TIME_OUT,
            },
        )
        return WaitRoomResult(
            status=WaitRoomStatus.LiveStart, room_user_list=room_user_list
        )
    else:
        conn.execute(
            text(
                "UPDATE `room_user` SET `time_to_live`=:time_to_live WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
                "time_to_live": now+ROOM_WAIT_TIME_OUT,
            },
        )        
        return WaitRoomResult(
            status=WaitRoomStatus.Waiting, room_user_list=room_user_list
        )


def wait_room(token: str, room_id: int) -> WaitRoomResult:
    with engine.begin() as conn:
        return _wait_room(conn, token, room_id)


# room/start
def _start_room(conn, token: str, room_id: int) -> None:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken

    now = int(time.time())

    result = conn.execute(
        text("UPDATE `room` SET `is_playing`=TRUE, `time_to_live`=:time_to_live WHERE `room_id`=:room_id"),
        {
            "room_id": room_id,
            "time_to_live": now+ROOM_WAIT_TIME_OUT,
        },
    )
    result = conn.execute(
        text("UPDATE `room_user` SET `time_to_live`=:time_to_live WHERE `room_id`=:room_id AND `user_id`=:user_id"),
        {
            "room_id": room_id,
            "user_id": user.id,
            "time_to_live": now+ROOM_LIVE_TIME_OUT,
        },
    )


def start_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        _start_room(conn, token, room_id)


# room/end
def _end_room(
    conn, token: str, room_id: int, judge_count_list: list[int], score: int
) -> None:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken
    
    now = int(time.time())

    judge_count_str = ""
    for _, judge in enumerate(judge_count_list):
        judge_count_str += str(judge) + ","
    judge_count_str = judge_count_str.rstrip(",")

    result = conn.execute(
        text(
            "UPDATE `room_user` SET `judge_count_list`=:judge_count_str, `score`=:score WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        {
            "judge_count_str": judge_count_str,
            "score": score,
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    result = conn.execute(
        text(
            "UPDATE `room_user` SET `time_to_live`=:time_to_live WHERE `room_id`=:room_id"
        ),
        {
            "room_id": room_id,
            "time_to_live": now+ROOM_END_TIME_OUT,
        },
    )



def end_room(token: str, room_id: int, judge_count_list: list[int], score: int) -> None:
    with engine.begin() as conn:
        _end_room(conn, token, room_id, judge_count_list, score)


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]  # 各判定数(良い判定から昇順)
    score: int

    class Config:
        orm_mode = True


def _result_room(conn, token: str, room_id: int) -> list[ResultUser]:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken

    now = int(time.time())

    result = conn.execute(
        text(
            "SELECT `user_id`, `judge_count_list`, `score` FROM `room_user` WHERE `room_id`=:room_id AND `time_to_live`>:time_to_live"
        ),
        {
            "room_id": room_id,
            "time_to_live": now,
        },
    )

    rows = result.fetchall()
    print(rows)
    isFinished = len(rows) > 0
    for _, row in enumerate(rows):
        if row["judge_count_list"] is None:
            isFinished = False

    result_user_list = []
    if isFinished:
        for _, row in enumerate(rows):
            judge_count_list = list[int](
                map(int, str.split(row["judge_count_list"], ","))
            )
            result_user_list.append(
                ResultUser(
                    user_id=row["user_id"],
                    judge_count_list=judge_count_list,
                    score=row["score"],
                )
            )

    return result_user_list


def result_room(token: str, room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        return _result_room(conn, token, room_id)


def _leave_room(conn, token: str, room_id: int) -> None:
    user = _get_user_by_token(conn=conn, token=token)
    if user is None:
        raise InvalidToken

    conn.execute(
        text("DELETE FROM `room_user` WHERE `user_id`=:user_id"),
        {
            "user_id": user.id,
        },
    )
    _update_joined_user_count_by_room_id(conn=conn, room_id=room_id, now=int(time.time()))


def leave_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        _leave_room(conn, token, room_id)


def _update_joined_user_count_by_room_id(conn, room_id: int, now: int) -> None:
    conn.execute(
        text("UPDATE `room` SET `joined_user_count` = IFNULL((SELECT COUNT(`user_id`) FROM `room_user` WHERE `room_id`=:room_id AND `time_to_live`>:time_to_live GROUP BY `room_id`),0) WHERE `room_id`=:room_id AND `time_to_live`>:time_to_live"),
        {
            "room_id": room_id,
            "time_to_live": now,
        },
    )


def _update_joined_user_count_by_live_id(conn, live_id: int, now: int) -> None:
    if live_id == LIVE_ID_NULL:
        _update_joined_user_count_all(conn, now)
        return

    result = conn.execute(
        text("SELECT `room_id` FROM `room` WHERE `live_id`=:live_id AND `time_to_live`>:time_to_live AND `joined_user_count` BETWEEN 1 AND `max_user_count`"),
        {
            "live_id": live_id,
            "time_to_live": now,
        },
    )
    rows = result.fetchall()
    for _, row in enumerate(rows):
        _update_joined_user_count_by_room_id(conn, row["room_id"], now)


def _update_joined_user_count_all(conn, now: int) -> None:
    result = conn.execute(
        text("SELECT `room_id` FROM `room` WHERE `time_to_live`>:time_to_live"),
        {
            "time_to_live": now,
        },
    )
    rooms = result.fetchall()
    for _, room in enumerate(rooms):
        _update_joined_user_count_by_room_id(conn, room["room_id"], now)



def _erase_timeout(conn) -> None:
    now = int(time.time())
    conn.execute(
        text("DELETE FROM `room` WHERE `time_to_live`<:time_to_live OR `joined_user_count`=0"),
        {"time_to_live": now},
    )
    conn.execute(
        text("DELETE FROM `room_user` WHERE `time_to_live`<:time_to_live OR `joined_user_count`=0"),
        {"time_to_live": now},
    )

