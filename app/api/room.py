from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import model
from .user import get_auth_token

router = APIRouter()


class RoomCreateRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID
    select_difficulty: model.LiveDifficulty  # 難易度


class RoomCreateResponse(BaseModel):
    room_id: int  # 発行されたルームのID（以後の通信はこのiDを添える）


@router.post("/create", response_model=RoomCreateResponse)
def create(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    """ルームを作成する"""
    # print(req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID


class RoomListResponse(BaseModel):
    room_info_list: list[model.RoomInfo]  # 入場可能なルームのリスト


@router.post("/list", response_model=RoomListResponse)
def rooms(req: RoomListRequest) -> RoomListResponse:
    """ルーム一覧を表示する"""
    # print(req)
    room_info_list = model.get_waiting_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


class RoomJoinRequest(BaseModel):
    room_id: int  # 入場するルームのID
    select_difficulty: model.LiveDifficulty  # 難易度


class RoomJoinResponse(BaseModel):
    join_room_result: model.JoinRoomResult  # 入場結果


@router.post("/join", response_model=RoomJoinResponse)
def join(
    req: RoomJoinRequest, token: str = Depends(get_auth_token)
) -> RoomJoinResponse:
    """ルームに参加する"""
    # print(req)
    result = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=result)


class RoomWaitRequest(BaseModel):
    room_id: int  # 入場するルームのID


class RoomWaitResponse(BaseModel):
    status: model.WaitRoomStatus  # 入場結果
    room_user_list: list[model.RoomUser]  # ルーム内のユーザー一覧


@router.post("/wait", response_model=RoomWaitResponse)
def wait(
    req: RoomWaitRequest, token: str = Depends(get_auth_token)
) -> RoomWaitResponse:
    """ルーム待機する"""
    # print(req)
    status, room_user_list = model.wait_room(token, req.room_id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class LiveStartRequest(BaseModel):
    room_id: int  # 入場するルームのID


class LiveStartResponse(BaseModel):
    pass


@router.post("/start", response_model=LiveStartResponse)
def start(req: LiveStartRequest, token: str = Depends(get_auth_token)):
    """ルーム開始する"""
    # print(req)
    model.start_live(token, req.room_id)
    return dict[str, object]()


class RoomEndRequest(BaseModel):
    room_id: int  # 入場するルームのID
    judge_count_list: list[int]  # ユーザーの判定数
    score: int  # ユーザーのスコア


class RoomEndResponse(BaseModel):
    pass


@router.post("/end", response_model=RoomEndResponse)
def end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    """ルーム終了する"""
    # print(req)
    judge: str = ",".join(map(str, req.judge_count_list))
    model.end_live(token, req.room_id, judge, req.score)
    return dict[str, object]()


class RoomResultRequest(BaseModel):
    room_id: int  # 入場するルームのID


class RoomResultResponse(BaseModel):
    result_user_list: list[model.ResultUser]  # ルームの結果


@router.post("/result", response_model=RoomResultResponse)
def result(req: RoomResultRequest) -> RoomResultResponse:
    """ルーム結果を表示する"""
    # print(req)
    result = model.get_room_result(req.room_id)
    return RoomResultResponse(result_user_list=result)


class RoomLeaveRequest(BaseModel):
    room_id: int  # ルームのID


class RoomLeaveResponse(BaseModel):
    pass


@router.post("/leave", response_model=RoomLeaveResponse)
def leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    """ルームを退出する"""
    # print(req)
    model.leave_room(token, req.room_id)
    return dict[str, object]()
