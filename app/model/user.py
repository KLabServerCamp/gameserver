from typing import Optional
import uuid
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound


from app.db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げる"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    # 外部に見られてもいいもの

    id: int
    name: str
    leader_card_id: int

    class Config:
        orm_mode = True


def create_user(name: str, leader_card_id: int) -> str:
    """Create new user and returns their token"""
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        _ = conn.execute(
            text(
                """
                INSERT
                    INTO
                        `user` (`name`, `token`, `leader_card_id`)
                    VALUES
                        (:name, :token, :leader_card_id)
                """
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
        # print(f"create_user(): id={result.lastrowid} {token=}")
    return token


def get_user_by_token(token: str) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def _get_user_by_token(conn, token: str) -> Optional[SafeUser]:
    res = conn.execute(
        text(
            """
            SELECT
                `id`,
                `name`,
                `leader_card_id`
            FROM
                `user`
            WHERE
                `token` = :token
            """
        ),
        {"token": token},
    )
    try:
        row = res.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_id(user_id: int) -> Optional[SafeUser]:
    with engine.begin() as conn:
        return _get_user_by_id(conn, user_id)


def _get_user_by_id(conn, user_id: int) -> Optional[SafeUser]:
    row = conn.execute(
        text(
            """
            SELECT
                `id`,
                `name`,
                `leader_card_id`
            FROM
                `user`
            WHERE
                `id` = :user_id
            """
        ),
        {"user_id": user_id},
    )
    try:
        res = row.one()
    except NoResultFound:
        return None

    return SafeUser.from_orm(res)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        return _update_user(conn=conn, token=token, name=name, leader_card_id=leader_card_id)


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    me = _get_user_by_token(conn, token)
    if me is None:
        raise InvalidToken()
    _ = conn.execute(
        text(
            """
            UPDATE
                `user`
            SET
                `name` = :name,
                `leader_card_id` = :leader_card_id
            WHERE
                `token` = :token
            """
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )

    return None
