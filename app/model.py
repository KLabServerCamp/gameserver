import uuid
from enum import IntEnum

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class StrictBase(BaseModel):
    """DBを利用するためのBaseModel"""

    # strictモードを有効にする
    model_config = ConfigDict(strict=True)


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


class SafeUser(StrictBase):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


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


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    conn.execute(
        text(
            "UPDATE `user`"
            " SET name=:name, leader_card_id=:leader_card_id"
            " WHERE token=:token"
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        # TODO: 実装
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        _update_user(conn, token, name, leader_card_id)


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


class RoomInfo(StrictBase):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(StrictBase):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(StrictBase):
    user_id: int
    judge_count_list: list[int]
    score: int


def _create_room(conn, live_id: int, difficulty: LiveDifficulty, user: SafeUser) -> int:
    # 作成
    conn.execute(
        text(
            "INSERT INTO `room` (live_id, owner_id, status) "
            "VALUES (:live_id, :owner_id, :status)"
        ),
        {
            "live_id": live_id,
            "owner_id": user.id,
            "status": WaitRoomStatus.Waiting.value,
        },
    )

    # IDを取りたい
    result = conn.execute(
        text(
            "SELECT `room_id` FROM `room`"
            " WHERE `owner_id`=:owner_id AND `status` NOT IN (:status)"
        ),
        {"owner_id": user.id, "status": WaitRoomStatus.LiveStart.value},
    )
    
    row = result.one()

    # UserをRoomに追加する
    conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, select_difficulty) "
            "VALUES (:room_id, :user_id, :select_difficulty)"
        ),
        {
            "room_id": row.room_id,
            "user_id": user.id,
            "select_difficulty": difficulty,
        },
    )

    return row


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        # TODO: 実装
        room_id: int = _create_room(
            conn=conn,
            live_id=live_id,
            difficulty=difficulty,
            user=user,
        )
        print("ROOOM:", room_id)
        return room_id.room_id


def _get_room(conn, room_id: int, live_id: int) -> RoomInfo:
    res = conn.execute(
        text(
            "SELECT `user_id` FROM `room_member`"
            " WHERE `room_id`=:room_id"
        ),
        {"room_id": room_id},
    )

    room = RoomInfo(
        room_id=room_id,
        live_id=live_id,
        joined_user_count=len(res.all()),
        max_user_count=4,
    )
    return room


def _get_room_list(conn, live_id: int) -> list[RoomInfo]:
    if live_id == 0:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `status` FROM `room`"
            ),
            {}
        )
    else:
        result = conn.execute(
            text(
                "SELECT `room_id`, `live_id`, `status` FROM `room`"
                " WHERE `live_id`=:live_id"
            ),
            {"live_id": live_id},
        )

    try:
        rows = result.all()
    except NoResultFound:
        return []

    room_list = []

    for row in rows:
        print("ROW===")
        print(row)
        room = _get_room(conn, row.room_id, row.live_id)
        room_list.append(room)

    return room_list


def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        room_list = _get_room_list(conn, live_id=live_id)
        print("Room_List: " + f"{room_list}")
        return room_list