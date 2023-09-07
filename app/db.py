from sqlalchemy import create_engine

from . import config

engine = create_engine(
    config.DATABASE_URI,
    future=True,
    echo=True,
    pool_recycle=300
)
