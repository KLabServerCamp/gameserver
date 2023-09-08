import fastapi.exception_handlers
from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from . import model
from .auth import UserToken
from .model import LiveDifficulty

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
    print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


# Room APIs


class RoomID(BaseModel):
    room_id: int


@app.post("/room/create")
def create(token: UserToken, req: model.CreateRoomRequest) -> RoomID:
    """ルーム作成リクエスト"""
    print("/room/create", req)
    room_id = model.create_room(token, req.live_id,
                                LiveDifficulty(req.select_difficulty))
    print(room_id)
    return RoomID(room_id=room_id)


@app.post("/room/list")
def return_list(live_id: int) -> dict:
    rooms = dict()
    rooms["room_info_list"] = model.room_list(live_id=live_id)
    return rooms


@app.post("/room/join")
def join_room(token: UserToken,
              room_id: int, select_difficulty: LiveDifficulty) -> dict:
    result = model._join_room(
        token=token,
        room_id=room_id,
        select_difficulty=select_difficulty
    )
    print(result)
    return {"join_room_result": result}


@app.post("/room/wait")
def wait(token: UserToken, room_id: int) -> dict:
    status = model.get_room_status(room_id=room_id)
    u_id = model.get_user_by_token(token=token)
    room_user_list = model.get_user_list(me=u_id, room_id=room_id)
    ret = {
        "status": status,
        "room_user_list": room_user_list
    }
    print(ret)
    return ret


@app.post("/room/start")
def start(token: UserToken, room_id: int) -> None:
    user = model.get_user_by_token(token=token)
    print("--- user_id ---")
    print(user)
    print("--- is_host ---")
    if model.is_host(user_id=user.id, room_id=room_id):
        print("true")
        model.change_room_state(
            room_id=room_id,
            room_state=model.WaitRoomStatus.LiveStart
            )
    else:
        print("false")


@app.post("/room/end")
def end(token: UserToken, room_id: int, score: int,
        judge_count_list: list[int]):
    user = model.get_user_by_token(token=token)
    model.save_score(user_id=user.id, room_id=room_id, score=score,
                     judge_count_list=judge_count_list)


@app.post("/room/result")
def result(room_id: int) -> list[model.ResultUser]:
    if model.everyone_end(room_id=room_id):
        return model.get_result_user(room_id=room_id)
    else:
        return []


@app.post("/room/leave")
def leave(token: UserToken, room_id: int):
    user = model.get_user_by_token(token=token)
    model.leave_room(user_id=user.id, room_id=room_id)
    return {}
