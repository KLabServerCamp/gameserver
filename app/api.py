from fastapi import Depends, FastAPI, HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import model
from .model import LiveDifficulty, SafeUser

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


class RoomCreateRequest(BaseModel):
    """Room作成時のリクエスト

    Parameters
    ----------
    live_id: int
        ルームで遊ぶ楽曲のID
    select_difficulty: LiveDifficulty
        選択難易度
    """

    live_id: int
    select_difficulty: LiveDifficulty


class RoomCreateResponse(BaseModel):
    """Room作成時のレスポンス

    Parameters
    ----------
    room_id: int
        発行されたルームのID（以後の通信はこのiDを添える）
    """

    room_id: int


@app.post("/user/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest) -> UserCreateResponse:
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
def user_me(token: str = Depends(get_auth_token)) -> SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=404)
    # print(f"user_me({token=}, {user=})")
    return user


class Empty(BaseModel):
    pass


@app.post("/user/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)) -> dict:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return {}


# Room APIs


@app.post("/room/create", response_model=RoomCreateResponse)
def create_room(
    req: RoomCreateRequest, token: str = Depends(get_auth_token)
) -> RoomCreateResponse:
    room_id = model.create_room(token, req.live_id)
    # TODO: オーナが選択したselect_difficultyを保存する
    return RoomCreateResponse(room_id=room_id)
