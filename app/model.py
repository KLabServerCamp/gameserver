import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text, Connection
from sqlalchemy.exc import NoResultFound

from .db import engine


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
        # DB側で生成されたPRIMARY KEYを参照できる
        print(f"create_user(): {result.lastrowid=}")
    return token


def _get_user_by_token(conn, token: str) -> SafeUser | None:
    # TODO: 実装(わからなかったら資料を見ながら)
    result = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` "
             "FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()  # 結果の一意性確認
    except NoResultFound:
        return None
    return SafeUser.model_validate(
        row, from_attributes=True
    )  # row からオブジェクトへの変換 (pydantic)
    ...


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        # TODO: 実装
        conn.execute(
            text(
                "UPDATE `user` SET "
                "`name`=:name, `leader_card_id`=:leader_card_id "
                "WHERE `token`=:token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )
        return
        ...


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

        result = conn.execute(text(
            "INSERT INTO `room` (`live_id`) "
            "VALUES (:live_id)"),
            {"live_id": live_id}
        )
        room_id = result.lastrowid

        _join_room(conn, user, RoomJoinRequest(
            room_id=room_id,
            select_difficulty=difficulty)
        )

        return room_id


MAX_USER_COUNT = 4


class RoomListRequest(BaseModel):
    live_id: int


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


def list_room(req) -> list[RoomInfo]:
    rid = req.live_id
    reslist = []
    with engine.begin() as conn:
        result = conn.execute(text(
            "SELECT `id`, `live_id` FROM `room` WHERE `live_id`=:live_id"
            ),
            {"live_id": rid}
        ) if rid != 0 else conn.execute(text(
            "SELECT `id`, `live_id` FROM `room`"
        ))
        rows = result.fetchall()
        for row in rows:
            room_id = row.id
            live_id = row.live_id
            result = conn.execute(text(
                "SELECT `user_id` FROM `room_member` WHERE `room_id`=:room_id"
                ),
                {"room_id": room_id}
            )
            users = result.fetchall()
            reslist.append(RoomInfo(
                room_id=room_id,
                live_id=live_id,
                joined_user_count=len(users),
                max_user_count=MAX_USER_COUNT
            ))
    return reslist


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult
    

def join_room(token: str, req: RoomJoinRequest) -> RoomJoinResponse:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        return _join_room(conn, user, req)


def _join_room(conn, user, req: RoomJoinRequest):
    room_id = req.room_id
    difficulty = req.select_difficulty

    # [確認] 参加中の部屋が無いこと (OtherError)
    result = conn.execute(text(
        "SELECT * FROM `room_member` WHERE `user_id`=:uid"
        ),
        {"uid": user.id}
    )
    rows = result.fetchall()
    if len(rows) > 0:   # not empty
        print("you are already in a room. user_id={}, room_id={}"
              .format(user.id, rows[0].room_id))
        return RoomJoinResponse(join_room_result=JoinRoomResult.OtherError)

    # [確認] 参加先の部屋が存在すること (OtherError)
    result = conn.execute(text(
        "SELECT * FROM `room` WHERE `id`=:rid"
        ),
        {"rid": req.room_id}
    )
    try:
        result.one()
    except NoResultFound:
        print("no such room, room_id: ", req.room_id)
        return RoomJoinResponse(join_room_result=JoinRoomResult.OtherError)

    # room = result.fetchall()[0]

    # [確認] 参加先の部屋に空席があること (RoomFull)
    result = conn.execute(text(
        "SELECT * FROM `room_member` WHERE `room_id`=:rid"
        ),
        {"rid": req.room_id}
    )
    cnt = len(result.fetchall())
    if cnt >= MAX_USER_COUNT:
        return RoomJoinResponse(join_room_result=JoinRoomResult.RoomFull)

    # 参加可能
    conn.execute(text(
        "INSERT INTO `room_member` (`room_id`, `user_id`, `difficulty`) "
        "VALUES (:room_id, :user_id, :difficulty)"),
        {
            "room_id": room_id,
            "user_id": user.id,
            "difficulty": int(difficulty)
        }
    )
    return RoomJoinResponse(join_room_result=JoinRoomResult.Ok)

