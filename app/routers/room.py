from fastapi import APIRouter
from pydantic import BaseModel

from app import schemas
from app.auth import UserToken
from app.models import Room

from .user import Empty

router = APIRouter()


@router.post("/room/create")
def create(token: UserToken, req: schemas.CreateRoomRequest) -> schemas.RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = Room.create_room(token, req.live_id, req.select_difficulty)
    return schemas.RoomID(room_id=room_id)


@router.post("/room/list")
def list_(req: schemas.ListRoomRequest):
    """ルーム一覧"""
    room_info_list: list = Room.get_room_list(req.live_id)
    return schemas.ListRoomResponse(room_info_list=room_info_list)


@router.post("/room/join")
def join_(token: UserToken, req: schemas.JoinRoomRequest):
    """room に join する"""
    res = Room.join_room(token, req.room_id, req.select_difficulty)
    return schemas.JoinRoomResponse(join_room_result=res)


@router.post("/room/wait")
def wait(token: UserToken, req: schemas.WaitRoomRequest):
    status, users = Room.wait_room(token, req.room_id)
    return schemas.WaitRoomResponse(status=status, room_user_list=users)


@router.post("/room/start")
def start(token: UserToken, req: schemas.StartRoomRequest):
    Room.start_room(token, req.room_id)
    return Empty()


@router.post("/room/end")
def end(token: UserToken, req: schemas.EndRoomRequest):
    Room.end_room(token, req.room_id, req.score, req.judge_count_list)
    return Empty()


@router.post("/room/result")
def result(req: schemas.ResultRoomRequest):
    print("/room/result", req)
    results: list[schemas.ResultUser] = Room.room_result(req.room_id)
    return schemas.ResultRoomResponse(result_user_list=results)


@router.post("/room/leave")
def leave(token: UserToken, req: schemas.LeaveRoomRequest):
    Room.leave_room(token, req.room_id)
    return Empty()
