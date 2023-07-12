import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError

from . import db_controllers as controllers
from . import models
from .auth import UserToken

app = FastAPI()


# リクエストのvalidation errorをprintする
# このエラーが出たら、リクエストのModel定義が間違っている
@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(req: Request, exc: RequestValidationError):
    print("Request validation error")
    print(f"{req.url=}\n{exc.body=}\n{exc=!s}")
    return await fastapi.exception_handlers.request_validation_exception_handler(
        req, exc
    )


# Sample API
@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


# User APIs


@app.post("/user/create")
def user_create(req: models.UserCreateRequest) -> models.UserCreateResponse:
    """新規ユーザー作成"""
    token = controllers.create_user(req.user_name, req.leader_card_id)
    return models.UserCreateResponse(user_token=token)


# 認証動作確認用のサンプルAPI
# ゲームアプリは使わない
@app.get("/user/me")
def user_me(token: UserToken) -> models.SafeUser:
    user = controllers.get_user_by_token(token)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    # print(f"user_me({token=}, {user=})")
    # 開発中以外は token をログに残してはいけない。
    return user


@app.post("/user/update")
def update(req: models.UserCreateRequest, token: UserToken) -> models.Empty:
    """Update user attributes"""
    # print(req)
    controllers.update_user(token, req.user_name, req.leader_card_id)
    return models.Empty()


# Room APIs


@app.post("/room/create")
def create(token: UserToken, req: models.CreateRoomRequest) -> models.RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = controllers.create_room(token, req.live_id, req.select_difficulty)
    return models.RoomID(room_id=room_id)


@app.post("/room/list")
def room_list(req: models.RoomListRequest) -> models.RoomListResponse:
    """ルームリスト取得リクエスト"""
    print("/room/list", req)
    room_list = controllers.get_room_list(req.live_id)
    return models.RoomListResponse(room_info_list=room_list)


@app.post("/room/join")
def join(token: UserToken, req: models.JoinRoomRequest) -> models.JoinRoomResponse:
    """ルーム入場リクエスト"""
    print("/room/join", req)
    join_room_result = controllers.join_room(token, req.room_id, req.select_difficulty)
    return models.JoinRoomResponse(join_room_result=join_room_result)


@app.post("/room/leave")
def leave(token: UserToken, req: models.LeaveRoomRequest) -> models.Empty:
    """ルーム退場リクエスト"""
    print("/room/leave", req)
    controllers.leave_room(token, req.room_id)
    return models.Empty()
