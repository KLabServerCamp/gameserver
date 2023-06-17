"""
認証モジュール

引数に `user: SafeUser` を指定することで認証を行い、そのユーザーを取得できる。
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from .model import SafeUser as SafeUserBase
from .service import get_user_by_token

__all__ = ["SafeUser"]
bearer = HTTPBearer()


def get_auth_user(
        cred: HTTPAuthorizationCredentials = Depends(bearer)) -> SafeUserBase:
    assert cred is not None
    if not cred.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="invalid credential")
    token = cred.credentials
    user = get_user_by_token(token)
    if user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="unauthorized user")
    return user


SafeUser = Annotated[SafeUserBase, Depends(get_auth_user)]
