import uuid
from enum import IntEnum

from pydantic import BaseModel
from .db import engine
from . import model
import json


MAX_ROOM_MEMBER_COUNT = 4


def create_user(name: str, leader_card_id: int) -> str:
    # 重複の可能性を排除しない行儀の悪いコード
    token = str(uuid.uuid4())
    with engine.begin() as conn:
        id = model.create_user(conn, token, name, leader_card_id)
        print(f"create_user(): {id=}")
    return token


def get_user_by_token(token: str) -> model.SafeUser | None:
    with engine.begin() as conn:
        return model.get_user_by_token(conn, token)


def update_user(id: int, name: str, leader_card_id: int) -> None:
    with engine.begin() as conn:
        model.update_user(conn, id, name, leader_card_id)


#  room -------------------------------------------------------
class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count:	int


class JoinRoomResult(IntEnum):
    OK = 1
    ROOM_FULL = 2
    DISBANDED = 3
    OTHER_ERROR = 4


def create_room(
        live_id: int, host_user_id: int, difficulty: model.LiveDifficulty
        ) -> int:
    """部屋を作ってroom_idを返します"""
    with engine.begin() as conn:
        room_id = model.create_room(conn, live_id, host_user_id)
        model.create_room_member(conn, room_id, host_user_id, difficulty)
        return room_id


def get_room_info_list_by_live_id(live_id: int) -> list[RoomInfo]:
    with engine.begin() as conn:
        rooms = model.get_room_with_members_num_list_by_live_id(conn, live_id)
        return [RoomInfo(
            room_id=room.id,
            live_id=room.live_id,
            joined_user_count=room.members_num,
            max_user_count=MAX_ROOM_MEMBER_COUNT,
        ) for room in rooms]


def join_room(
  room_id: int,
  user_id: int, difficulty: model.LiveDifficulty) -> JoinRoomResult:
    with engine.begin() as conn:
        if model.get_room(conn, room_id, model.Lock.FOR_UPDATE) is None:
            return JoinRoomResult.Disbanded
        members = model.get_room_member_list(conn, room_id)
        if (user_id in [r.user_id for r in members]):
            return JoinRoomResult.OTHER_ERROR
        if (len(members) >= MAX_ROOM_MEMBER_COUNT):
            return JoinRoomResult.ROOM_FULL
        model.create_room_member(conn, room_id, user_id, difficulty)
        return JoinRoomResult.OK


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: model.LiveDifficulty
    is_me: bool
    is_host: bool


def wait_room(
        room_id: int,
        user_id: int) -> tuple[model.WaitRoomStatus, list[RoomUser]]:
    with engine.begin() as conn:
        room = model.get_room(conn, room_id)
        if room is None:
            return [model.WaitRoomStatus.DISSOLUTION, []]
        userOrRoomMembers = model.get_user_or_room_member_list(conn, room_id)
        members = [RoomUser(
                    user_id=u.user_id,
                    name=u.name,
                    leader_card_id=u.leader_card_id,
                    select_difficulty=u.live_difficulty,
                    is_me=user_id == u.user_id,
                    is_host=u.user_id == room.host_user_id,
                ) for u in userOrRoomMembers]
        return [room.status, members]


def start_room(room_id: int, user_id: int):
    with engine.begin() as conn:
        room = model.get_room(conn, room_id, model.Lock.FOR_UPDATE)
        if room is None:
            return
        if room.host_user_id != user_id:
            return
        model.update_room(
            conn, room.id, room.live_id, room.host_user_id,
            model.WaitRoomStatus.LIVE_START)


def end_room(
        room_id: int, user_id: int, score: int, judge_count_list: list[int]):
    with engine.begin() as conn:
        room_member = model.get_room_member(conn, room_id, user_id)
        if room_member is None:
            return
        model.update_room_member(
            conn,
            room_id, user_id,
            room_member.live_difficulty,
            score,
            json.dumps(judge_count_list),
        )


class ResultUser(BaseModel):
    id: int
    user_id: int
    judge_count_list: list[int]
    score: int


def result_room(room_id: int) -> list[ResultUser]:
    with engine.begin() as conn:
        members = model.get_room_member_list(conn, room_id)
        print(members)
        return [ResultUser(
            id=room_id,
            user_id=m.user_id,
            judge_count_list=eval(m.judge),
            score=m.score,
        ) for m in members if m.judge is not None]


def leave_room(room_id: int, user_id: int):
    with engine.begin() as conn:
        room = model.get_room(conn, room_id, model.Lock.FOR_UPDATE)
        if room is None:
            return

        model.delete_room_member(conn, room_id, user_id)
        members = model.get_room_member_list(conn, room_id)
        if len(members) < 1:
            model.delete_room()
        # ホストしか開始できないため、ホストが抜けたら部屋消滅
        if room.status == model.WaitRoomStatus.WAITING & \
                room.host_user_id == user_id:
            model.delete_room()
