import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.config import MAX_USER_COUNT
from app.router.router import Empty

from app.router.user import get_auth_token


from app import model


router = APIRouter()
# FIXME: Status Code


# room APIs
class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: model.LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: model.LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


def _remove_already_joined_room_member(user_id):
    """Remove already joined room member"""
    pass
    try:
        joined = model.find_room_member_by_user_id(user_id)
    except Exception:
        raise ("見つからない")

    for m in joined:
        try:
            _pass_host_to_next_member(m.room_id, m.user_id)
            model.delete_room_member(m.user_id, m.room_id)
        except Exception:
            raise ("削除できない")


def _pass_host_to_next_member(room_id: int, user_id: int) -> None:
    """ホストを次のメンバーに渡す"""
    room_members = model.get_room_members(room_id)
    if room_members is None:
        return

    if len(room_members) == 1:
        return

    try:
        me = [m for m in room_members if m.user_id == user_id][0]
    except Exception:
        raise Exception("ユーザーが存在しません")

    if not me.is_host:
        return

    # ホストを委譲する
    remaining_members = [m for m in room_members if m.user_id != user_id]
    try:
        model.update_room_member_host(room_id, remaining_members[0].user_id, True)
    except Exception:
        raise Exception("ホストの委譲に失敗しました")


@router.post("/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """Create a new room"""

    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=401)

    try:
        _remove_already_joined_room_member(me.id)
    except Exception:
        raise HTTPException(status_code=500)

    try:
        id = model.create_room(me.id, req.live_id, req.select_difficulty)
    except Exception:
        raise HTTPException(status_code=500)

    return RoomCreateResponse(room_id=id)


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@router.post("/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    """List all rooms"""

    try:
        if req.live_id == 0:
            rooms = model.get_room_list(user_max=MAX_USER_COUNT, user_min=1, room_status=model.WaitRoomStatus.Waiting)
        else:
            rooms = model.get_room_list(
                req.live_id, user_max=MAX_USER_COUNT, user_min=1, room_status=model.WaitRoomStatus.Waiting
            )
    except Exception:
        raise HTTPException(status_code=500)

    try:
        res = [
            RoomInfo(room_id=r.id, live_id=r.live_id, joined_user_count=r.user_count, max_user_count=MAX_USER_COUNT)
            for r in rooms
        ]
    except Exception:
        raise HTTPException(status_code=500)

    return RoomListResponse(room_info_list=res)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: model.LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: model.JoinRoomResult


@router.post("/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    """Join a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=401)

    try:
        members = model.get_room_members(req.room_id)
    except:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.OtherError)

    if members is None:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.OtherError)

    if len(members) >= MAX_USER_COUNT:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.RoomFull)

    live_status = model.get_room_status(req.room_id)
    if live_status is None:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.OtherError)

    if live_status == model.WaitRoomStatus.Dissolution:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.Disbanded)

    try:
        _remove_already_joined_room_member(me.id)
    except Exception:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.OtherError)

    try:
        model.add_room_member(me.id, req.room_id, req.select_difficulty)
    except Exception:
        return RoomJoinResponse(join_room_result=model.JoinRoomResult.OtherError)

    return RoomJoinResponse(join_room_result=model.JoinRoomResult.Ok)


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: model.WaitRoomStatus
    room_user_list: list[RoomUser]


@router.post("/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    """Wait for a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=401)

    try:
        status = model.get_room_status(req.room_id)
    except Exception:
        raise HTTPException(status_code=500)

    if status is None:
        raise HTTPException(status_code=500)
    try:
        members = model.get_room_members(req.room_id)
    except Exception:
        raise HTTPException(status_code=500)

    if members is None:
        raise HTTPException(status_code=404)

    room_user_list = []

    for m in members:
        try:
            user = model.get_user_by_id(m.user_id)
        except Exception:
            raise HTTPException(status_code=500)

        room_user_list.append(
            RoomUser(
                user_id=user.id,
                name=user.name,
                leader_card_id=user.leader_card_id,
                select_difficulty=m.select_difficulty,
                is_me=(me.id == user.id),
                is_host=m.is_host,
            )
        )

    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int


@router.post("/start", response_model=Empty)
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    """Start a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=401)

    live_status = model.get_room_status(req.room_id)
    if live_status is None:
        raise HTTPException(status_code=500)

    if live_status != model.WaitRoomStatus.Waiting:
        raise HTTPException(status_code=422)

    members = model.get_room_members(req.room_id)

    for m in members:
        if m.user_id == me.id:
            if not m.is_host:
                raise HTTPException(status_code=422)
            break

    try:
        model.update_room_status(req.room_id, model.WaitRoomStatus.LiveStart)
    except Exception:
        raise HTTPException(status_code=500)

    return {}


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@router.post("/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    """End a room"""
    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=401)

    try:
        live_status = model.get_room_status(req.room_id)
    except Exception:
        raise HTTPException(status_code=500)

    if live_status is None:
        raise HTTPException(status_code=500)

    if live_status != model.WaitRoomStatus.LiveStart:
        raise HTTPException(status_code=422)

    try:
        model.store_room_member_result(req.room_id, me.id, req.score, req.judge_count_list)
    except Exception:
        raise HTTPException(status_code=500)

    return {}


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@router.post("/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    """Get result of a room"""

    try:
        members = model.get_room_members(req.room_id)
    except Exception:
        raise HTTPException(status_code=500)

    if members is None:
        raise HTTPException(status_code=500)

    try:
        res = [
            ResultUser(user_id=m.user_id, judge_count_list=json.loads(m.judge_count_list), score=m.score)
            for m in members
        ]
    except Exception:
        return RoomResultResponse(result_user_list=[])

    if len(res) != len(members):
        return RoomResultResponse(result_user_list=[])

    return RoomResultResponse(result_user_list=res)


class RoomLeaveRequest(BaseModel):
    room_id: int


@router.post("/leave", response_model=Empty)
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    """Leave a room"""

    me = model.get_user_by_token(token)
    if me is None:
        raise HTTPException(status_code=401)
    try:
        room_members = model.get_room_members(req.room_id)
    except Exception:
        raise HTTPException(status_code=500)

    if room_members is None:
        raise HTTPException(status_code=500)

    if len(room_members) == 1:
        try:
            model.update_room_status(req.room_id, model.WaitRoomStatus.Dissolution)
        except Exception:
            raise HTTPException(status_code=500)
    else:
        try:
            _pass_host_to_next_member(req.room_id, me.id)
        except Exception:
            raise HTTPException(status_code=500)

    try:
        model.delete_room_member(me.id, req.room_id)
    except Exception:
        raise HTTPException(status_code=500)

    return {}
