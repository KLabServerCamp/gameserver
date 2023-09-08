import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import (
    JoinRoomResult,
    LiveDifficulty,
    ResultUser,
    RoomInfo,
    RoomUser,
    WaitRoomStatus,
)

app = FastAPI()


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req, exc):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers.request_validation_exception_handler(
        req, exc
    )


# Sample API
@app.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


# User APIs


# FastAPI 0.100 は model_validate_json() を使わないので、 strict モードにすると
# EnumがValidationエラーになってしまいます。
class UserCreateRequest(BaseModel):
    user_name: str = Field(title="ユーザー名")
    leader_card_id: int = Field(title="リーダーカードのID")


# Responseの方は strict モードを利用できます
class UserCreateResponse(BaseModel, strict=True):
    user_token: str


@app.post("/user/create")
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


# 認証動作確認用のサンプルAPI
# ゲームアプリは使わない
@app.get("/user/me")
def user_me(token: UserToken) -> model.SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update")
def update(req: UserCreateRequest, token: UserToken) -> Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class RoomID(BaseModel):
    room_id: int


class CreateRoomRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


class RoomList(BaseModel):
    room_info_list: list[RoomInfo]


class ListRoomRequest(BaseModel):
    live_id: int


@app.post("/room/list")
def list_room(token: UserToken, req: ListRoomRequest) -> RoomList:
    """ルームリストのリクエスト"""
    print("/room/list", req)
    room_info_list = model.list_room(token, req.live_id)
    return RoomList(room_info_list=room_info_list)


class JoinRoomResponse(BaseModel):
    join_room_result: JoinRoomResult


class JoinRoomRequest(BaseModel):
    room_id: int
    select_difficulty: int


@app.post("/room/join")
def join_room(token: UserToken, req: JoinRoomRequest) -> JoinRoomResponse:
    """ルーム参加リクエスト"""
    print("/room/join", req)
    join_room_result = model.join_room(token, req.room_id, req.select_difficulty)
    return JoinRoomResponse(join_room_result=join_room_result)


class WaitRoomResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait")
def wait_room(token: UserToken, req: RoomID) -> WaitRoomResponse:
    """ルーム待機中"""
    print("/room/wait", req)
    status, room_user_list = model.wait_room(token, req.room_id)
    return WaitRoomResponse(status=status, room_user_list=room_user_list)


@app.post("/room/start")
def start_room(token: UserToken, req: RoomID):
    """ルーム開始"""
    print("/room/start", req)
    model.start_room(token, req.room_id)


class EndRoomRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


@app.post("/room/end")
def end_room(token: UserToken, req: EndRoomRequest):
    """ルーム終了"""
    print("/room/end", req)
    model.end_room(token, req.room_id, req.judge_count_list, req.score)


class ResultRoomRespomse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result")
def result_room(token: UserToken, req: RoomID):
    """ルーム結果表示"""
    print("/room/result", req)
    result_user_list = model.result_room(token, req.room_id)
    if result_user_list is not None:
        return ResultRoomRespomse(result_user_list=result_user_list)
