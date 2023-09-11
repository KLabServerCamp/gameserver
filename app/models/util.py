from sqlalchemy import Connection, text

from app import schemas


def _get_user_by_token(conn: Connection, token: str) -> schemas.SafeUser | None:
    res = conn.execute(
        text("SELECT `id`, `name`, `leader_card_id` FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    row = res.one_or_none()
    if row is None:
        return None
    return schemas.SafeUser.model_validate(row, from_attributes=True)


def _get_room_users_from_room_id(conn: Connection, room_id: int) -> list:
    """room_id のルームに join しているプレイヤーを返す"""
    res = conn.execute(
        text("SELECT `user_id` FROM `room_member` WHERE `room_id`=:room_id"),
        {"room_id": room_id},
    )
    return res.all()


def _get_room_from_room_id(conn: Connection, room_id: int) -> schemas.SafeRoom | None:
    res = conn.execute(
        text(
            "SELECT `room_id`, `owner_id`, `live_id`, `max_user_count`, `status` FROM `room` WHERE `room_id`=:room_id"
        ),
        {"room_id": room_id},
    )
    room = res.one_or_none()
    if room is None:
        return None
    return schemas.SafeRoom.model_validate(room, from_attributes=True)


def _delete_user_from_room(conn: Connection, room_id: int, user_id: int) -> None:
    conn.execute(
        text(
            "DELETE FROM `room_member` WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        {"room_id": room_id, "user_id": user_id},
    )


def _delete_room(conn: Connection, room_id) -> None:
    # room.status を 3 に変更
    conn.execute(
        text("UPDATE `room` SET `status`=3 WHERE `room_id`=:room_id"),
        {"room_id": room_id},
    )


def _change_room_owner(
    conn: Connection, room_id: int, owner: schemas.SafeUser, users_in_room: list
) -> None:
    # オーナーではない適当なユーザ 1 人にだけ owner 権限を移譲する
    for user in users_in_room:
        if user.user_id == owner.id:
            continue
        conn.execute(
            text("UPDATE `room` SET `owner_id`=:new_user_id WHERE `room_id`=:room_id"),
            {"new_user_id": user.user_id, "room_id": room_id},
        )
        break


def _update_room_status(
    conn: Connection, room_id: int, status: schemas.WaitRoomStatus
) -> None:
    conn.execute(
        text("UPDATE `room` SET `status`=:status WHERE `room_id`=:room_id"),
        {"status": int(status), "room_id": room_id},
    )
