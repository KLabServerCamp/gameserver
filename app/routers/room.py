from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import model
from ..dependencies import get_auth_token
from ..model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    WaitRoomStatus,
)

router = APIRouter(
    prefix="/room",
    tags=["room"],
)


class Empty(BaseModel):
    pass


class RoomCreateRequest(BaseModel):
    """Room作成時のリクエスト

    Attributes
    ----------
    live_id: int
        ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty
        選択難易度
    """

    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    """Room作成時のレスポンス

    Attributes
    ----------
    room_id: int
        発行されたルームのID（以後の通信はこのiDを添える）
    """

    room_id: int


class RoomListRequest(BaseModel):
    """Room一覧取得時のリクエスト

    Attributes
    ----------
    live_id: int
        ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）
    """

    live_id: int


class RoomListResponse(BaseModel):
    """Room一覧取得時のレスポンス

    Attributes
    ----------
    room_info_list: list[RoomInfo]
        ルーム一覧
    """

    room_info_list: list[RoomInfo]


class RoomJoinRequest(BaseModel):
    """Room参加時のリクエスト

    Attributes
    ----------
    room_id: int
        入るルーム
    select_difficulty: LiveDifficulty
        選択難易度
    """

    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    """Room参加時のレスポンス

    Attributes
    ----------
    join_room_result: JoinRoomResult
        ルーム入場結果
    """

    join_room_result: JoinRoomResult


class RoomWaitRequest(BaseModel):
    """ルーム待機時のリクエスト

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


class RoomWaitResponse(BaseModel):
    """ルーム待機時のレスポンス

    Attributes
    ----------
    status: WaitRoomStatus
        結果
    room_user_list: list[RoomUser]
        ルームにいるプレイヤー一覧
    """

    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    """ルーム開始時のリクエスト

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


class RoomEndRequest(BaseModel):
    """ルームのライブ終了時リクエスト

    ゲーム終わったら各人が叩く。

    Attributes
    ----------
    room_id: int
        対象ルーム
    judge_count_list: list[int]
        各判定数
    score: int
        スコア
    """

    room_id: int
    judge_count_list: list[int]
    score: int


class RoomResultRequest(BaseModel):
    """ルームの結果取得時のリクエスト

    end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


class RoomResultResponse(BaseModel):
    """ルームの結果取得時のレスポンス

    Attributes
    ----------
    result_user_list: list[ResultUser]
        自身を含む各ユーザーの結果。※全員揃っていない待機中は[]が返却される想定
    """

    result_user_list: list[ResultUser]


class RoomLeaveRequest(BaseModel):
    """ルームの退出時のリクエスト

    Attributes
    ----------
    room_id: int
        対象ルーム
    """

    room_id: int


# Room APIs


@router.post("/create", response_model=RoomCreateResponse)
def create_room(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    """Roomを作成する"""
    room_id = model.create_room(token, req.live_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        model.insert_room_member(room_id, me.id, req.select_difficulty, is_owner=True)
    return RoomCreateResponse(room_id=room_id)


@router.post("/list", response_model=RoomListResponse)
def get_room_list(req: RoomListRequest) -> RoomListResponse:
    room_info_list = model.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


@router.post("/join", response_model=RoomJoinResponse)
def join_room(
    req: RoomJoinRequest, token: str = Depends(get_auth_token)
) -> RoomJoinResponse:
    """Roomに参加する"""
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        join_room_result = model.join_room(req.room_id, me.id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=join_room_result)


@router.post("/wait", response_model=RoomWaitResponse)
def wait_room(
    req: RoomWaitRequest, token: str = Depends(get_auth_token)
) -> RoomWaitResponse:
    """Roomの待機状態を取得する"""
    status = model.get_room_status(req.room_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        room_user_list = model.get_room_user_list(req.room_id, me.id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


@router.post("/start", response_model=Empty)
def start_room(req: RoomStartRequest, token: str = Depends(get_auth_token)) -> Empty:
    """Roomをゲーム開始状態にする"""
    # NOTE:
    # オーナーかどうかを確認する必要があるかも
    model.start_room(req.room_id)
    return Empty()


@router.post("/end", response_model=Empty)
def end_room(req: RoomEndRequest, token: str = Depends(get_auth_token)) -> Empty:
    """結果をサーバーに送信する"""
    if len(req.judge_count_list) != 5:
        raise Exception("Length of judge_count_list must be 5.")
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        model.store_score(req.room_id, me.id, req.judge_count_list, req.score)
    return Empty()


@router.post("/result", response_model=RoomResultResponse)
def get_room_result(req: RoomResultRequest) -> RoomResultResponse:
    """ルームの結果を取得する"""
    result_user_list = model.get_room_result(req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)


@router.post("/leave", response_model=Empty)
def leave_room(req: RoomLeaveRequest, token: str = Depends(get_auth_token)) -> Empty:
    """Roomから退出する"""
    me = model.get_user_by_token(token)
    if me is None:
        raise Exception("user not found")
    else:
        model.leave_room(req.room_id, me.id)
    return Empty()
