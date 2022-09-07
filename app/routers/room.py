from fastapi import APIRouter, Depends

from .. import model, schemas
from ..dependencies import get_auth_token
from ..exceptions import InvalidJudgeResult, InvalidToken, RoomNotFound

router = APIRouter(
    prefix="/room",
    tags=["room"],
)

# Room APIs


@router.post("/create", response_model=schemas.RoomCreateResponse)
def create_room(
    req: schemas.RoomCreateRequest, token: str = Depends(get_auth_token)
) -> schemas.RoomCreateResponse:
    """Roomを作成する"""
    room_id = model.create_room(token, req.live_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()
    else:
        model.insert_room_member(room_id, me.id, req.select_difficulty, is_owner=True)
    return schemas.RoomCreateResponse(room_id=room_id)


@router.post("/list", response_model=schemas.RoomListResponse)
def get_room_list(req: schemas.RoomListRequest) -> schemas.RoomListResponse:
    room_info_list = model.get_room_list(req.live_id)
    return schemas.RoomListResponse(room_info_list=room_info_list)


@router.post("/join", response_model=schemas.RoomJoinResponse)
def join_room(
    req: schemas.RoomJoinRequest, token: str = Depends(get_auth_token)
) -> schemas.RoomJoinResponse:
    """Roomに参加する"""
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()

    join_room_result = model.join_room(req.room_id, me.id, req.select_difficulty)
    return schemas.RoomJoinResponse(join_room_result=join_room_result)


@router.post("/wait", response_model=schemas.RoomWaitResponse)
def wait_room(
    req: schemas.RoomWaitRequest, token: str = Depends(get_auth_token)
) -> schemas.RoomWaitResponse:
    """Roomの待機状態を取得する"""
    status = model.get_room_status(req.room_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()

    room_user_list = model.get_room_user_list(req.room_id, me.id)
    return schemas.RoomWaitResponse(status=status, room_user_list=room_user_list)


@router.post("/start", response_model=schemas.EmptyResponse)
def start_room(
    req: schemas.RoomStartRequest, token: str = Depends(get_auth_token)
) -> schemas.EmptyResponse:
    """Roomをゲーム開始状態にする"""
    # NOTE:
    # オーナーかどうかを確認する必要があるかも
    model.start_room(req.room_id)
    return schemas.EmptyResponse()


@router.post("/end", response_model=schemas.EmptyResponse)
def end_room(
    req: schemas.RoomEndRequest, token: str = Depends(get_auth_token)
) -> schemas.EmptyResponse:
    """結果をサーバーに送信する"""
    if len(req.judge_count_list) != 5:
        raise InvalidJudgeResult()
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()

    model.store_score(req.room_id, me.id, req.judge_count_list, req.score)
    return schemas.EmptyResponse()


@router.post("/result", response_model=schemas.RoomResultResponse)
def get_room_result(req: schemas.RoomResultRequest) -> schemas.RoomResultResponse:
    """ルームの結果を取得する"""
    result_user_list = model.get_room_result(req.room_id)
    room_info = model.get_room_info_by_room_id(req.room_id)

    if room_info is None:
        raise RoomNotFound()

    # 全員が終了した場合のみリザルトを返す
    if len(result_user_list) < room_info.joined_user_count:
        return schemas.RoomResultResponse(result_user_list=[])

    return schemas.RoomResultResponse(result_user_list=result_user_list)


@router.post("/leave", response_model=schemas.EmptyResponse)
def leave_room(
    req: schemas.RoomLeaveRequest, token: str = Depends(get_auth_token)
) -> schemas.EmptyResponse:
    """Roomから退出する"""
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()

    users = model.get_room_user_list(req.room_id, me.id)

    for user in users:
        if user.user_id == me.id:
            is_host = user.is_host
            break

    # オーナーが退出する場合、次のユーザーをオーナーにする
    if is_host and len(users) >= 2:
        for user in users:
            if user.user_id != me.id:
                model.move_owner_to(req.room_id, user.user_id)
                break

    model.leave_room(req.room_id, me.id)

    # もしそのユーザが最後のユーザだったらルームを削除する
    if len(users) == 0:
        model.delete_room(req.room_id)

    return schemas.EmptyResponse()
