from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import model
from ..dependencies import get_auth_token
from ..exceptions import InvalidJudgeResult, InvalidToken, RoomNotFound
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
    """空のレスポンス"""

    pass


class RoomCreateRequest(BaseModel):
    """Room作成時のリクエスト"""

    live_id: int = Field(description="ルームで遊ぶ楽曲のID")
    select_difficulty: LiveDifficulty = Field(description="選択難易度")


class RoomCreateResponse(BaseModel):
    """Room作成時のレスポンス"""

    room_id: int = Field(description="発行されたルームのID（以後の通信はこのiDを添える）")


class RoomListRequest(BaseModel):
    """Room一覧取得時のリクエスト"""

    live_id: int = Field(description="ルームで遊ぶ楽曲のID（※0はワイルドカード。全てのルームを対象とする）")


class RoomListResponse(BaseModel):
    """Room一覧取得時のレスポンス"""

    room_info_list: list[RoomInfo] = Field(description="ルーム一覧")


class RoomJoinRequest(BaseModel):
    """Room参加時のリクエスト"""

    room_id: int = Field(description="入るルーム")
    select_difficulty: LiveDifficulty = Field(description="選択難易度")


class RoomJoinResponse(BaseModel):
    """Room参加時のレスポンス"""

    join_room_result: JoinRoomResult = Field(description="ルーム入場結果")


class RoomWaitRequest(BaseModel):
    """ルーム待機時のリクエスト"""

    room_id: int = Field(description="対象ルーム")


class RoomWaitResponse(BaseModel):
    """ルーム待機時のレスポンス"""

    status: WaitRoomStatus = Field(description="参加しているルームの状態")
    room_user_list: list[RoomUser] = Field(description="ルームにいるプレイヤー一覧")


class RoomStartRequest(BaseModel):
    """ルーム開始時のリクエスト"""

    room_id: int = Field(description="対象ルーム")


class RoomEndRequest(BaseModel):
    """ルームのライブ終了時リクエスト"""

    room_id: int = Field(description="対象ルーム")
    judge_count_list: list[int] = Field(description="各判定数")
    score: int = Field(description="スコア")


class RoomResultRequest(BaseModel):
    """ルームの結果取得時のリクエスト

    /room/end 叩いたあとにこれをポーリングする。 クライアントはn秒間隔で投げる想定。
    """

    room_id: int = Field(description="対象ルーム")


class RoomResultResponse(BaseModel):
    """ルームの結果取得時のレスポンス"""

    result_user_list: list[ResultUser] = Field(
        description="自身を含む各ユーザーの結果※全員揃っていない待機中は[]が返却される想定"
    )


class RoomLeaveRequest(BaseModel):
    """ルームの退出時のリクエスト"""

    room_id: int = Field(description="対象ルーム")


# Room APIs


@router.post("/create", response_model=RoomCreateResponse)
def create_room(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    """Roomを作成する"""
    room_id = model.create_room(token, req.live_id)
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()
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
        raise InvalidToken()

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
        raise InvalidToken()

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
        raise InvalidJudgeResult()
    me = model.get_user_by_token(token)
    if me is None:
        raise InvalidToken()

    model.store_score(req.room_id, me.id, req.judge_count_list, req.score)
    return Empty()


@router.post("/result", response_model=RoomResultResponse)
def get_room_result(req: RoomResultRequest) -> RoomResultResponse:
    """ルームの結果を取得する"""
    result_user_list = model.get_room_result(req.room_id)
    room_info = model.get_room_info_by_room_id(req.room_id)

    if room_info is None:
        raise RoomNotFound()

    # 全員が終了した場合のみリザルトを返す
    if len(result_user_list) < room_info.joined_user_count:
        return RoomResultResponse(result_user_list=[])

    return RoomResultResponse(result_user_list=result_user_list)


@router.post("/leave", response_model=Empty)
def leave_room(req: RoomLeaveRequest, token: str = Depends(get_auth_token)) -> Empty:
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

    return Empty()
