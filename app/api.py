from enum import Enum

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import SafeUser, LiveDifficulty, JoinRoomResult, WaitRoomStatus, RoomInfo, RoomUser, ResultUser

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


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


class RoomJoinRequest(BaseModel):
    room_id: int


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


class RoomStartRequest(BaseModel):
    room_id: int


class RoomStartResponse(BaseModel):
    pass


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


class RoomEndResponse(BaseModel):
    pass


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


class RoomLeaveRequest(BaseModel):
    room_id: int


class RoomLeaveResponse(BaseModel):
    pass


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


#ルームを新規で建てる
@app.post("room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest):
    user_data = user_me()
    room_id = model.create_room(req.live_id, user_data, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


#入場可能なルーム一覧を取得
@app.post("room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest):
    room_info_list = model.get_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


#ルームに入場
@app.post("room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest):
    user_data = user_me()
    join_room_result = model.join_room(req.room_id, user_data, req.select_difficulty)
    return RoomJoinResponse(join_room_result=join_room_result)


#ルーム待機中
@app.post("room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest):
    user_data = user_me()
    status, room_user_list = model.get_wait_room_status(req.room_id, user_data.id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


#ルームのライブ開始
@app.post("room/start", response_model=RoomStartResponse)
def room_start(req: RoomStartRequest):
    model.room_start_(req.room_id)
    return RoomStartResponse()


#ルームのライブ終了時リクエスト
@app.post("room/end", response_model=RoomEndResponse)
def room_end(req: RoomEndRequest):
    user_data = user_me()
    model.room_end_(user_data.id, req.room_id, req.score, req.judge_count_list)
    return RoomEndResponse()


#ルームのライブ終了後
@app.post("room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    result_user_list = model.get_room_result(req.room_id)
    return RoomResultResponse(result_user_list=result_user_list)