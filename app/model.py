import uuid
from enum import IntEnum

from pydantic import BaseModel  # , ConfigDict <- 削除
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine

import json


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    # UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
    # サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
    # ユーザーによるリトライは一般的には良くないけれども、
    # 確率が非常に低ければ許容できる場合もある。
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
    # TODO: 実装(わからなかったら資料を見ながら)
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        # TODO: 実装
        conn.execute(
            text(
                "UPDATE `user` SET `name`=:name,"
                " `leader_card_id`=:leader_card_id WHERE `token`=:token"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )


# Room Enum
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    """部屋参加時のステータス"""

    Ok = 1  # 入場OK
    RoomFull = 2  # 満員
    Disbanded = 3  # 解散済み
    OtherError = 4  # その他エラー


class WaitRoomStatus(IntEnum):
    """部屋待機時のステータス"""

    Waiting = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart = 2  # ライブ画面遷移OK
    Dissolution = 3  # 解散された


# Room Models
class RoomInfo(BaseModel, strict=True):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int
    status: int


class RoomUser(BaseModel, strict=True):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel, strict=True):
    user_id: int
    judge_count_list: list[int]
    score: int


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        # TODO: 実装
        result = conn.execute(
            text("INSERT INTO `room` (live_id) VALUES (:live_id)"),
            {"live_id": live_id},
        )
        room_id = result.lastrowid
        _create_room_user(conn, token, room_id, difficulty, is_host=True)
    return room_id


def _create_room_user(
    conn, token: str, room_id: int, difficulty: LiveDifficulty, is_host: bool
) -> None:
    """ユーザーをroom_memberテーブルに追加"""
    user = get_user_by_token(token)

    conn.execute(
        text(
            "INSERT INTO `room_member`"
            " (room_id, user_id, name, leader_card_id, select_difficulty, is_host)"
            " VALUES (:room_id, :user_id, :name, :leader_card_id, :select_difficulty, :is_host)"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
            "name": user.name,
            "leader_card_id": user.leader_card_id,
            "select_difficulty": int(difficulty),
            "is_host": is_host,
        },
    )


def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`,  `joined_user_count`,  `max_user_count`, `status`"
                " FROM `room` WHERE live_id=:live_id AND `joined_user_count` < `max_user_count`"
            ),
            {"live_id": live_id},
        )
        try:
            room_list = []
            for room in result:
                room_list.append(
                    RoomInfo(
                        room_id=room.room_id,
                        live_id=room.live_id,
                        joined_user_count=room.joined_user_count,
                        max_user_count=room.max_user_count,
                        status=room.status,
                    )
                )
        except NoResultFound:
            return None
    return room_list


def join_room(token: str, room_id: int, difficulty: LiveDifficulty) -> JoinRoomResult:
    with engine.begin() as conn:
        # 対象roomの情報を取り出す
        result = conn.execute(
            text(
                "SELECT `joined_user_count`, `max_user_count` FROM `room`"
                " WHERE `room_id`=:room_id "
            ),
            {"room_id": room_id},
        )
        try:
            room = result.one()
            if room.joined_user_count >= room.max_user_count:
                # 満員
                return JoinRoomResult.RoomFull
            elif room.wait_room_status == WaitRoomStatus.Dissolution.value:
                # 解散済み
                return JoinRoomResult.Disbanded
        except NoResultFound:
            return JoinRoomResult.OtherError  # その他エラー

        # 以下参加処理
        # room_memberテーブルに追加
        _create_room_user(conn, token, room_id, difficulty, is_host=False)

        new_joined_user_count = room.joined_user_count + 1
        # roomの参加人数を増やす
        conn.execute(
            text(
                "UPDATE `room` SET `joined_user_count`=:joined_user_count"
                " WHERE `room_id`=:room_id"
            ),
            {"room_id": room_id, "joined_user_count": new_joined_user_count},
        )
    return JoinRoomResult.Ok


def get_room_status(token: str, room_id: int) -> WaitRoomStatus:
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM `room` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
    try:
        return result.scalar()
    except NoResultFound:
        return None


def get_room_users(token: str, room_id: int) -> list[RoomUser]:
    user = get_user_by_token(token)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT `user_id`, `name`, `leader_card_id`, `select_difficulty`, `is_host`
                    FROM `room_member` WHERE `room_id`=:room_id
                """
            ),
            {"room_id": room_id},
        )
        try:
            room_user_list = []
            for room_user in result:
                room_user_list.append(
                    RoomUser(
                        user_id=room_user.user_id,
                        name=room_user.name,
                        leader_card_id=room_user.leader_card_id,
                        select_difficulty=LiveDifficulty(room_user.select_difficulty),
                        is_me=room_user.user_id == user.id,
                        is_host=bool(room_user.is_host),
                    )
                )
        except NoResultFound:
            return None

    return room_user_list


def _is_host(room_id: int, user_id: int) -> bool:
    """ user_id が room_id のホストかどうかチェック """
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT `is_host` FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id
                """
            ),
            {"room_id": room_id, "user_id": user_id},
        )
    return result.one().is_host


def start_room(token: str, room_id: int) -> None:

    user = get_user_by_token(token)
    if not _is_host(room_id, user.id):
        return False

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE `room` SET `status`=:status WHERE `room_id`=:room_id
                """
            ),
            {"status": WaitRoomStatus.LiveStart.value, "room_id": room_id},
        )


def end_room(token: str, room_id: int, judge: list[int], score: int) -> None:

    user = get_user_by_token(token)
    judge_json = json.dumps(judge)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE `room_member` SET `score`=:score, `judge_count_list`=:judge_count_list
                 WHERE `room_id`=:room_id AND `user_id`=:user_id
                """
            ),
            {
                "score": score,
                "judge_count_list": judge_json,
                "room_id": room_id,
                "user_id": user.id
            },
        )
