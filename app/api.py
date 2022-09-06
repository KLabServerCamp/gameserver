from enum import Enum

# from lib2to3.pytree import Base
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


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest):
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


bearer = HTTPBearer()


def get_auth_token(
    cred: HTTPAuthorizationCredentials = Depends(bearer)
) -> str:
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
    return SafeUser(
        id=user.id, name=user.name, leader_card_id=user.leader_card_id
    )


class Empty(BaseModel):
    pass


class UserUpdateRequest(BaseModel):
    user_name: str
    leader_card_id: int


@app.post("/user/update", response_model=Empty)
def update(req: UserUpdateRequest, token: str = Depends(get_auth_token)):
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()


class LiveDifficulty(Enum):
    normal = 1
    hard = 2


class RoomCreateRequest(BaseModel):
    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    room_id: int


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(req: RoomCreateRequest, token: str = Depends(get_auth_token)):
    """新規ルーム作成"""
    # 入力：曲ID,難易度設定 + トークン
    # 出力：ルームID
    id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=id)


class JoinRoomResult(Enum):
    Ok = 1
    RoomFull = 2
    Disbanded = 3
    OtherError = 4


class WaitRoomStatus(Enum):
    Waiting = 1
    LiveStart = 2
    Dissolution = 3


class RoomInfo(BaseModel):
    room_id: int
    live_id: int
    joined_user_count: int
    max_user_count: int


class RoomUser(BaseModel):
    user_id: int
    name: str
    leader_card_id: int
    select_difficulty: LiveDifficulty
    is_me: bool
    is_host: bool


class ResultUser(BaseModel):
    user_id: int
    judge_count_list: list[int]
    score: int


class RoomListRequest(BaseModel):
    live_id: int


class RoomListResponse(BaseModel):
    room_info_list: list[RoomInfo]


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest, token: str = Depends(get_auth_token)):
    """新規ルーム作成"""
    # 入力：曲ID
    # 出力：部屋一覧
    rows = model.list_room(token, req.live_id)
    # print(rows)
    output = []
    for row in rows:
        element = RoomInfo(
            room_id=row["room_id"], live_id=row["live_id"],
            joined_user_count=row["joined_user_count"],
            max_user_count=row["max_user_count"]
        )
        output.append(element)
    # print(output)
    return RoomListResponse(room_info_list=output)


class RoomJoinRequest(BaseModel):
    room_id: int
    select_difficulty: LiveDifficulty


class RoomJoinResponse(BaseModel):
    join_room_result: JoinRoomResult


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(req: RoomJoinRequest, token: str = Depends(get_auth_token)):
    # 入力：部屋ID,難易度
    # 出力：部屋入場結果
    join_result = model.join_room(token, req.room_id, req.select_difficulty)
    # print(rows)
    return RoomJoinResponse(join_room_result=join_result)


class RoomWaitRequest(BaseModel):
    room_id: int


class RoomWaitResponse(BaseModel):
    status: WaitRoomStatus
    room_user_list: list[RoomUser]


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(req: RoomWaitRequest, token: str = Depends(get_auth_token)):
    result = model.wait_room(req.room_id, token)
    output = []
    for row in result[1]:
        output.append(
            dict(
                user_id=row.user_id,
                name=row.name,
                leader_card_id=row.leader_card_id,
                select_difficulty=row.select_difficulty,
                is_me=row.is_me,
                is_host=row.is_host
            )
        )
    return RoomWaitResponse(status=result[0], room_user_list=output)


class RoomStartRequest(BaseModel):
    room_id: int


class RoomStartResponse(BaseModel):
    pass


@app.post("/room/start", response_model=RoomStartResponse)
def room_start(req: RoomStartRequest):
    model.start_room(req.room_id)
    return RoomStartResponse()


class RoomEndRequest(BaseModel):
    room_id: int
    judge_count_list: list[int]
    score: int


class RoomEndResponse(BaseModel):
    pass


@app.post("/room/end", response_model=RoomEndResponse)
def room_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    model.end_room(req.room_id, req.judge_count_list, req.score, token)
    return RoomEndResponse()


class RoomResultRequest(BaseModel):
    room_id: int


class RoomResultResponse(BaseModel):
    result_user_list: list[ResultUser]


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest):
    result = model.result_room(req.room_id)
    output = []
    for row in result:
        output.append(
            dict(
                user_id=row.user_id,
                judge_count_list=[
                    row.judge_perfect,
                    row.judge_great,
                    row.judge_good,
                    row.judge_bad,
                    row.judge_miss,
                ],
                score=row.score
            )
        )
    # print("出力：", output)
    return RoomResultResponse(result_user_list=output)


class RoomLeaveRequest(BaseModel):
    room_id: int


class RoomLeaveResponse(BaseModel):
    pass


@app.post("/room/leave", response_model=RoomLeaveResponse)
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    model.leave_room(req.room_id, token)
    return RoomLeaveResponse()
