from sqlalchemy import text

from app import schemas
from app.db import engine

from .util import _get_user_by_token


class User:
    @staticmethod
    def create(name: str, leader_card_id: int) -> str:
        """Create new user and returns their token"""
        import uuid

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

    @staticmethod
    def get_user_by_token(token: str) -> schemas.SafeUser | None:
        with engine.begin() as conn:
            return _get_user_by_token(conn, token)

    @staticmethod
    def update(token: str, name: str, leader_card_id: int) -> None:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id WHERE `token`=:token"
                ),
                {"token": token, "name": name, "leader_card_id": leader_card_id},
            )
