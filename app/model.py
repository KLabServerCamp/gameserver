import json
import sys
import uuid
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import Connection, text
from sqlalchemy.exc import MultipleResultsFound, NoResultFound

from .db import engine
from .view import (
    LiveDifficulty,
    RoomInfo,
    JoinRoomResult,
    RoomUser,
    ResultUser,
    WaitRoomStatus,
    RoomEndRequest,
    RoomJoinRequest,
    RoomJoinResponse,
    RoomLeaveRequest,
    RoomResultRequest,
    RoomResultResponse,
    RoomStartRequest,
    RoomWaitRequest,
    RoomWaitResponse,
)

from datetime import datetime, timezone, timedelta

DEBUGPRINT = True


def debugprint(msg: str) -> None:
    if DEBUGPRINT:
        print(msg)


# 時刻取得 (aware: JST)
def get_current_time() -> datetime:
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))


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


def _get_user_by_token(conn: Connection, token: str) -> SafeUser | None:
    # TODO: 実装(わからなかったら資料を見ながら)
    result = conn.execute(
        text(
            "SELECT `id`, `name`, `leader_card_id` "
            "FROM `user` WHERE `token`=:token"
        ),
        {"token": token},
    )
    try:
        row = result.one()  # 結果の一意性確認
    except NoResultFound:
        return None
    return SafeUser.model_validate(
        row, from_attributes=True
    )  # row からオブジェクトへの変換 (pydantic)


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


def create_room(token: str, live_id: int, difficulty: LiveDifficulty):
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken(f"{token=}")
        # TODO: 実装

        if _is_user_in_room(conn, user.id):
            print(
                "Error: you are in the room, id="
                f"{_get_room_by_user_id(conn, user.id)}."
            )
            return -1

        room_id = _add_room_row(
            conn,
            _RoomRow(
                id=0,
                live_id=live_id,
                owner_id=user.id,
                status=WaitRoomStatus.Waiting
            ),
        )

        rjr = RoomJoinRequest(room_id=room_id, select_difficulty=difficulty)
        _join_room(conn, user, rjr)

        _set_room_host_id(conn, room_id, user.id)
        _set_room_status(conn, room_id, WaitRoomStatus.Waiting)

        return room_id


# 入室可能な最大人数
MAX_USER_COUNT = 4

# 部屋タイムアウト (寿命)
ROOM_TIMEOUT_MAX = 300

# 部屋タイムアウト (wait 無し)
ROOM_TIMEOUT_NOWAIT = 10

# リザルトタイムアウト
ROOM_TIMEOUT_RESULT = 10

# ポーリング間隔
INTV_POLLING = 2


# 部屋リスト & 古い部屋のクリーンアップ
def list_room(req) -> list[RoomInfo]:
    with engine.begin() as conn:
        # 部屋タイムアウト処理
        # wait: 300 秒経過 または Waiting かつ 10 秒経過
        # end: first_end が None でないかつ 30 秒経過
        waited = conn.execute(text(
            "SELECT `id` FROM "
            "(SELECT `id`, `status`, TIMESTAMPDIFF("
            "SECOND, `last_wait`, CURRENT_TIMESTAMP()"
            ") AS 'elapsed_w', TIMESTAMPDIFF("
            "SECOND, `first_end`, CURRENT_TIMESTAMP()"
            ") AS `elapsed_e` FROM `room`) AS `dummy` "
            "WHERE `elapsed_w` >= :thr_to_w_long OR "
            "`elapsed_w` >= :thr_to_w_short AND `status` = :status OR "
            "`elapsed_e` IS NOT NULL AND `elapsed_e` >= :thr_to_e"
            ),
            {
                "thr_to_w_long": ROOM_TIMEOUT_MAX,
                "thr_to_w_short": ROOM_TIMEOUT_NOWAIT,
                "status": int(WaitRoomStatus.Waiting),
                "thr_to_e": ROOM_TIMEOUT_RESULT + INTV_POLLING * 3
            }).fetchall()
        for room in waited:
            _del_room_row(conn, room.id, force=True)

        # 参加可能部屋リストアップ処理
        lid = req.live_id

        if lid != 0:  # 特定曲検索
            rows = conn.execute(
                text(
                    "SELECT `id`, `live_id` FROM `room` "
                    "WHERE `status`=:status AND `live_id`=:live_id"
                ),
                {"status": int(WaitRoomStatus.Waiting), "live_id": lid},
            ).fetchall()
        else:  # 全曲検索
            rows = conn.execute(
                text("SELECT `id`, `live_id` FROM `room` "
                     "WHERE `status`=:status"),
                {"status": int(WaitRoomStatus.Waiting)},
            ).fetchall()

        return [
            RoomInfo(
                room_id=row.id,
                live_id=row.live_id,
                joined_user_count=_get_room_users_count(conn, row.id),
                max_user_count=MAX_USER_COUNT,
            ) for row in rows
        ]


# TODO: ここから上も書き直したい


# 例外メッセージに DB 内の情報を載せるのめちゃくちゃ酷い気がするが、
# 公開環境じゃないのでしょうがない
class DBDuplicateEntriesException(Exception):
    pass


# ユーザの存在確認 (重複確認込み)
def _check_user_existence(conn: Connection, user_id) -> bool:
    debugprint(f"{sys._getframe().f_code.co_name}(), {user_id=}")
    result = conn.execute(
        text("SELECT * FROM `user` WHERE `id`=:uid"), {"uid": user_id}
    )
    try:
        result.one()
    except NoResultFound:
        return False
    except MultipleResultsFound as e:
        raise DBDuplicateEntriesException(f"in user: id={user_id}") from e
    return True


class _RoomRow(BaseModel):
    id: int
    live_id: int
    owner_id: Optional[int] = None
    status: WaitRoomStatus = WaitRoomStatus.Waiting
    players: int = 0
    last_wait: datetime = get_current_time()
    first_end: Optional[datetime] = None


def _get_room_row(conn: Connection, room_id) -> _RoomRow:
    debugprint(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    assert _check_room_existence(conn, room_id)
    result = conn.execute(
        text("SELECT * FROM `room` WHERE `id`=:rid"), {"rid": room_id}
    )
    room = result.first()
    return _RoomRow(
        id=room.id,
        live_id=room.live_id,
        owner_id=room.owner_id,
        status=room.status,
        players=room.players,
        last_wait=room.last_wait,
        first_end=room.first_end
    )


def _set_room_row(conn: Connection, new_data: _RoomRow):
    print(f"{sys._getframe().f_code.co_name}(), {new_data=}")
    room_id = new_data.id
    assert _check_room_existence(conn, room_id)
    conn.execute(
        text(
            "UPDATE `room` "
            "SET live_id=:live_id, owner_id=:owner_id, status=:status "
            "WHERE id=:id"
        ),
        {
            "id": new_data.id,
            "live_id": new_data.live_id,
            "owner_id": new_data.owner_id,
            "status": int(new_data.status),
        },
    )


# 部屋を新規作成し、その部屋の ID を返す
def _add_room_row(conn: Connection, new_data: _RoomRow):
    print(f"{sys._getframe().f_code.co_name}(), {new_data=}")
    if new_data.id != 0:
        print("You must set 'id' field to zero to create new room. "
              f"{new_data.id=}")
    return conn.execute(
        text(
            "INSERT INTO `room` (`live_id`, `owner_id`, `status`) "
            "VALUES (:live_id, :owner_id, :status)"
        ),
        {
            "live_id": new_data.live_id,
            "owner_id": new_data.owner_id,
            "status": int(new_data.status),
        },
    ).lastrowid


# 部屋削除 (空でない部屋は force=True でないと削除しない)
def _del_room_row(conn: Connection, room_id, *, force: bool = False):
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}, {force=}")
    if force:
        conn.execute(
            text("DELETE FROM `room_member` WHERE `room_id`=:rid"),
            {"rid": room_id}
        )
    elif _get_room_users_count(conn, room_id) != 0:
        print(f"You can't delete non-empty room. {room_id=}")
        return

    conn.execute(text("DELETE FROM `room` WHERE `id`=:rid"), {"rid": room_id})


class _RoomMemberRow(BaseModel):
    room_id: int
    user_id: int
    score: Optional[int] = None
    judge_count_list: Optional[list[int]] = None
    difficulty: LiveDifficulty


def _get_room_member_row(conn: Connection, room_id, user_id) \
        -> _RoomMemberRow | None:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}, {user_id=}")
    if not _is_user_in_the_room(conn, user_id, room_id):
        print(f"The user is not in the room. {room_id=}, {user_id=}")
        return
    return conn.execute(
        text("SELECT * FROM `room_member` "
             "WHERE `room_id`=:rid AND `user_id`=:uid"),
        {"rid": room_id, "uid": user_id},
    ).first()


def _get_room_members_rows(conn: Connection, room_id) -> list[_RoomMemberRow]:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    if not _check_room_existence(conn, room_id):
        print(f"No such room. {room_id=}")
        return []
    return conn.execute(
        text("SELECT * FROM `room_member` " "WHERE `room_id`=:rid"),
        {"rid": room_id}
    ).fetchall()


def _set_room_member_row(conn: Connection, new_data: _RoomMemberRow) -> None:
    print(f"{sys._getframe().f_code.co_name}(), {new_data=}")
    room_id = new_data.room_id
    user_id = new_data.user_id
    if not _is_user_in_the_room(conn, user_id, room_id):
        print(f"The user is not in the room. {room_id=}, {user_id=}")
        return
    conn.execute(
        text(
            "UPDATE `room_member` "
            "SET score=:score, "
            "difficulty=:difficulty, "
            "judge_count_list=:judge_count_list "
            "WHERE room_id=:rid AND user_id=:uid"
        ),
        {
            "rid": room_id,
            "uid": user_id,
            "score": new_data.score,
            "judge_count_list": json.dumps(new_data.judge_count_list),
            "difficulty": int(new_data.difficulty),
        },
    )


# ユーザのいる部屋 ID 取得 (部屋にいない場合 -1)
def _get_room_by_user_id(conn: Connection, user_id):
    print(f"{sys._getframe().f_code.co_name}(), {user_id=}")
    if not _check_user_existence(conn, user_id):
        print(f"No such user. {user_id=}")
        return -1

    result = conn.execute(
        text("SELECT * FROM `room_member` WHERE `user_id`=:uid"),
        {"uid": user_id}
    )
    rows = result.fetchall()
    if len(rows) > 1:
        raise DBDuplicateEntriesException(f"in room_member: {user_id=}")

    return rows[0].room_id if len(rows) > 0 else -1


# ユーザがいずれかの部屋にいるかどうか
def _is_user_in_room(conn: Connection, user_id) -> bool:
    print(f"{sys._getframe().f_code.co_name}(), {user_id=}")
    return _get_room_by_user_id(conn, user_id) != -1


# ユーザが指定の部屋にいるかどうか
def _is_user_in_the_room(conn: Connection, user_id, room_id) -> bool:
    print(f"{sys._getframe().f_code.co_name}(), {user_id=}, {room_id=}")
    return _get_room_by_user_id(conn, user_id) == room_id


# 部屋の存在確認 (重複確認込み)
def _check_room_existence(conn: Connection, room_id) -> bool:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    result = conn.execute(
        text("SELECT * FROM `room` WHERE `id`=:rid"), {"rid": room_id}
    )
    try:
        result.one()
    except NoResultFound:
        return False
    except MultipleResultsFound as e:
        raise DBDuplicateEntriesException(f"in room: {room_id=}") from e
    return True


class _RoomUserRow(BaseModel):
    user_id: int
    score: Optional[int] = None
    difficulty: LiveDifficulty
    name: str
    leader_card_id: int


# 部屋にいるユーザ (リスト)
def _get_users_by_room_id(conn: Connection, room_id) -> list[_RoomUserRow]:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    if not _check_room_existence(conn, room_id):
        print(f"No such room. {room_id=}")
        return []
    return conn.execute(
        text(
            "SELECT "
            "`room_member`.`user_id`, "
            "`room_member`.`score`, "
            "`room_member`.`difficulty`, "
            "`user`.`name`, "
            "`user`.`leader_card_id` "
            "FROM `room_member` "
            "INNER JOIN `user` ON `user_id`=`user`.`id` "
            "WHERE `room_id`=:rid"
        ),
        {"rid": room_id},
    ).fetchall()


# 部屋にいる人数
def _get_room_users_count(conn: Connection, room_id) -> int:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    if not _check_room_existence(conn, room_id):
        print(f"No such room. {room_id=}")
        return []
    return conn.execute(
        text("SELECT COUNT(1) FROM `room_member` WHERE `room_id`=:rid"),
        {"rid": room_id},
    ).first()[0]


# 満員かどうか
def _is_room_full(conn: Connection, room_id) -> bool:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    return _get_room_users_count(conn, room_id) >= MAX_USER_COUNT


# ルーム部屋主取得
def _get_room_host_id(conn: Connection, room_id) -> int:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    return _get_room_row(conn, room_id).owner_id


class NewHostNotInRoomException(Exception):
    pass


# ルーム部屋主変更
def _set_room_host_id(conn: Connection, room_id, new_uid):
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}, {new_uid=}")
    # 部屋外の人が部屋主になってどーする
    if not _is_user_in_the_room(conn, new_uid, room_id):
        raise NewHostNotInRoomException(f"{room_id=}, {new_uid=}")
    room = _get_room_row(conn, room_id)
    room.owner_id = new_uid
    _set_room_row(conn, room)


# 部屋主かどうか
def _is_user_host(conn: Connection, room_id, user_id) -> bool:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}, {user_id=}")
    return _get_room_host_id(conn, room_id) == user_id


# ルームステータス取得
def _get_room_status(conn: Connection, room_id) -> WaitRoomStatus | None:
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    if not _check_room_existence(conn, room_id):
        print(f"No such room. {room_id=}")
        return
    return _get_room_row(conn, room_id).status


# ルームステータス変更
def _set_room_status(conn: Connection, room_id, new_status: WaitRoomStatus):
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}, {new_status=}")
    if not _check_room_existence(conn, room_id):
        print(f"No such room. {room_id=}")
        return
    room = _get_room_row(conn, room_id)
    room.status = new_status
    _set_room_row(conn, room)


def _incr_room_players(conn: Connection, room_id):
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    conn.execute(
        text("UPDATE `room` SET `players`=`players`+1 WHERE `id`=:rid"),
        {"rid": room_id},
    )


def _decr_room_players(conn: Connection, room_id):
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}")
    # 0 になるならリザルト送信完了
    players = conn.execute(
        text("SELECT `players` FROM `room` WHERE `id`=:rid"), {"rid": room_id}
    ).first()[0]
    if players == 1:
        _set_room_status(conn, room_id, WaitRoomStatus.ResultSent)
        # [要検討] どこで部屋削除するか
        #   - ここで良い気もするが、果たして
        _del_room_row(conn, room_id, force=True)
    else:
        # デクリメント
        conn.execute(
            text("UPDATE `room` SET `players`=`players`-1 WHERE `id`=:rid"),
            {"rid": room_id},
        )


# ルーム入室
def _add_room_member(conn: Connection, room_id, user_id, diff: LiveDifficulty):
    print(f"{sys._getframe().f_code.co_name}(), "
          f"{room_id=}, {user_id=}, {diff=}")
    if _is_user_in_room(conn, user_id):
        print(f"Already in room. {user_id=}")
        return
    conn.execute(
        text(
            "INSERT INTO `room_member` (`room_id`, `user_id`, `difficulty`) "
            "VALUES (:room_id, :user_id, :difficulty)"
        ),
        {"room_id": room_id, "user_id": user_id, "difficulty": int(diff)},
    )

    # 参加人数インクリメント
    _incr_room_players(conn, room_id)


# ルーム退室
def _del_room_member(conn: Connection, room_id, user_id):
    print(f"{sys._getframe().f_code.co_name}(), {room_id=}, {user_id=}")
    if not _is_user_in_the_room(conn, user_id, room_id):
        print(f"The user is not in the room. {room_id=}, {user_id=}")
        return

    conn.execute(
        text(
            "DELETE FROM `room_member` "
            "WHERE `room_id`=:room_id AND `user_id`=:user_id"
        ),
        {
            "room_id": room_id,
            "user_id": user_id,
        },
    )

    # 参加人数デクリメント
    _decr_room_players(conn, room_id)


# 経過時間取得 (最初の end から)
def _get_elapsed_end_room(conn: Connection, room_id) -> int | None:
    first_end_naive: datetime = conn.execute(text(
        "SELECT `first_end` FROM `room` WHERE `id`=:rid"
    ), {"rid": room_id}).first()[0]
    if first_end_naive is None:
        return None
    first_end = first_end_naive.astimezone(timezone(timedelta(hours=9)))
    elapsed = get_current_time() - first_end
    return elapsed.seconds


# 時刻更新 (wait)
def _update_wait_room(conn: Connection, room_id):
    conn.execute(text(
        "UPDATE `room` SET `last_wait`=:time WHERE `id`=:rid"
    ), {
        "time": get_current_time(),
        "rid": room_id
    })


# 時刻更新 (end)
def _update_end_room(conn: Connection, room_id):
    conn.execute(text(
        "UPDATE `room` SET `first_end`=:time WHERE `id`=:rid"
    ), {
        "time": get_current_time(),
        "rid": room_id
    })


def join_room(token: str, req: RoomJoinRequest) -> RoomJoinResponse:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            raise InvalidToken(f"{token=}")
        return _join_room(conn, user, req)


def _join_room(conn: Connection, user, req: RoomJoinRequest):
    print(f"{sys._getframe().f_code.co_name}(), {user=}, {req=}")
    room_id = req.room_id
    difficulty = req.select_difficulty

    # [確認] 参加中の部屋が無いこと (OtherError)
    if _get_room_by_user_id(conn, user.id) >= 0:
        print("you are already in another room. uid=", user.id)
        return RoomJoinResponse(join_room_result=JoinRoomResult.OtherError)

    # [確認] 参加先の部屋が存在すること (OtherError)
    if not _check_room_existence(conn, room_id):
        return RoomJoinResponse(join_room_result=JoinRoomResult.Dismissed)

    # [確認] 参加先の部屋に空席があること (RoomFull)
    if _is_room_full(conn, room_id):
        return RoomJoinResponse(join_room_result=JoinRoomResult.RoomFull)

    # [要検討] ライブ開始済の部屋には参加できてよいか？
    #   - 多分良くない
    #   - /room/list のタイミングでは Waiting だった部屋が /room/join するまでに
    #       状態変化している場合のためにチェックはすべき
    if _get_room_status(conn, room_id) != WaitRoomStatus.Waiting:
        print("Live already ongoing or dismissed")
        return RoomJoinResponse(join_room_result=JoinRoomResult.LiveStarted)

    # 参加可能
    _add_room_member(conn, room_id, user.id, difficulty)

    # # 空の部屋でホスト不在の部屋の場合は新たに設定
    # if _get_room_host_id(conn, room_id) is None or -1:
    #     _set_room_host_id(conn, room_id, user.id)

    # # 解散状態を解除
    # if _get_room_status(conn, room_id) == WaitRoomStatus.Dismissed:
    #     _set_room_status(conn, room_id, WaitRoomStatus.Waiting)

    return RoomJoinResponse(join_room_result=JoinRoomResult.Ok)


def leave_room(token: str, req: RoomLeaveRequest) -> None:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return InvalidToken(f"{token=}")
        uid = user.id
        rid = req.room_id

        # そもそも部屋にいないので退出出来ない場合
        if not _is_user_in_the_room(conn, uid, rid):
            print(f"You are not in the room, {uid=}, {rid=}")
            return

        hid = _get_room_host_id(conn, rid)

        # 部屋主退出
        if uid == hid:
            other_user_list = _get_room_members_rows(conn, rid)
            # 次の部屋主を (いれば) 雑に決める
            if len(other_user_list) > 1:
                for other in other_user_list:
                    if other.user_id != uid:
                        _set_room_host_id(conn, rid, other.user_id)
                        break

        # レコード削除 (room_member)
        _del_room_member(conn, rid, uid)


def wait_room(token: str, req: RoomWaitRequest) -> RoomWaitResponse:
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return InvalidToken(f"{token=}")
        uid = user.id
        rid = req.room_id

        # [要検討] 部屋にいない人も wait レスポンスを受けられるべきか？
        #   - とくに弾かなければいけない理由は思いつかない
        #   - クライアント側で status だけ見てゲーム開始判定してるとかならマズイ
        # (以下実装案)
        # if not _is_user_in_the_room(conn, uid, rid):
        #     print("Unauthorized; you are not in the room.")
        #     print(f"{uid=}, {rid=}")
        #     return

        status = _get_room_status(conn, rid)
        members = _get_users_by_room_id(conn, rid)
        room_user_list = [
            RoomUser(
                user_id=member.user_id,
                name=member.name,
                leader_card_id=member.leader_card_id,
                select_difficulty=member.difficulty,
                is_me=member.user_id == uid,
                is_host=_is_user_host(conn, rid, member.user_id),
            )
            for member in members
        ]

        _update_wait_room(conn, rid)

        return RoomWaitResponse(status=status, room_user_list=room_user_list)


def start_room(token: str, req: RoomStartRequest):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return InvalidToken(f"{token=}")

        uid = user.id
        rid = req.room_id

        if not _check_room_existence(conn, rid):
            print(f"no such room, {rid=}")
            return

        if not _is_user_host(conn, rid, uid):
            print("Unauthorized; you are not the host of the room")
            print(f"{uid=}, {rid=}")
            return

        # [要検討] Waiting 以外の場合どうする？
        #   - もう始まってる場合の重複 start とか
        #   - 解散部屋での start とか
        if _get_room_status(conn, rid) != WaitRoomStatus.Waiting:
            print("Invalid; "
                  "the live is already ongoing or the room is dismissed")
            return

        # スコアの初期化
        members = _get_room_members_rows(conn, rid)
        for member in members:
            _set_room_member_row(
                conn,
                _RoomMemberRow(
                    room_id=member.room_id,
                    user_id=member.user_id,
                    difficulty=member.difficulty,
                ),
            )

        _set_room_status(conn, rid, WaitRoomStatus.LiveStart)
        return


def end_room(token: str, req: RoomEndRequest):
    with engine.begin() as conn:
        user = _get_user_by_token(conn, token)
        if user is None:
            return InvalidToken(f"{token=}")
        uid = user.id
        rid = req.room_id

        row = _get_room_member_row(conn, rid, uid)
        member = _RoomMemberRow(
            room_id=row.room_id,
            user_id=row.user_id,
            score=req.score,
            judge_count_list=req.judge_count_list,
            difficulty=row.difficulty,
        )

        if _get_elapsed_end_room(conn, rid) is None:
            _update_end_room(conn, rid)

        _set_room_member_row(conn, member)


def result_room(req: RoomResultRequest) -> RoomResultResponse:
    with engine.begin() as conn:
        room_id = req.room_id

        # 終了した人の数
        done = conn.execute(
            text(
                "SELECT COUNT(1) FROM `room_member` "
                "WHERE `room_id`=:rid AND `score` IS NOT NULL"
            ),
            {"rid": room_id},
        ).first()[0]

        # 空リストを返せばクライアントは待機
        ret = RoomResultResponse(result_user_list=[])

        # 部屋にいる人数分終了する (リザルトが出揃う) までは待機
        if _get_room_users_count(conn, room_id) > done \
                and _get_elapsed_end_room(conn, room_id) < ROOM_TIMEOUT_RESULT:
            return ret

        # 解散 (ライブ終了後、全員がリザルトを受け取るまで情報を保持するための状態)
        _set_room_status(conn, room_id, WaitRoomStatus.Dismissed)

        # 同室のスコアが NULL でない人のリザルトを集める
        rows = conn.execute(
            text(
                "SELECT `user_id`, `score`, `judge_count_list` "
                "FROM `room_member` LEFT JOIN `user` "
                "ON `room_member`.`user_id` = `user`.`id` "
                "WHERE `room_id`=:rid AND `score` IS NOT NULL"
            ),
            {"rid": room_id},
        ).fetchall()

        # result_user_list にリザルトを append
        for row in rows:
            ret.result_user_list.append(
                ResultUser(
                    user_id=row.user_id,
                    judge_count_list=json.loads(row.judge_count_list),
                    score=row.score,
                )
            )

        # リザルト送信前に未送信プレイヤー数 (players) をデクリメント
        _decr_room_players(conn, room_id)

        # 空でないリストを返すのでリザルトが表示される
        return ret
