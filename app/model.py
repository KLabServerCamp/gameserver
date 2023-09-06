import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


# サーバーで生成するオブジェクトは strict を使う
class SafeUser(BaseModel, strict=True):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int


# UUID4は天文学的な確率だけど衝突する確率があるので、気にするならリトライする必要がある。
# サーバーでリトライしない場合は、クライアントかユーザー（手動）にリトライさせることになる。
# ユーザーによるリトライは一般的には良くないけれども、確率が非常に低ければ許容できる場合もある。
def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
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
        text(
            "SELECT `id`, `name`, `token`, `leader_card_id`"
            "FROM `user` WHERE `token`=:token"
        ),
        {"token": token},
    )
    print(result)
    return result.fetchone()


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE `user` SET name=:name, leader_card_id=:leader_card_id "
                "WHERE token=:token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )
        print({"name": name, "leader_card_id": leader_card_id, "token": token})
        conn.commit()


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        # TODO: 実装
