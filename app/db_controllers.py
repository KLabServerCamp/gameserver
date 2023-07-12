import uuid

from sqlalchemy import Connection, text

from . import models
from .db import engine

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


def _get_user_by_token(conn: Connection, token: str) -> models.SafeUser | None:
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
        return models.SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> models.SafeUser | None:
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


"""
Room controllers
"""


def _create_room(
    conn: Connection,
    token: str,
    live_id: int,
    difficulty: models.LiveDifficulty,
    owner_id: int,
) -> int:
    result = conn.execute(
        text("INSERT INTO `room` (live_id, owner_id)" " VALUES (:live_id, :owner_id)"),
        {"live_id": live_id, "owner_id": owner_id},
    )
    return result.lastrowid


def create_room(token: str, live_id: int, difficulty: models.LiveDifficulty) -> int:
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise models.InvalidToken
        room_id = _create_room(conn, token, live_id, difficulty, user.id)
        print(f"create_room(): {room_id=}")
        return room_id


def _get_room_list(conn: Connection, live_id: int) -> list[models.RoomInfo]:
    room_infos: list[models.RoomInfo] = []
    results = conn.execute(
        text(
            "SELECT id as room_id, live_id, COALESCE(mem_cnt, 0) as joined_user_count, max_user_count FROM room "
            "LEFT OUTER JOIN (SELECT room_id, COUNT(*) as mem_cnt FROM room_member GROUP BY room_id) AS mem_cnts "
            "ON room.id=mem_cnts.room_id"
        ),
    )
    for result in results:
        room_info = models.RoomInfo.model_validate(result, from_attributes=True)
        room_infos.append(room_info)
    return room_infos


def get_room_list(live_id: int) -> list[models.RoomInfo]:
    """
    入場可能なルーム一覧を取得

    Args:
        live_id (int): ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）

    Returns:
        room_info_list (list[RoomInfo]): 入場可能なルーム一覧
    """
    with engine.begin() as conn:
        return _get_room_list(conn, live_id=0)
