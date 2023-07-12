import uuid
from typing import Any

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

    query_text: str = (
        "SELECT id as room_id, live_id, COALESCE(mem_cnt, 0) as joined_user_count, max_user_count FROM room "
        "LEFT OUTER JOIN (SELECT room_id, COUNT(*) as mem_cnt FROM room_member GROUP BY room_id) AS mem_cnts "
        "ON room.id=mem_cnts.room_id"
    )
    query_params: dict[str, Any] = {}

    if live_id != 0:
        query_text += " WHERE room.live_id=:live_id"
        query_params["live_id"] = live_id

    results = conn.execute(text(query_text), parameters=query_params)
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
        return _get_room_list(conn, live_id=live_id)


def _join_room(
    conn: Connection, room_id: int, user_id: int, difficulty: models.LiveDifficulty
) -> models.JoinRoomResult:
    room_info: models.RoomInfo
    
    # TODO: リクエストしたユーザが、既に他の部屋に入場していないか確認する必要がある。
    
    # 指定された room_id に該当する room が DB に存在しているか確認します。
    # FOR UPDATE を追記することで、このクエリ以降、排他処理します。
    res = conn.execute(
        text(
            "SELECT id as room_id, live_id, COALESCE(mem_cnt, 0) as joined_user_count, max_user_count FROM room "
            "LEFT OUTER JOIN (SELECT room_id, COUNT(*) as mem_cnt FROM room_member GROUP BY room_id) AS mem_cnts "
            "ON room.id=mem_cnts.room_id "
            "WHERE room.id=:room_id "
            "FOR UPDATE"
        ),
        parameters={"room_id": room_id},
    )

    # 存在しない場合、既に解散しているとみなします
    try:
        row = res.one()
    except Exception as e:
        print(e)
        return models.JoinRoomResult.Disbanded
    else:
        room_info = models.RoomInfo.model_validate(row, from_attributes=True)

    # room_info に基づいて、入場済みメンバー数が定員が超えていないか確認します。
    if room_info.joined_user_count >= room_info.max_user_count:
        return models.JoinRoomResult.RoomFull

    conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, selected_difficulty) "
            "VALUES (:room_id, :user_id, :difficulty)"
        ),
        parameters={"room_id": room_id, "user_id": user_id, "difficulty": difficulty.value},
    )

    return models.JoinRoomResult.Ok


def join_room(
    token: str, room_id: int, difficulty: models.LiveDifficulty
) -> models.JoinRoomResult:
    # JoinRoomResult
    # Ok	1	入場OK
    # RoomFull	2	満員
    # Disbanded	3	解散済み
    # OtherError	4	その他エラー
    
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return models.JoinRoomResult.OtherError
        return _join_room(conn, room_id=room_id, user_id=user.id, difficulty=difficulty)
    