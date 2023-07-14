import uuid

from sqlalchemy import Connection, text

from ..db import engine
from ..schemas.structures import SafeUser

"""
User controllers
"""


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


def _get_user_by_token(conn: Connection, token: str) -> SafeUser | None:
    res = conn.execute(
        text("select `id`, `name`, `leader_card_id` from `user` where `token`=:token"),
        parameters={"token": token},
    )
    try:
        row = res.one()
    except Exception as e:
        print(e)
        return None
    else:
        return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def _update_user(conn: Connection, token: str, name: str, leader_card_id: int) -> None:
    conn.execute(
        text(
            "update `user` set name=:name, leader_card_id=:leader_card_id "
            "where `token`=:token"
        ),
        parameters={
            "name": name,
            "leader_card_id": leader_card_id,
            "token": token,
        },
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        _update_user(conn, token, name, leader_card_id)
