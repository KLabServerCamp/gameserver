from typing import Annotated, Any, Generator

from fastapi import Depends
from sqlalchemy import Connection, create_engine

from . import config

engine = create_engine(config.DATABASE_URI, future=True, echo=True, pool_recycle=300)


def get_db() -> Generator[Connection, Any, None]:
    with engine.begin() as connection:
        yield connection


SqlConnection = Annotated[Connection, Depends(get_db)]
