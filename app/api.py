from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model

app = FastAPI()

# Sample APIs


@app.get("/")
async def root() -> dict[str, str]:
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
    cred: HTTPAuthorizationCredentials = Depends(bearer),
) -> str:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(status_code=401, detail="invalid credential")
    return cred.credentials


@app.get("/user/me", response_model=model.SafeUser)
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
    return dict[str, object]()


# Room APIs


class RoomCreateRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID
    select_difficulty: model.LiveDifficulty  # 難易度


class RoomCreateResponse(BaseModel):
    room_id: int  # 発行されたルームのID（以後の通信はこのiDを添える）


@app.post("/room/create", response_model=RoomCreateResponse)
def room_create(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    """ルームを作成する"""
    # print(req)
    room_id = model.create_room(token, req.live_id, req.select_difficulty)
    return RoomCreateResponse(room_id=room_id)


class RoomListRequest(BaseModel):
    live_id: int  # ルームで遊ぶ楽曲のID


class RoomListResponse(BaseModel):
    room_info_list: list[model.RoomInfo]  # 入場可能なルームのリスト


@app.post("/room/list", response_model=RoomListResponse)
def room_list(req: RoomListRequest) -> RoomListResponse:
    """ルーム一覧を表示する"""
    # print(req)
    room_info_list = model.get_waiting_room_list(req.live_id)
    return RoomListResponse(room_info_list=room_info_list)


class RoomJoinRequest(BaseModel):
    room_id: int  # 入場するルームのID
    select_difficulty: model.LiveDifficulty  # 難易度


class RoomJoinResponse(BaseModel):
    join_room_result: model.JoinRoomResult  # 入場結果


@app.post("/room/join", response_model=RoomJoinResponse)
def room_join(
    req: RoomJoinRequest, token: str = Depends(get_auth_token)
) -> RoomJoinResponse:
    """ルームに参加する"""
    # print(req)
    result = model.join_room(token, req.room_id, req.select_difficulty)
    return RoomJoinResponse(join_room_result=result)


class RoomWaitRequest(BaseModel):
    room_id: int  # 入場するルームのID


class RoomWaitResponse(BaseModel):
    status: model.WaitRoomStatus  # 入場結果
    room_user_list: list[model.RoomUser]  # ルーム内のユーザー一覧


@app.post("/room/wait", response_model=RoomWaitResponse)
def room_wait(
    req: RoomWaitRequest, token: str = Depends(get_auth_token)
) -> RoomWaitResponse:
    """ルーム待機する"""
    # print(req)
    status, room_user_list = model.wait_room(token, req.room_id)
    return RoomWaitResponse(status=status, room_user_list=room_user_list)


class RoomStartRequest(BaseModel):
    room_id: int  # 入場するルームのID


@app.post("/room/start", response_model=Empty)
def live_start(req: RoomStartRequest, token: str = Depends(get_auth_token)):
    """ルーム開始する"""
    # print(req)
    model.start_live(token, req.room_id)
    return dict[str, object]()


class RoomEndRequest(BaseModel):
    room_id: int  # 入場するルームのID
    judge_count_list: list[int]  # ユーザーの判定数
    score: int  # ユーザーのスコア


class RoomEndResponse(BaseModel):
    pass


@app.post("/room/end", response_model=RoomEndResponse)
def live_end(req: RoomEndRequest, token: str = Depends(get_auth_token)):
    """ルーム終了する"""
    # print(req)
    judge: str = ",".join(map(str, req.judge_count_list))
    model.end_live(token, req.room_id, judge, req.score)
    return dict[str, object]()


class RoomResultRequest(BaseModel):
    room_id: int  # 入場するルームのID


class RoomResultResponse(BaseModel):
    result_user_list: list[model.ResultUser]  # ルームの結果


@app.post("/room/result", response_model=RoomResultResponse)
def room_result(req: RoomResultRequest) -> RoomResultResponse:
    """ルーム結果を表示する"""
    # print(req)
    result = model.get_room_result(req.room_id)
    return RoomResultResponse(result_user_list=result)


class RoomLeaveRequest(BaseModel):
    room_id: int  # ルームのID


class RoomLeaveResponse(BaseModel):
    pass


@app.post("/room/leave", response_model=RoomLeaveResponse)
def room_leave(req: RoomLeaveRequest, token: str = Depends(get_auth_token)):
    """ルームを退出する"""
    # print(req)
    model.leave_room(token, req.room_id)
    return dict[str, object]()
