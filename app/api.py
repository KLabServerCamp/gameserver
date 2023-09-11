import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import List

from . import model
from .auth import UserToken
from .model import LiveDifficulty
from .model import JoinRoomResult
from .model import WaitRoomStatus

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
    return {"message": "Hello World!"}


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


class LiveID(BaseModel):
    live_id: int


class RoomList(BaseModel):
    room_info_list: list


class JoinRoomRequest(BaseModel):
    join_room_result: JoinRoomResult


class WaitRoomInfo(BaseModel):
    wait_room_status: WaitRoomStatus


@app.post("/room/create")
def create(token: UserToken, req: CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def list(req: LiveID) -> RoomList:
    """部屋一覧表示"""
    print("/room/list", req)
    room_list = model.search_room(req.live_id)
    print(f"postroom: {room_list}")
    return RoomList(room_info_list=room_list)


@app.post("/room/join")
def join(token: UserToken, req: RoomID) -> JoinRoomRequest:
    """ルーム参加処理"""
    print("/room/join", req)
    join_room_result = model.join_room(token, req.room_id)
    return JoinRoomRequest(join_room_result=join_room_result)


class WaitResultUser(BaseModel):
    id: int
    name: str
    leader_card_id: int
    difficulty: LiveDifficulty
    is_host: bool


@app.post("/room/wait")
def wait(req: RoomID):
    """待機処理"""
    print("/room/wait", req)
    status, user_list = model.room_wait(req.room_id)
    wait_result = {
        "status": status,
        "room_user_list": user_list
    }
    return wait_result


@app.post("/room/start")
def start(token: UserToken, req: RoomID) -> Empty:
    """ライブ開始処理"""
    print("/room/start", req)
    model.room_start(token, req.room_id)
    return Empty()


class ScoreResult(BaseModel):
    room_id: int
    score: int
    judge_count_list: List[int]


@app.post("/room/end")
def end(token: UserToken, req: ScoreResult) -> Empty:
    """ライブ終了処理"""
    print("/room/end", req)
    model.room_end(token, req.room_id, req.judge_count_list, req.score)
    return Empty()


@app.post("/room/result")
def result(req: RoomID):
    """ライブリザルト処理"""
    print("/room/result", req)
    user_result = model.room_result(req.room_id)
    return user_result


@app.post("/room/leave")
def leave(token: UserToken, req: RoomID) -> Empty:
    """退出処理"""
    print("/room/leave", req)
    model.room_leave(token, req.room_id)
    return Empty()
