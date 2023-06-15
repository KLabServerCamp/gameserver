import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    # SafeUser.from_orm(row) できるようにする
    class Config:
        orm_mode = True


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
    return SafeUser.from_orm(row)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        # TODO: 実装
        conn.execute(
            text(
                "UPDATE `user` SET `name`=:name, `leader_card_id`=:leader_card_id "
                "WHERE `token`=:token"
            ),
            {"name": name, "leader_card_id": leader_card_id, "token": token},
        )
    return None


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class WaitRoomStatus(IntEnum):
    Waiting = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart = 2  # ライブ画面遷移OK
    Dissolution = 3  # 解散された


def create_room(token: str, live_id: int, difficulty: LiveDifficulty) -> int:
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        # TODO: 実装
        result = conn.execute(
            text(
                "INSERT INTO `room` (live_id, owner, status)"
                " VALUES (:live_id, :owner, :status)"
            ),
            {
                "live_id": live_id,
                "owner": user.id,
                "status": int(WaitRoomStatus.Waiting),
            },
        )
        print(f"create_room(): {result.lastrowid=}")
    return result.lastrowid


def get_user_count_in_room(room_id: int) -> int:
    # 部屋のメンバー数を取得
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM `room_member` WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        member_count = result.scalar()
    return member_count


def get_room_list(live_id: int) -> list[tuple[int, int]]:
    with engine.begin() as conn:
        if live_id == 0:
            result = conn.execute(text("SELECT * FROM room"))
            return result.all()
        else:
            result = conn.execute(
                text("SELECT `room_id`,`live_id` FROM room WHERE `live_id`=:live_id"),
                {"live_id": live_id},
            )
            return result.all()


class JoinRoomResult(IntEnum):
    """難易度"""

    Ok = 1  # 入場OK
    RoomFull = 2  # 満員
    Disbanded = 3  # 解放済み
    OtherError = 4  # その他エラー


def join_room(
    token: str, room_id: int, select_difficulty: LiveDifficulty
) -> JoinRoomResult:
    with engine.begin() as conn:
        try:
            user = _get_user_by_token(conn, token)
            if user is None:
                raise InvalidToken
        except InvalidToken:
            return JoinRoomResult.OtherError

        result = conn.execute(
            text("SELECT * FROM room WHERE `room_id`=:room_id FOR UPDATE"),
            {"room_id": room_id},
        )
        try:
            row = result.one()
        except NoResultFound:
            return JoinRoomResult.Disbanded
        max_user_count = 4  # 仮

        # 部屋のメンバー数を取得
        member_count = get_user_count_in_room(room_id)

        if member_count < max_user_count:
            owner = conn.execute(text("SELECT owner FROM room")).scalar()
            is_host = user.id == owner
            conn.execute(
                text(
                    "INSERT INTO `room_member` (room_id,user_id,select_difficulty,is_host)"
                    "VALUES (:room_id,:user_id,:select_difficulty,:is_host)"
                ),
                {
                    "room_id": room_id,
                    "user_id": user.id,
                    "select_difficulty": int(select_difficulty),
                    "is_host": is_host,
                },
            )
            return JoinRoomResult.Ok
        else:
            return JoinRoomResult.RoomFull


def get_wait_room_member(token: str, room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT
                    room_member.user_id,
                    user.name,
                    user.leader_card_id,
                    room_member.is_host,
                    room_member.select_difficulty
                FROM room_member
                INNER JOIN user ON room_member.user_id = user.id
                WHERE room_member.room_id = :room_id
                """
            ),
            {"room_id": room_id},
        )
        return result.all()


def get_wait_room_status(room_id: int):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT `status` FROM room WHERE `room_id`=:room_id"),
            {"room_id": room_id},
        )
        return result.scalar()
