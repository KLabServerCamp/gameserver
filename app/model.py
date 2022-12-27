import json
import uuid
from enum import Enum, IntEnum
from typing import Optional

# from db import engine
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine  # データベースの管理をしている


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


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
    with engine.begin() as conn:  # エラーが起きた場合には自動でロールバックしてくれる。
        result = conn.execute(
            text(  # SQLAlchemyで処理できるようにするためにテキスト化する必要がある。　第二引数の辞書を参照することで、VALUESに挿入される。
                "INSERT INTO `user` (name, token, leader_card_id) VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    # TODO: 実装
    with engine.begin() as conn:
        result = conn.execute(
            text(
                "SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token` = :token"
            ),
            {"token": token},
        )
        try:
            row = result.one()
            print(type(row), type(row[0]), type(row[1]), type(row[2]))
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
        reult = conn.execute(
            text(
                "UPDATE `user` SET `name`=:name, `leader_card_id`=:id WHERE `token`=:token"
            ),
            {"name": name, "id": leader_card_id, "token": token},
        )


if __name__ == "__main__":
    conn = engine.connect()
    token = create_user(name="honoka", leader_card_id=1)
    update_user(token, "honono", 50)
    res = _get_user_by_token(conn, token)
    print(res)
