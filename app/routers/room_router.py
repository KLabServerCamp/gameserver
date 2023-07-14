from fastapi import APIRouter

from app.schemas.enums import JoinRoomResult
from app.services.user_service import get_user_by_token

from ..auth import InvalidToken, UserToken
from ..db import SqlConnection
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
def create(conn: SqlConnection, token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)

    user = get_user_by_token(conn, token)
    if user is None:
        raise InvalidToken
    room_id = service.create_room(conn, req.live_id, user.id)
    print(f"create_room(): {room_id=}")
    service.join_room(
        conn, room_id=room_id, user_id=user.id, difficulty=req.select_difficulty
    )
    return RoomID(room_id=room_id)


@router.post("/list")
def room_list(conn: SqlConnection, req: RoomListRequest) -> RoomListResponse:
    """ルームリスト取得リクエスト"""
    print("/room/list", req)
    room_list = service.get_room_list(conn, req.live_id)
    return RoomListResponse(room_info_list=room_list)


@router.post("/join")
def join(
    conn: SqlConnection, token: UserToken, req: JoinRoomRequest
) -> JoinRoomResponse:
    """ルーム入場リクエスト"""
    print("/room/join", req)
    join_room_result: JoinRoomResult
    user = get_user_by_token(conn, token)
    if user is None:
        join_room_result = JoinRoomResult.OtherError
    join_room_result = service.join_room(
        conn, room_id=req.room_id, user_id=user.id, difficulty=req.select_difficulty
    )
    return JoinRoomResponse(join_room_result=join_room_result)


@router.post("/wait")
def wait(conn: SqlConnection, token: UserToken, req: RoomID) -> WaitRoomResponse:
    """ルーム待機中（ポーリング）。APIの結果でゲーム開始がわかる。 クライアントはn秒間隔で投げる想定。"""

    user = get_user_by_token(conn, token)
    if user is None:
        raise InvalidToken

    wait_room_status, room_users = service.wait_room(conn, user.id, req.room_id)
    return WaitRoomResponse(status=wait_room_status, room_user_list=room_users)


@router.post("/start")
def start(conn: SqlConnection, token: UserToken, req: RoomID) -> Empty:
    """ルームのライブ開始。部屋のオーナーがたたく。"""

    user = get_user_by_token(conn, token)
    if user is None:
        raise InvalidToken
    service.start_room(conn, room_id=req.room_id)
    return Empty()


@router.post("/end")
def end(conn: SqlConnection, token: UserToken, req: EndRoomRequest) -> Empty:
    """ルームのライブ終了時リクエスト。ゲーム終わったら各人が叩く。"""

    user = get_user_by_token(conn, token)
    if user is None:
        raise InvalidToken
    service.end_room(conn, user.id, req.room_id, req.score, *req.judge_count_list)
    return Empty()


@router.post("/result")
def result(conn: SqlConnection, req: RoomID) -> ResultRoomResponse:
    """
    ルームのライブ終了後。end 叩いたあとにこれをポーリングする。
    クライアントはn秒間隔で投げる想定。
    """
    result_users = service.result_room(conn, room_id=req.room_id)
    return ResultRoomResponse(result_user_list=result_users)


@router.post("/leave")
def leave(conn: SqlConnection, token: UserToken, req: LeaveRoomRequest) -> Empty:
    """ルーム退場リクエスト"""
    print("/room/leave", req)

    user = get_user_by_token(conn, token)
    if user is None:
        raise InvalidToken

    service.leave_room(conn, req.room_id, user.id)
    service.disband_owned_room(conn, req.room_id, user.id)
    return Empty()
