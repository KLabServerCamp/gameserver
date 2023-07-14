from fastapi import APIRouter

from ..auth import UserToken
from ..schemas.structures import (
    CreateRoomRequest,
    Empty,
    EndRoomRequest,
    JoinRoomRequest,
    JoinRoomResponse,
    LeaveRoomRequest,
    ResultRoomResponse,
    RoomID,
    RoomListRequest,
    RoomListResponse,
    WaitRoomResponse,
)
from ..services import room_service as service

router = APIRouter()


@router.post("/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = service.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@router.post("/list")
def room_list(req: RoomListRequest) -> RoomListResponse:
    """ルームリスト取得リクエスト"""
    print("/room/list", req)
    room_list = service.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_list)


@router.post("/join")
def join(token: UserToken, req: JoinRoomRequest) -> JoinRoomResponse:
    """ルーム入場リクエスト"""
    print("/room/join", req)
    join_room_result = service.join_room(token, req.room_id, req.select_difficulty)
    return JoinRoomResponse(join_room_result=join_room_result)


@router.post("/wait")
def wait(token: UserToken, req: RoomID) -> WaitRoomResponse:
    """ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。"""
    wait_room_status, room_users = service.wait_room(token, req.room_id)
    return WaitRoomResponse(status=wait_room_status, room_user_list=room_users)


@router.post("/start")
def start(token: UserToken, req: RoomID) -> Empty:
    """ルームのライブ開始。部屋のオーナーがたたく。"""
    service.start_room(token, room_id=req.room_id)
    return Empty()


@router.post("/end")
def end(token: UserToken, req: EndRoomRequest) -> Empty:
    """ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。"""
    service.end_room(token, req.room_id, req.score, *req.judge_count_list)
    return Empty()


@router.post("/result")
def result(token: UserToken, req: RoomID) -> ResultRoomResponse:
    """
    ルームのライブ終了後。end 叩いたあとにこれをポーリングする。
    クライアントはn秒間隔で投げる想定。
    """
    result_users = service.result_room(token, req.room_id)
    return ResultRoomResponse(result_user_list=result_users)


@router.post("/leave")
def leave(token: UserToken, req: LeaveRoomRequest) -> Empty:
    """ルーム退場リクエスト"""
    print("/room/leave", req)
    service.leave_room(token, req.room_id)
    return Empty()
