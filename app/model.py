import json
import uuid
from enum import Enum, IntEnum
from operator import ge
from tkinter.messagebox import NO
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.future import Connection

from .db import engine


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
    """Create new user and returns their token

    Parameters
    ----------
    name
        user name
    leader_card_id
        user card leader id
    """
    token = str(uuid.uuid4())
    # NOTE: tokenが衝突したらリトライする必要がある.
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO `user` (name, token, leader_card_id) "
                "VALUES (:name, :token, :leader_card_id)"
            ),
            {"name": name, "token": token, "leader_card_id": leader_card_id},
        )
    return token


def _get_user_by_token(conn: Connection, token: str) -> Optional[SafeUser]:
    result = conn.execute(
        text("SELECT * FROM user WHERE token = :token"), {"token": token}
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> Optional[SafeUser]:
    """Retreive SafeUser obj from token

    Parameters
    ----------
    token
        user token

    Returns
    -------
        SafeUser object
    """
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(
    token: str, name: Optional[str] = None, leader_card_id: Optional[int] = None
) -> None:
    """Update user info through parameters.

    Parameters
    ----------
    token
        user token
    name
        user name
    leader_card_id
        user card id
    """
    user = get_user_by_token(token)
    if user is None:
        return None

    # set values if a parameter is None
    if name is None:
        name = user.name
    if leader_card_id is None:
        leader_card_id = user.leader_card_id

    # execute below only if updating at least one parameter.
    if name != user.name or leader_card_id != user.leader_card_id:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE user SET name = :name, leader_card_id = :leader_card_id "
                    "WHERE token = :token"
                ),
                {"name": name, "leader_card_id": leader_card_id, "token": token},
            )


def show_all_user() -> list[tuple[int, str, str, int]]:
    """Show all users in user table.

    Returns
    -------
    list[tuple(int, str, str, int)]
        all of user table rows
    """
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM user"),
        )
    return result.fetchall()


def get_user_all() -> list[SafeUser]:
    """Retrieve all user

    Returns
    -------
    list[SafeUser]
        SafeUser instances
    """
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT * FROM user"),
        )
    users = []
    for row in result:
        users.append(SafeUser.from_orm(row))
    return users


def delete_user_by_token(token: str) -> None:
    """Delete a user by token

    Parameters
    ----------
    token
        user token
    """
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM user WHERE token = :token"),
            {"token": token},
        )
