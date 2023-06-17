import json
import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


class NotOwner(Exception):
    """APIの実行者がルームのオーナーではなかったときに投げるエラー"""


class InvalidScore(Exception):
    """スコアが不正だったときに投げるエラー"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    # SafeUser.from_orm(row) できるようにする
    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    # UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
    # サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
    # ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id)"
                " VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        print(f"create_user(): {result.lastrowid=}")  # DB側で生成されたPRIMARY KEYを参照できる
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id"
                " WHERE `token`=:token"
            ),
            {"token": token, "name": name, "leader_card_id": leader_card_id},
        )


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int

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
    judge_count_list: list[int]
    score: int


def _update_wait_room_status(
    conn: Connection, room_id: int, status: WaitRoomStatus
) -> None:
    conn.execute(
        text("UPDATE `room` SET `wait_room_status`=:status WHERE `room_id`=:room_id"),
        {"room_id": room_id, "status": status.value},
    )


def create_room(token: str, live_id: int, difficulty: LiveDifficulty) -> int:
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        result = conn.execute(
            text(
                "INSERT INTO `room` SET `live_id`=:live_id, `host_id`=:host_id, `joined_user_count`=:joined_user_count"
                ", `max_user_count`=:max_user_count, `wait_room_status`=:wait_room_status"
            ),
            {
                "live_id": live_id,
                "host_id": user.id,
                "joined_user_count": 1,
                "max_user_count": 4,
                "wait_room_status": WaitRoomStatus.Waiting.value,
            },
        )
        conn.execute(
            text(
                "INSERT INTO `room_user` SET `room_id`=:room_id, `user_id`=:user_id, `difficulty`=:difficulty"
            ),
            {
                "room_id": result.lastrowid,
                "user_id": user.id,
                "difficulty": difficulty.value,
            },
        )
    return result.lastrowid


def room_search(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        # search room only wait_room_status is Waiting
        if live_id == 0:  # Wildcard (search all rooms)
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `wait_room_status`=:wait_room_status"
                ),
                {"wait_room_status": WaitRoomStatus.Waiting.value},
            )
        else:
            result = conn.execute(
                text(
                    "SELECT `room_id`, `live_id`, `joined_user_count`, `max_user_count` FROM `room` WHERE `live_id`=:live_id AND `wait_room_status`=:wait_room_status"
                ),
                {"live_id": live_id, "wait_room_status": WaitRoomStatus.Waiting.value},
            )
        rows = result.all()
        rows = [RoomInfo.from_orm(row) for row in rows]
        return rows


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result = conn.execute(
            text(
                "SELECT `joined_user_count`, `max_user_count`, `wait_room_status` FROM `room` WHERE `room_id`=:room_id"
                " FOR UPDATE"
            ),
            {"room_id": room_id},
        )
        row = result.one()
        if row.wait_room_status == WaitRoomStatus.Dissolution.value:
            return JoinRoomResult.Disbanded
        if row.joined_user_count >= row.max_user_count:
            return JoinRoomResult.RoomFull

        conn.execute(
            text(
                "INSERT INTO `room_user` SET `room_id`=:room_id, `user_id`=:user_id, `difficulty`=:difficulty"
            ),
            {
                "room_id": room_id,
                "user_id": user.id,
                "difficulty": select_difficulty.value,
            },
        )
        conn.execute(
            text(
                "UPDATE `room` SET `joined_user_count`=`joined_user_count`+1 WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
    return JoinRoomResult.Ok


def room_wait_status(token: str, room_id: int) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result = conn.execute(
            text(
                "SELECT `host_id`, `wait_room_status` FROM `room` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        row = result.one()
        host_id = row.host_id
        status = WaitRoomStatus(row.wait_room_status)
        result = conn.execute(
            text(
                "SELECT `user_id`, `difficulty` FROM `room_user` WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return (status, [])

        room_users: list[RoomUser] = []
        for row in rows:
            result = conn.execute(
                text("SELECT `name`, `leader_card_id` FROM `user` WHERE `id`=:user_id"),
                {"user_id": row.user_id},
            )
            row_user = result.one()
            room_users.append(
                RoomUser(
                    user_id=row.user_id,
                    name=row_user.name,
                    leader_card_id=row_user.leader_card_id,
                    select_difficulty=LiveDifficulty(row.difficulty),
                    is_me=row.user_id == user.id,
                    is_host=row.user_id == host_id,
                )
            )
        return (status, room_users)


def room_start(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result = conn.execute(
            text(
                "SELECT `host_id`, `joined_user_count`, `wait_room_status`"
                " FROM `room` WHERE `room_id`=:room_id"
                " FOR UPDATE"
            ),
            {"room_id": room_id},
        )
        row = result.one()
        if row.host_id != user.id:
            raise NotOwner
        _update_wait_room_status(conn, room_id, WaitRoomStatus.LiveStart)


def room_end(token: str, room_id: int, judge_count_list: list[int], score: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        # Perfect, Great, Good, Bad, Miss の5つ
        if len(judge_count_list) != 5:
            raise InvalidScore

        conn.execute(
            text(
                "UPDATE `room_user` SET `score`=:score, `is_end`=true,"
                " `judge_count`=:judge_count"
                " WHERE `room_id`=:room_id AND `user_id`=:user_id"
            ),
            {
                "score": score,
                "room_id": room_id,
                "user_id": user.id,
                "judge_count": json.dumps(judge_count_list),
            },
        )


def room_result(token: str, room_id: int) -> list[ResultUser]:
    # 全員room_endが終わって揃っていないときは空リストを返す
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result = conn.execute(
            text(
                "SELECT `user_id`, `judge_count`, `score` FROM `room_user` WHERE `room_id`=:room_id AND `is_end`=true"
            ),
            {"room_id": room_id},
        )
        try:
            rows = result.all()
        except NoResultFound:
            return []

        # Check if all users have finished
        result = conn.execute(
            text("SELECT `joined_user_count` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        joined_user_count = result.one().joined_user_count
        if len(rows) < joined_user_count:
            return []

        result_user = [
            ResultUser(
                user_id=row.user_id,
                judge_count_list=json.loads(row.judge_count),
                score=row.score,
            )
            for row in rows
        ]

        return result_user


def leave_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken

        result = conn.execute(
            text("SELECT `host_id` FROM `room` WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id},
        )
        row = result.one()
        if row.host_id == user.id:
            # 解散
            _update_wait_room_status(conn, room_id, WaitRoomStatus.Dissolution)
        else:
            # room_userから削除
            conn.execute(
                text(
                    "DELETE FROM `room_user` WHERE `room_id`=:room_id AND `user_id`=:user_id"
                ),
                {"room_id": room_id, "user_id": user.id},
            )
            # roomのjoined_user_countを減らす
            conn.execute(
                text(
                    "UPDATE `room` SET `joined_user_count`=`joined_user_count`-1 WHERE `room_id`=:room_id"
                ),
                {"room_id": room_id},
            )
