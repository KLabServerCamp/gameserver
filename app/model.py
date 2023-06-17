from enum import IntEnum, Enum

from typing import Optional
from pydantic import BaseModel
from sqlalchemy import text, Connection
from sqlalchemy.exc import NoResultFound


class Lock(Enum):
    NONE = ""
    LOCK_IN_SHARE_MODE = " LOCK IN SHARE MODE "
    FOR_UPDATE = " FOR UPDATE "


# User ----------------------------------
class SafeUser(BaseModel):
    """token を含まないUser"""

    id: int
    name: str
    leader_card_id: int

    # SafeUser.from_orm(row) できるようにする
    class Config:
        orm_mode = True


def create_user(
        conn: Connection, token: str, name: str, leader_card_id: int) -> int:
    return conn.execute(
        text(
            "INSERT INTO `user` (name, token, leader_card_id)"
            " VALUES (:name, :token, :leader_card_id)"
        ),
        {"name": name, "token": token, "leader_card_id": leader_card_id},
    ).lastrowid


def update_user(
        conn: Connection, id: int, name: str, leader_card_id: int) -> None:
    conn.execute(
        text(
            "UPDATE user"
            " SET name=:name, leader_card_id=:leader_card_id "
            " WHERE id=:id"
        ),
        {"id": id, "name": name, "leader_card_id": leader_card_id},
    )


def get_user_by_token(conn: Connection, token: str) -> SafeUser | None:
    result = conn.execute(
        text("SELECT * FROM `user` WHERE `token`=:token"),
        {"token": token},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return SafeUser.from_orm(row)


# Room -------------------------------------------------------
class WaitRoomStatus(IntEnum):
    WAITING = 1
    LIVE_START = 2
    DISSOLUTION = 3


class Room(BaseModel):
    id: int
    live_id: int
    host_user_id: int
    status: WaitRoomStatus

    class Config:
        orm_mode = True


def create_room(conn: Connection, live_id: int, host_user_id: int) -> int:
    return conn.execute(
        text(
            "INSERT INTO `room` (`live_id`, `host_user_id`, `status`)"
            " VALUES (:live_id, :host_user_id, :status)"
        ),
        {
            "live_id": live_id,
            "host_user_id": host_user_id,
            "status": WaitRoomStatus.WAITING.value,
        },
    ).lastrowid


def get_room(
        conn: Connection, room_id: int, lock: Lock = Lock.NONE) -> Room | None:
    result = conn.execute(
        text("SELECT * FROM `room` WHERE id=:id" + lock.value),
        {"id": room_id},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return Room.from_orm(row)


def update_room(
        conn: Connection,
        room_id: int, live_id: int, host_user_id: int, status: WaitRoomStatus):
    conn.execute(
        text(
            "UPDATE `room`"
            " SET live_id=:live_id, host_user_id=:host_user_id, status=:status"
            " WHERE id=:id"
        ),
        {
            "id": room_id,
            "live_id": live_id,
            "host_user_id": host_user_id,
            "status": status.value
        },
    )


class RoomWithMembersNum(Room):
    members_num: int


# 仕様上 COALESCE はいらないが備忘録も兼ねて
def get_room_with_members_num_list_by_live_id(
        conn: Connection, live_id: int) -> list[RoomWithMembersNum]:
    result = conn.execute(
        text(
            "SELECT *, COALESCE(t2.count, 0) as members_num"
            " FROM `room`"
            " LEFT OUTER JOIN"
            " (SELECT `room_id`, COUNT(*) AS count"
            "  FROM `room_member` GROUP BY `room_id`) as `t2`"
            " ON id = room_id"
            " WHERE live_id=:live_id"
        ),
        {"live_id": live_id},
    )
    return [RoomWithMembersNum.from_orm(row) for row in result]


def delete_room(conn: Connection, id: int) -> None:
    conn.execute(
        text("DELETE FROM `room` WHERE id=:id"),
        {"id": id},
    )


# Room Member ----------------------------------------------------
class LiveDifficulty(IntEnum):
    NORMAL = 1
    HARD = 2


class RoomMember(BaseModel):
    room_id: int
    user_id: int
    live_difficulty: LiveDifficulty
    score: Optional[int]
    judge: Optional[str]

    class Config:
        orm_mode = True


def create_room_member(
        conn: Connection,
        room_id: int, user_id: int, live_difficulty: LiveDifficulty) -> None:
    conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, live_difficulty)"
            " VALUES (:room_id, :user_id, :live_difficulty)"
        ),
        {
            "room_id": room_id,
            "user_id": user_id,
            "live_difficulty": live_difficulty.value,
        }
    )


def get_room_member(
        conn: Connection, room_id: int, user_id: int) -> RoomMember | None:
    result = conn.execute(
        text(
            "SELECT * From `room_member`"
            " WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        {"room_id": room_id, "user_id": user_id},
    )
    try:
        row = result.one()
    except NoResultFound:
        return None
    return RoomMember.from_orm(row)


def get_room_member_list(conn: Connection, room_id: int) -> list[RoomMember]:
    rows = conn.execute(
        text(
            "SELECT * FROM `room_member`"
            " WHERE room_id=:room_id"
        ),
        {"room_id": room_id},
    )
    return [RoomMember.from_orm(row) for row in rows]


def update_room_member(
        conn: Connection, room_id: int, user_id: int,
        live_difficulty: LiveDifficulty,
        score: int | None, judge: str | None):
    conn.execute(
        text(
            "UPDATE `room_member`"
            " SET live_difficulty=:live_difficulty, score=:score, judge=:judge"
            " WHERE room_id=:room_id AND user_id=:user_id"
        ),
        {
            "room_id": room_id,
            "user_id": user_id,
            "live_difficulty": live_difficulty.value,
            "score": score,
            "judge": judge,
        },
    )


def delete_room_member(conn: Connection, room_id: int, user_id: int):
    conn.execute(
        text(
            "DELETE FROM `room_member`"
            " WHERE room_id=:room_id AND user_id=:user_id"
        ),
        {"room_id": room_id, "user_id": user_id},
    )


class UserOrRoomMember(SafeUser, RoomMember):
    class Config:
        orm_mode = True


def get_user_or_room_member_list(
        conn: Connection, room_id: int) -> list[UserOrRoomMember]:
    rows = conn.execute(
        text(
            "SELECT u.*, rm.* FROM `room_member` as rm"
            " JOIN `user` as u"
            " ON user_id=u.id"
            " WHERE room_id=:room_id"
        ),
        {"room_id": room_id},
    ).fetchall()
    return [UserOrRoomMember.from_orm(row) for row in rows]


# group by と count を使った方が賢いが、汎用性を求めてしまった
# def get_room_list_by_live_id(live_id: int) -> list[Room]:
#    with engine.begin() as conn:
#        result = conn.execute(
#            text(
#                "SELECT *"
#                " FROM `room`"
#                " LEFT JOIN `room_member`"
#                " ON room.id = room_member.room_id"
#                " WHERE `live_id`=:live_id"
#            ),
#            {"live_id": live_id},
#        )
#        rows = result.all()
#        rooms = {}
#        members = defaultdict(lambda: [])
#        for r in rows:
#            if (r.id not in rooms):
#                rooms[r.id] = dict(r._mapping)
#            members[r.id].append(RoomMember.from_orm(r))
#        return [Room.parse_obj(
#            {**r, "members": members[r["id"]]}
#            ) for r in rooms.values()]
