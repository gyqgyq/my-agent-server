from datetime import datetime

from sqlalchemy import BigInteger, VARCHAR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(VARCHAR(64), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)

