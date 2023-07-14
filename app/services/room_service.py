from typing import Any

from sqlalchemy import Connection, text

from ..auth import InvalidToken
from ..db import engine
from ..schemas.enums import JoinRoomResult, LiveDifficulty, WaitRoomStatus
from ..schemas.structures import ResultUser, RoomInfo, RoomUser
from .user_service import _get_user_by_token


def _create_room(
    conn: Connection,
    token: str,
    live_id: int,
    difficulty: LiveDifficulty,
    owner_id: int,
) -> int:
    result = conn.execute(
        text("INSERT INTO `room` (live_id, owner_id)" " VALUES (:live_id, :owner_id)"),
        {"live_id": live_id, "owner_id": owner_id},
    )
    return result.lastrowid


def create_room(token: str, live_id: int, difficulty: LiveDifficulty) -> int:
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        room_id = _create_room(conn, token, live_id, difficulty, user.id)
        print(f"create_room(): {room_id=}")

        _join_room(conn, room_id=room_id, user_id=user.id, difficulty=difficulty)
        return room_id


def _get_room_list(conn: Connection, live_id: int) -> list[RoomInfo]:
    room_infos: list[RoomInfo] = []

    query_text: str = (
        "SELECT id as room_id, live_id, COALESCE(mem_cnt, 0) as joined_user_count, max_user_count "
        "FROM room "
        "LEFT OUTER JOIN (SELECT room_id, COUNT(*) as mem_cnt FROM room_member GROUP BY room_id) AS mem_cnts "
        "ON room.id=mem_cnts.room_id "
        "WHERE is_game_started=0"
    )
    query_params: dict[str, Any] = {}

    if live_id != 0:
        query_text += " AND room.live_id=:live_id"
        query_params["live_id"] = live_id

    results = conn.execute(text(query_text), parameters=query_params)
    for result in results:
        room_info = RoomInfo.model_validate(result, from_attributes=True)
        room_infos.append(room_info)
    return room_infos


def get_room_list(live_id: int) -> list[RoomInfo]:
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
    conn: Connection, room_id: int, user_id: int, difficulty: LiveDifficulty
) -> JoinRoomResult:
    room_info: RoomInfo

    # TODO: リクエストしたユーザが、既に別の部屋（またはこの部屋）に入場していないか確認する必要がある。

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
        return JoinRoomResult.Disbanded
    else:
        room_info = RoomInfo.model_validate(row, from_attributes=True)

    # room_info に基づいて、入場済みメンバー数が定員が超えていないか確認します。
    if room_info.joined_user_count >= room_info.max_user_count:
        return JoinRoomResult.RoomFull

    conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, select_difficulty) "
            "VALUES (:room_id, :user_id, :difficulty)"
        ),
        parameters={
            "room_id": room_id,
            "user_id": user_id,
            "difficulty": difficulty.value,
        },
    )

    return JoinRoomResult.Ok


def join_room(token: str, room_id: int, difficulty: LiveDifficulty) -> JoinRoomResult:
    # JoinRoomResult
    # Ok	1	入場OK
    # RoomFull	2	満員
    # Disbanded	3	解散済み
    # OtherError	4	その他エラー

    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return JoinRoomResult.OtherError
        return _join_room(conn, room_id=room_id, user_id=user.id, difficulty=difficulty)


def _wait_room(
    conn: Connection, user_id: int, room_id: int
) -> tuple[WaitRoomStatus, list[RoomUser]]:
    # select * from room_member inner join user on room_member.user_id=user.id left outer join (select owner_id from room) as room on room_member.user_id=room.owner_id;

    wait_room_status: WaitRoomStatus = WaitRoomStatus.Waiting
    room_users: list[RoomUser] = []

    # リクエストされた部屋が存在しているか確認します
    res = conn.execute(
        text("SELECT * FROM room WHERE id=:room_id"),
        parameters={"room_id": room_id},
    )
    try:
        res.one()
    except Exception as e:
        print(e)
        wait_room_status = WaitRoomStatus.Dissolution
        return wait_room_status, room_users

    # 自分の部屋がゲーム開始になっているか (room.is_game_started=1) 確認します。
    # このパラメータは、ホストがライブ開始をリクエストすると1になります。
    # もしこのパラメータ自体を確認できない場合は、部屋が解散されたとみなして、処理します。
    res = conn.execute(
        text("SELECT is_game_started FROM room WHERE id=:room_id"),
        parameters={"room_id": room_id},
    )
    try:
        status = res.one()
        if status.is_game_started == 1:
            wait_room_status = WaitRoomStatus.LiveStart
    except Exception as e:
        print(e)
        wait_room_status = WaitRoomStatus.Dissolution
        return wait_room_status, room_users

    # 指定された部屋にいるメンバー一覧を取得します。
    results = conn.execute(
        text(
            "SELECT "
            "user_id, "
            "name, "
            "leader_card_id, "
            "select_difficulty, "
            "IF(user_id=:user_id, 1, 0) as is_me, "
            "IF(ISNULL(owner_id), 0, 1) as is_host "
            "FROM room_member "
            "INNER JOIN user ON room_member.user_id=user.id "
            "LEFT OUTER JOIN (SELECT * FROM room WHERE id=:room_id) AS room ON room_member.user_id=room.owner_id "
            "WHERE room_id=:room_id"
        ),
        parameters={"user_id": user_id, "room_id": room_id},
    )

    for result in results:
        room_user = RoomUser.model_validate(result, from_attributes=True)
        room_users.append(room_user)

    return wait_room_status, room_users


def wait_room(token: str, room_id: int) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        return _wait_room(conn, user.id, room_id)


def _start_room(conn: Connection, room_id: int) -> None:
    conn.execute(
        text("UPDATE `room` " "SET is_game_started=1 " "WHERE `id`=:room_id"),
        parameters={"room_id": room_id},
    )


def start_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        _start_room(conn, room_id)


def _end_room(
    conn: Connection,
    user_id: int,
    room_id: int,
    score: int,
    n_perfects: int,
    n_greats: int,
    n_goods: int,
    n_bads: int,
    n_misses: int,
) -> None:
    conn.execute(
        text(
            "UPDATE `room_member` "
            "SET "
            "is_game_finished=1, "
            "latest_score=:latest_score, "
            "latest_num_perfect=:n_perfects, "
            "latest_num_great=:n_greats, "
            "latest_num_good=:n_goods, "
            "latest_num_bad=:n_bads, "
            "latest_num_miss=:n_misses "
            "WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        parameters={
            "user_id": user_id,
            "room_id": room_id,
            "latest_score": score,
            "n_perfects": n_perfects,
            "n_greats": n_greats,
            "n_goods": n_goods,
            "n_bads": n_bads,
            "n_misses": n_misses,
        },
    )


def end_room(
    token: str,
    room_id: int,
    score: int,
    n_perfects: int,
    n_greats: int,
    n_goods: int,
    n_bads: int,
    n_misses: int,
) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        _end_room(
            conn=conn,
            user_id=user.id,
            room_id=room_id,
            score=score,
            n_perfects=n_perfects,
            n_greats=n_greats,
            n_goods=n_goods,
            n_bads=n_bads,
            n_misses=n_misses,
        )


def _result_room(conn: Connection, room_id: int) -> list[ResultUser]:
    result_users: list[ResultUser] = []

    # まだプレイ中のユーザ数を確認します。
    # 1人以上いた場合は、空のリストを返します。
    res = conn.execute(
        text(
            "SELECT SUM(1-is_game_finished) AS unfinished_users "
            "FROM room_member "
            "WHERE room_id=:room_id"
        ),
        parameters={"room_id": room_id},
    )
    try:
        status = res.one()
        if status.unfinished_users > 0:
            return []
    except Exception as e:
        print(e)
        return []

    results = conn.execute(
        text(
            "SELECT user_id, latest_score, "
            "latest_num_perfect, latest_num_great, latest_num_good, "
            "latest_num_bad, latest_num_miss "
            "FROM room_member "
            "WHERE room_id=:room_id"
        ),
        parameters={"room_id": room_id},
    )

    for result in results:
        result_user = ResultUser(
            user_id=result.user_id,
            score=result.latest_score,
            judge_count_list=[
                result.latest_num_perfect,
                result.latest_num_great,
                result.latest_num_good,
                result.latest_num_bad,
                result.latest_num_miss,
            ],
        )
        result_users.append(result_user)

    return result_users


def result_room(token: str, room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        return _result_room(conn, room_id=room_id)


def _leave_room(conn: Connection, room_id: int, user_id: int) -> None:
    conn.execute(
        text("DELETE FROM `room_member` WHERE room_id=:room_id AND user_id=:user_id"),
        parameters={"room_id": room_id, "user_id": user_id},
    )
    conn.execute(
        text("DELETE FROM `room` WHERE owner_id=:user_id"),
        parameters={"user_id": user_id},
    )


def leave_room(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        _leave_room(conn, room_id=room_id, user_id=user.id)
