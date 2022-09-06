from fastapi import APIRouter, Depends
from pydantic import BaseModel

from .. import model
from ..dependencies import get_auth_token
from ..exceptions import InvalidToken
from ..model import SafeUser

router = APIRouter(
    prefix="/user",
    tags=["user"],
)


class UserCreateRequest(BaseModel):
    user_name: str
    leader_card_id: int


class UserCreateResponse(BaseModel):
    user_token: str


class Empty(BaseModel):
    pass


@router.post("/create", response_model=UserCreateResponse)
def user_create(req: UserCreateRequest) -> UserCreateResponse:
    """新規ユーザー作成"""
    token = model.create_user(req.user_name, req.leader_card_id)
    return UserCreateResponse(user_token=token)


@router.get("/me", response_model=SafeUser)
def user_me(token: str = Depends(get_auth_token)) -> SafeUser:
    user = model.get_user_by_token(token)
    if user is None:
        raise InvalidToken()
    return user


@router.post("/update", response_model=Empty)
def update(req: UserCreateRequest, token: str = Depends(get_auth_token)) -> Empty:
    """Update user attributes"""
    # print(req)
    model.update_user(token, req.user_name, req.leader_card_id)
    return Empty()
