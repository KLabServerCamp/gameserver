from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import SafeUser

app = FastAPI()

# Sample APIs

@app.get("/")
async def root():
    return {"message": "Hello World"}


# User APIs
# ユーザ作成
class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


# ルーム作成
class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: int


class RoomCreateResponse(BaseModel):
    room_id: int

# ルーム一覧
class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list


# ルーム参加
class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: int


class joinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4

class RoomJoinResponse(BaseModel):
    join_room_result: int


# ルーム状態
class WaitRoomStatus(Enum):
    Wating = 1
    LiveStart = 2
    Dissolution = 3


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: int
    room_user_list: list


# ライブ開始
class RoomStartRequest(BaseModel):
    room_id: int


# ライブ終了
class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list
    score: int


# 結果表示
class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list


# ルーム退去
class RoomLeaveRequest(BaseModel):
    room_id: int


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# ルーム作成
@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    room_id = model.create_room(user_id, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


# ルーム検索
@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest, token: str = Depends(get_auth_token)):
    room_info_list = model.search_room(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


# ルーム参加
@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    room_id = req.room_id
    select_difficulty = req.select_difficulty
    join_room_result = model.join_room(user_id, room_id, select_difficulty)

    return RoomJoinResponse(join_room_result=join_room_result)


# ルーム待ち
@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    room_user_list = model.wait_room(req.room_id, user_id)
    status = model.get_status_by_roomid(req.room_id)
    return RoomWaitResponse(room_user_list=room_user_list, status=status)


# ライブの開始
@app.post("/room/start")
def room_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    model.update_status_by_roomid(req.room_id, 2)


# ライブ終了
@app.post("/room/end")
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    room_id = req.room_id
    judge_count_list = req.judge_count_list
    score = req.score

    model.end_room(user_id, room_id, judge_count_list, score)


# ライブ終了
@app.post("/room/result")
def room_end(req: RoomResultRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    room_id = req.room_id

    result_user_list = model.result_room(room_id)
    return RoomResultResponse(result_user_list=result_user_list)

# ルーム退去
@app.post("/room/leave")
def room_end(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    user_id = model.get_user_by_token(token).id
    room_id = req.room_id

    result_user_list = model.leave_room(user_id,room_id)
