from sqlalchemy import create_engine

from . import config

# from sqlalchemy.ext.declarative import as_declarative, declared_attr
# from sqlalchemy import Column, ForeignKey, INT, JSON, BIGINT, VARCHAR

engine = create_engine(config.DATABASE_URI, future=True, echo=True, pool_recycle=300)

# @as_declarative()
# class Base:
#     @declared_attr
#     def __tablename__(cls):
#         return cls.__name__.lower()


# class User(Base):
#     __tablename__ = "user"
#     id = Column(BIGINT, primary_key=True, autoincrement=True, nullable=False)
#     name = Column(VARCHAR(255), nullable=False)
#     token = Column(VARCHAR(255), nullable=False, unique=True)
#     leader_card_id = Column(INT, nullable=False)


# class Room(Base):
#     __tablename__ = "room"
#     id = Column(INT, primary_key=True, nullable=False, autoincrement=True)
#     live_id = Column(INT, nullable=False)
#     # ondelete="CASCADE" で子も削除
#     owner_id = Column(BIGINT, ForeignKey("user.id", ondelete="SET NULL"))
#     status = Column(INT)


# class RoomMember(Base):
#     __tablename__ = "room_member"
#     room_id = Column(BIGINT, ForeignKey("room.id", ondelete="SET NULL"),
#                      primary_key=True, nullable=False)
#     user_id = Column(BIGINT, ForeignKey("user.id", ondelete="SET NULL"),
#                      primary_key=True, nullable=False)
#     score = Column(INT)
#     judge_count_list = Column(JSON)
#     difficulty = Column(INT)
