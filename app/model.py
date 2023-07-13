import uuid
from enum import IntEnum
from typing import Tuple

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound

from .db import engine


class StrictBase(BaseModel):
    """DBを利用するためのBaseModel"""

    # strictモードを有効にする
    model_config = ConfigDict(strict=True)


class InvalidToken(Exception):
    """指定されたtokenが不正だったときに投げるエラー"""


class SafeUser(StrictBase):
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
    return SafeUser.model_validate(row, from_attributes=True)


def get_user_by_token(token: str) -> SafeUser | None:
    with engine.begin() as conn:
        return _get_user_by_token(conn, token)


def _update_user(conn, token: str, name: str, leader_card_id: int) -> None:
    conn.execute(
        text(
            "UPDATE `user`"
            " SET name=:name, leader_card_id=:leader_card_id"
            " WHERE token=:token"
        ),
        {"name": name, "leader_card_id": leader_card_id, "token": token},
    )


def update_user(token: str, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        # TODO: 実装
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        _update_user(conn, token, name, leader_card_id)


# IntEnum の使い方の例
class LiveDifficulty(IntEnum):
    """難易度"""

    normal = 1
    hard = 2


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(StrictBase):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(StrictBase):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(StrictBase):
    user_id: int
    judge_count_list: list[int]
    score: int


def _create_room(conn, live_id: int, difficulty: LiveDifficulty, user: SafeUser) -> int:
    # 作成
    result = conn.execute(
        text(
            "INSERT INTO `room` (live_id, owner_id, status) "
            "VALUES (:live_id, :owner_id, :status)"
        ),
        {
            "live_id": live_id,
            "owner_id": user.id,
            "status": WaitRoomStatus.Waiting.value,
        },
    )

    # IDを取りたい (https://github.com/KLabServerCamp/gameserver/pull/35#discussion_r1260932496)
    room_id = result.lastrowid

    # UserをRoomに追加する
    conn.execute(
        text(
            "INSERT INTO `room_member` (room_id, user_id, select_difficulty) "
            "VALUES (:room_id, :user_id, :select_difficulty)"
        ),
        {
            "room_id": room_id,
            "user_id": user.id,
            "select_difficulty": difficulty,
        },
    )

    return room_id


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken
        # TODO: 実装
        room_id: int = _create_room(
            conn=conn,
            live_id=live_id,
            difficulty=difficulty,
            user=user,
        )
        print("ROOOM:", room_id)
        return room_id


def _get_room(conn, row) -> RoomInfo:
    room = RoomInfo(
        room_id=row.room_id,
        live_id=row.live_id,
        joined_user_count=row.juc,
        max_user_count=4,
    )
    return room


def _get_room_list(conn, live_id: int) -> list[RoomInfo]:
    # WaitingRoomStatus.WaitingなRoomのみをSELECT
    # https://github.com/KLabServerCamp/gameserver/pull/35#discussion_r1260935742
    if live_id == 0:
        result = conn.execute(
            text(
                "SELECT `r`.*, count(`rm`.`room_id`) AS juc"
                " FROM `room` AS r"
                " JOIN `room_member` AS rm"
                " ON `r`.`room_id`=`rm`.`room_id`"
                " WHERE `r`.`status`=:status"
                " GROUP BY `r`.`room_id`"
            ),
            {"status": WaitRoomStatus.Waiting.value},
        )
    else:
        result = conn.execute(
            text(
                "SELECT `r`.*, count(`rm`.`room_id`) AS juc"
                " FROM `room` AS r"
                " JOIN `room_member` AS rm"
                " ON `r`.`room_id`=`rm`.`room_id`"
                " WHERE `r`.`live_id`=:live_id"
                " AND `r`.`status`=:status"
                " GROUP BY `r`.`room_id`"
            ),
            {"live_id": live_id, "status": WaitRoomStatus.Waiting.value},
        )

    rows = result.all()
    room_list = []

    # N+1をしないように上のSQLを修正
    # https://github.com/KLabServerCamp/gameserver/pull/35#discussion_r1260934358
    for row in rows:
        room = _get_room(conn, row)
        room_list.append(room)

    return room_list


def get_room_list(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        room_list = _get_room_list(conn, live_id=live_id)
        print("Room_List: " + f"{room_list}")
        return room_list


def check_room_status(conn, room_id: int) -> WaitRoomStatus:
    result = conn.execute(
        text("SELECT `status` FROM `room`" " WHERE `room_id`=:room_id" " FOR UPDATE"),
        {"room_id": room_id},
    )

    # もし見つからなければ、解散されたことにする
    try:
        status = result.one().status
    except NoResultFound:
        return WaitRoomStatus.Dissolution

    return status


def _join_room(
    conn, room_id: int, difficulty: LiveDifficulty, user: SafeUser
) -> JoinRoomResult:
    # userをinsert?

    result = conn.execute(
        text(
            "SELECT `user_id` FROM `room_member`" " WHERE `room_id`=:room_id FOR UPDATE"
        ),
        {"room_id": room_id},
    )

    if len(result.all()) >= 4:
        return JoinRoomResult.RoomFull

    result = conn.execute(
        text(
            "INSERT INTO `room_member`  (room_id, user_id, select_difficulty)"
            " VALUES (:room_id, :user_id, :difficulty)"
        ),
        {"room_id": room_id, "user_id": user.id, "difficulty": difficulty},
    )

    return JoinRoomResult.Ok


def join_room(token: str, room_id: int, difficulty: LiveDifficulty) -> JoinRoomResult:
    with engine.begin() as conn:
        status: WaitRoomStatus = check_room_status(conn, room_id=room_id)

        if status == WaitRoomStatus.Dissolution:
            return JoinRoomResult.Disbanded

        user = _get_user_by_token(conn=conn, token=token)
        if user is None:
            return JoinRoomResult.OtherError

        if (
            conn.execute(
                text("SELECT `owner_id` FROM `room` WHERE `room_id`=:room_id"),
                {"room_id": room_id},
            )
            .one()
            .owner_id
            == user.id
        ):
            return JoinRoomResult.OtherError

        return _join_room(conn, room_id=room_id, difficulty=difficulty, user=user)


def get_room_user(conn, user: SafeUser, room_id: int) -> list[RoomUser]:
    result = conn.execute(
        text(
            "SELECT `u`.*, `rm`.`select_difficulty`, `r`.`owner_id` "
            "FROM `user` as `u` "
            "JOIN `room_member` as `rm` "
            "ON u.id=rm.user_id "
            "JOIN `room` as `r` "
            "ON r.room_id=rm.room_id "
            "WHERE `rm`.`room_id`=:room_id"
        ),
        {"room_id": room_id},
    )

    try:
        rows = result.all()
    except NoResultFound:
        return []

    room_user_list: RoomUser = []
    for row in rows:
        print("WAIT ROW: ", row)
        room_user = RoomUser(
            user_id=user.id,
            name=row.name,
            leader_card_id=row.leader_card_id,
            select_difficulty=LiveDifficulty(row.select_difficulty),
            is_me=True if row.id == user.id else False,
            is_host=True if row.owner_id == row.id else False,
        )
        room_user_list.append(room_user)
    print(room_user_list)
    return room_user_list


def _room_wait(
    conn, user: SafeUser, room_id: int
) -> tuple[WaitRoomStatus, list[RoomUser]]:
    status = check_room_status(conn, room_id=room_id)
    member = get_room_user(conn, user, room_id=room_id)

    return (status, member)


def room_wait(token: str, room_id: int) -> tuple[WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token=token)
        if user is None:
            raise InvalidToken
        return _room_wait(conn, user=user, room_id=room_id)


def _room_start(conn, user: SafeUser, room_id: int):
    # 部屋のオーナーなら部屋のステータスを更新する
    conn.execute(
        text("UPDATE `room`" " SET `status`=:status" " WHERE `owner_id`=:user_id"),
        {"status": WaitRoomStatus.LiveStart.value, "user_id": user.id},
    )


def room_start(token: str, room_id: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token=token)
        if user is None:
            raise InvalidToken

        _room_start(conn, user, room_id=room_id)


def _room_end(
    conn, user: SafeUser, room_id: int, judge_count_list: list[int], score: int
) -> None:
    # room_member にscoreなどを保存する
    conn.execute(
        text(
            "UPDATE `room_member`"
            "SET "
            "`score`=:score, "
            "`judge`=:judge "
            " WHERE `room_id`=:room_id"
            " AND `user_id`=:user_id"
        ),
        {
            "score": score,
            "judge": ",".join(map(str, judge_count_list)),
            "room_id": room_id,
            "user_id": user.id,
        },
    )


def room_end(token: str, room_id: int, judge_count_list: list[int], score: int) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token=token)
        if user is None:
            raise InvalidToken

        _room_end(
            conn=conn,
            user=user,
            room_id=room_id,
            judge_count_list=judge_count_list,
            score=score,
        )


def _room_result(conn, room_id) -> list[ResultUser]:
    # room_memberからもろもろ持ってくる

    result = conn.execute(
        text(
            "SELECT "
            "`user_id`, `judge`, `score`"
            " FROM `room_member`"
            " WHERE `room_id`=:room_id"
        ),
        {
            "room_id": room_id,
        },
    )

    result_user_list: list[ResultUser] = []
    rows = result.all()

    for row in rows:
        score = row.score
        judge = row.judge
        if score is None:
            continue

        user = ResultUser(
            user_id=row.user_id,
            judge_count_list=list(map(int, judge.split(","))),
            score=score,
        )
        result_user_list.append(user)

    if len(result_user_list) < len(rows):
        return []
    else:
        return result_user_list


def _room_dissolution(conn, room_id):
    conn.execute(
        text("UPDATE `room`" " SET `status`=:status" " WHERE `room_id`=:room_id"),
        {"status": WaitRoomStatus.Dissolution.value, "room_id": room_id},
    )

    conn.execute(
        text("DELETE FROM `room`" " WHERE `room_id`=:room_id" " AND `status`=:status"),
        {
            "room_id": room_id,
            "status": WaitRoomStatus.Dissolution.value,
        },
    )

    conn.execute(
        text("DELETE FROM `room_member`" " WHERE `room_id`=:room_id"),
        {"room_id": room_id},
    )


def room_result(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        response = _room_result(conn, room_id=room_id)

    if len(response) != 0:
        with engine.begin() as conn:
            _room_dissolution(conn, room_id=room_id)

    return response


def _room_leave(conn, user: SafeUser, room_id: int):
    # User を退出させる
    conn.execute(
        text(
            "DELETE FROM `room_member`"
            " WHERE `room_id`=:room_id"
            " AND `user_id`=:user_id"
        ),
        {"room_id": room_id, "user_id": user.id},
    )

    # もしownerだったら部屋を解散状態にしてみる
    conn.execute(
        text(
            "UPDATE `room`"
            " SET `status`=:status"
            " WHERE room_id=:room_id AND `owner_id`=:user_id"
        ),
        {
            "status": WaitRoomStatus.Dissolution.value,
            "room_id": room_id,
            "user_id": user.id,
        },
    )

    # もしownerなら、部屋のメンバーを退出させる
    conn.execute(
        text(
            "DELETE `room`, `room_member`"
            " FROM `room`"
            " JOIN `room_member`"
            " ON `room`.`room_id`=:room_id"
            " AND `room_member`.`room_id`=:room_id"
            " WHERE `room`.`owner_id`=:user_id"
        ),
        {"room_id": room_id, "user_id": user.id},
    )


def room_leave(token: str, room_id: int):
    with engine.begin() as conn:
        user = _get_user_by_token(conn=conn, token=token)
        if user is None:
            raise InvalidToken
        _room_leave(conn, user=user, room_id=room_id)
