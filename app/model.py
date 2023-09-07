import uuid
from enum import IntEnum

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

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


class RoomStatus(IntEnum):
    Waiting = 1
    LiveStart = 2
    Dismissed = 3


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

        _set_room_host_id(conn, room_id, user.id)
        _set_room_status(conn, room_id, RoomStatus.Waiting)

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
    lid = req.live_id
    reslist = []
    with engine.begin() as conn:
        result = conn.execute(text(
            "SELECT `id`, `live_id` FROM `room` WHERE `live_id`=:live_id"
            ),
            {"live_id": lid}
        ) if lid != 0 else conn.execute(text(
            "SELECT `id`, `live_id` FROM `room`"
        ))
        rows = result.fetchall()
# 関連: https://github.com/KLabServerCamp/gameserver/pull/37/files/042444c606e725073901d2c90358d1665b851d59
# "N+1" というやつがあるらしい クエリはちまちま投げず一気に投げるべき的な？
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


# TODO: ここから上も書き直したい


class JoinRoomResult(IntEnum):
    Ok = 1
    RoomFull = 2
    Dismissed = 3
    OtherError = 4


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


# 例外メッセージに DB 内の情報を載せるのめちゃくちゃ酷い気がするが、
# 公開環境じゃないのでしょうがない
class DBDuplicateEntriesException(Exception):
    pass


# ユーザの存在確認 (重複確認込み)
def _check_user_existence(conn, user_id) -> bool:
    result = conn.execute(text(
        "SELECT * FROM `user` WHERE `id`=:uid"
        ),
        {"uid": user_id}
    )
    try:
        result.one()
    except NoResultFound:
        print("no such user, uid=", user_id)
        return False
    except MultipleResultsFound:
        raise DBDuplicateEntriesException("in user: uid={}".format(user_id))
    return True


# ユーザのいる部屋 ID 取得 (部屋にいない場合 -1)
def _get_user_room_id(conn, user_id):
    assert _check_user_existence(conn, user_id)
    result = conn.execute(text(
        "SELECT * FROM `room_member` WHERE `user_id`=:uid"
        ),
        {"uid": user_id}
    )
    rows = result.fetchall()
    if len(rows) > 1:
        raise DBDuplicateEntriesException(
            "in room_member: uid={}".format(user_id)
        )

    if len(rows) == 0:
        return -1

    return rows[0].room_id


# ユーザがいずれかの部屋にいるかどうか
def _is_user_in_room(conn, user_id) -> bool:
    return _get_user_room_id(conn, user_id) == -1


# ユーザが指定の部屋にいるかどうか
def _is_user_in_the_room(conn, user_id, room_id) -> bool:
    return _get_user_room_id(conn, user_id) == room_id


# 部屋の存在確認 (重複確認込み)
def _check_room_existence(conn, room_id) -> bool:
    result = conn.execute(text(
        "SELECT * FROM `room` WHERE `id`=:rid"
        ),
        {"rid": room_id}
    )
    try:
        result.one()
    except NoResultFound:
        print("no such room, rid=", room_id)
        return False
    except MultipleResultsFound:
        print("more than one rooms, rid=", room_id)
        return False
    return True


# 部屋にいるユーザ (リスト)
def _get_room_users(conn, room_id):
    assert _check_room_existence(conn, room_id)
    result = conn.execute(text(
        "SELECT * FROM `room_member` WHERE `room_id`=:rid"
        ),
        {"rid": room_id}
    )
    return result.fetchall()


# 部屋にいる人数
def _get_room_users_count(conn, room_id) -> int:
    return len(_get_room_users(conn, room_id))


# 満員かどうか
def _is_room_full(conn, room_id) -> bool:
    return _get_room_users_count(conn, room_id) >= MAX_USER_COUNT


# ルーム部屋主取得
def _get_room_host_id(conn, room_id) -> int:
    assert _check_room_existence(conn, room_id)
    return conn.execute(text(
        "SELECT `owner_id` FROM `room` WHERE `id`=:rid"
        ),
        {"rid": room_id}
    ).fetchall()[0].owner_id


# ルーム部屋主変更
def _set_room_host_id(conn, room_id, new_uid):
    # 部屋外の人が部屋主になってどーする
    assert _is_user_in_the_room(conn, new_uid, room_id)
    conn.execute(text(
        "UPDATE `room` SET `owner_id`=:nuid WHERE `id`=:rid"
        ),
        {"nuid": new_uid, "rid": room_id}
    )


# ルームステータス取得
def _get_room_status(conn, room_id) -> RoomStatus:
    assert _check_room_existence(conn, room_id)
    return conn.execute(text(
        "SELECT `status` FROM `room` WHERE `id`=:rid"
        ),
        {"rid": room_id}
    ).fetchall()[0].status


# ルームステータス変更
def _set_room_status(conn, room_id, new_status: RoomStatus):
    assert _check_room_existence(conn, room_id)
    conn.execute(text(
        "UPDATE `room` SET `status`=:ns WHERE `id`=:rid"
        ),
        {"ns": int(new_status), "rid": room_id}
    )


# ルーム入室
def _add_room_member(conn, room_id, user_id, diff: LiveDifficulty):
    assert not _is_user_in_the_room(conn, user_id, room_id)
    conn.execute(text(
        "INSERT INTO `room_member` (`room_id`, `user_id`, `difficulty`) "
        "VALUES (:room_id, :user_id, :difficulty)"),
        {
            "room_id": room_id,
            "user_id": user_id,
            "difficulty": int(diff)
        }
    )


# ルーム退室
def _del_room_member(conn, room_id, user_id):
    assert _is_user_in_the_room(conn, user_id, room_id)
    conn.execute(text(
        "DELETE FROM `room_member` "
        "WHERE `room_id`=:room_id AND `user_id`=:user_id"),
        {
            "room_id": room_id,
            "user_id": user_id,
        }
    )


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
    if _get_user_room_id(conn, user.id) >= 0:
        print("you are already in another room. uid=", user.id)
        return RoomJoinResponse(join_room_result=JoinRoomResult.OtherError)

    # [確認] 参加先の部屋が存在すること (OtherError)
    if not _check_room_existence(conn, room_id):
        return RoomJoinResponse(join_room_result=JoinRoomResult.OtherError)

    # [確認] 参加先の部屋に空席があること (RoomFull)
    if _is_room_full(conn, room_id):
        return RoomJoinResponse(join_room_result=JoinRoomResult.RoomFull)

    # [要検討] ライブ開始済の部屋には参加できてよいか？

    # 参加可能
    _add_room_member(conn, room_id, user.id, difficulty)

    # 空の部屋でホスト不在の部屋の場合は新たに設定
    if not _get_room_host_id(conn, room_id) >= 0:
        _set_room_host_id(conn, room_id, user.id)

    # 解散状態を解除
    if _get_room_status(conn, room_id) == RoomStatus.Dismissed:
        _set_room_status(conn, room_id, RoomStatus.Waiting)

    return RoomJoinResponse(join_room_result=JoinRoomResult.Ok)


# 仕様に載ってないので、もしかすると単一の変数のときは構造体の定義が要らない
# いい感じの書き方がある？ (直に room_id を渡すと JSON にならないので一旦このまま)
class RoomLeaveRequest(BaseModel):
    room_id: int


def leave_room(token: str, req: RoomLeaveRequest) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return InvalidToken
        uid = user.id
        rid = req.room_id
        
        # そもそも部屋にいないので退出出来ない場合
        if not _is_user_in_the_room(conn, uid, rid):
            print("you are not in the room, uid={}, rid={}".format(uid, rid))
            return

        hid = _get_room_host_id(conn, rid)

        # 部屋主退出
        if uid == hid:
            other_user_list = _get_room_users(conn, rid)
            # ぼっち脱退 -> 部屋 0 人 -> dismissed (ステータス使い方あってる？)
            if len(other_user_list) == 1:
                _set_room_host_id(conn, rid, -1)
                _set_room_status(conn, rid, RoomStatus.Dismissed)
            else:   # 次の部屋主を雑に決める
                for other in other_user_list:
                    if other.user_id != uid:
                        _set_room_host_id(conn, rid, other.user_id)
                        break

        # レコード削除 (room_member)
        _del_room_member(conn, rid, uid)
