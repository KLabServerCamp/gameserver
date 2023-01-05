from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import RoomInfo, SafeUser


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class JoinRoomResult(Enum):
    Ok = 1  # 入場OK
    RoomFull = 2  # 満員
    Disbanded = 3  # 解散済み
    OtherError = 4  # その他エラー


class WaitRoomStatus(Enum):
    Waiting = 1  # ホストがライブ開始ボタン押すのを待っている
    LiveStart = 2  # ライブ画面遷移OK
    Dissolution = 3  # 解放された


app = FastAPI()

# Sample APIs


@app.get("/")
async def root():
    return {"message": "Hello World"}


# User APIs


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)  # ok
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


@app.get("/user/me", response_model=SafeUser)  # ok
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


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list = []


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list = []


class RoomEndRequest(BaseModel):
    room_id: int
    score: int
    judge_count_list: list[int]


@app.post("/room/create", response_model=RoomCreateResponse)  # ok
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    room_id = model.create_room(user.id, req.live_id, req.select_difficulty)

    return RoomCreateResponse(room_id=room_id)


@app.post("/room/list", response_model=RoomListResponse)  # ok
def room_list(req: RoomListRequest):
    room_info_list = model.list_room(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    wait_room_status, room_user_list = model.wait_room(user.id, req.room_id)
    return RoomWaitResponse(status=wait_room_status, room_user_list=room_user_list)


@app.post("/room/start", response_model=Empty)
def room_start(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.start_room(user.id, req.room_id)
    return {}


@app.post("/room/end", response_model=Empty)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.end_room(user.id, req.room_id, req.judge_count_list, req.score)
    return {}


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list = []


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    result_user_list = model.result_room(req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    join_room_result = model.join_room(user.id, req.room_id, req.select_difficulty)
    # return RoomJoinResponse(join_room_result=join_room_result)
    return join_room_result


class RoomLeaveRequest(BaseModel):
    room_id: int


@app.post("/room/leave", response_model=Empty)
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    user = model.get_user_by_token(token)
    model.leave_room(user.id, req.room_id)
    return {}
