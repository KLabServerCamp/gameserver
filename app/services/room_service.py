from typing import Any

from sqlalchemy import Connection, text

from ..schemas.enums import JoinRoomResult, LiveDifficulty, WaitRoomStatus
from ..schemas.structures import ResultUser, RoomInfo, RoomUser


def create_room(
    conn: Connection,
    live_id: int,
    owner_id: int,
) -> int:
    result = conn.execute(
        text("INSERT INTO `room` (live_id, owner_id)" " VALUES (:live_id, :owner_id)"),
        {"live_id": live_id, "owner_id": owner_id},
    )
    return result.lastrowid


def get_room_list(conn: Connection, live_id: int) -> list[RoomInfo]:
    """
    入場可能なルーム一覧を取得

    Args:
        live_id (int): ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）

    Returns:
        room_info_list (list[RoomInfo]): 入場可能なルーム一覧
    """
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


def join_room(
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


def wait_room(
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


def start_room(conn: Connection, room_id: int) -> None:
    conn.execute(
        text("UPDATE `room` " "SET is_game_started=1 " "WHERE `id`=:room_id"),
        parameters={"room_id": room_id},
    )


def end_room(
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


def result_room(conn: Connection, room_id: int) -> list[ResultUser]:
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


def leave_room(conn: Connection, room_id: int, user_id: int) -> None:
    conn.execute(
        text("DELETE FROM `room_member` WHERE room_id=:room_id AND user_id=:user_id"),
        parameters={"room_id": room_id, "user_id": user_id},
    )


def disband_owned_room(conn: Connection, room_id: int, user_id: int) -> None:
    # 指定された部屋に参加しているメンバーを room_member から削除する（自分自身がオーナーの場合のみ）
    conn.execute(
        text(
            "DELETE member "
            "FROM room_member AS member "
            "INNER JOIN "
            "(SELECT * FROM room WHERE owner_id=:user_id AND id=:room_id) "
            "AS room "
            "ON room_id=room.id;"
        ),
        parameters={"room_id": room_id, "user_id": user_id},
    )
    # 指定された部屋を room から削除する（自分自身がオーナーの場合のみ）
    conn.execute(
        text("DELETE FROM `room` WHERE id=:room_id AND owner_id=:user_id"),
        parameters={"room_id": room_id, "user_id": user_id},
    )
