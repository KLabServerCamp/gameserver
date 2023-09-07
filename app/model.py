import uuid
from enum import IntEnum

from pydantic import BaseModel  # , ConfigDict makeformatのエラー対策
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine
# from .api import RoomInfo


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
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id`" "FROM `user`" "WHERE `token`=:token"
        ),
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
        try:
            conn.execute(
                text(
                    "UPDATE `user` "
                    "SET name=:name, leader_card_id=:leader_card_id "
                    "WHERE token=:token"
                ),
                {"token": token, "name": name, "leader_card_id": leader_card_id},
            )
        except Exception as e:
            print(f"Error updating user: {str(e)}")
            return None
        print("User updated successfully.")


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


def create_room(token: str, live_id: int, select_difficulty: LiveDifficulty):
    print(select_difficulty)
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        else:
            result = conn.execute(
                text(
                    "INSERT INTO `room` (live_id, select_difficulty)"
                    " VALUES (:live_id, :select_difficulty)"
                ),
                {"live_id": live_id, "select_difficulty": select_difficulty.value},
            )
            room_id = result.lastrowid  # DB側で生成された PRIMARY KEY を参照できる
            print(f"create_room(): {room_id=}")
    return room_id


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


def list_room(token: str, live_id: int):
    """live_idから作成されているroomを返す"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        else:
            if live_id==0:
                result = conn.execute(
                    text(
                        "SELECT room_id, live_id, joined_user_count, max_user_count FROM room "
                    ),
                )
            else:
                result = conn.execute(
                    text(
                        "SELECT room_id, live_id, joined_user_count, max_user_count FROM room "
                        "WHERE live_id = :live_id"
                    ),
                    {"live_id": live_id},
                )
            # TODO:以下、もっと良い方法ありそう
            room_info_list = [
                RoomInfo(
                    room_id=row.room_id,
                    live_id=row.live_id,
                    joined_user_count=row.joined_user_count,
                    max_user_count=row.max_user_count
                )
                for row in result.fetchall()
            ]

    return room_info_list     
