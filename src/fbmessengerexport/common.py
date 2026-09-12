from typing import TypedDict


class MessageRow(TypedDict):
    uid: str
    timestamp: int
    text: str | None


class ThreadRow(TypedDict):
    uid: str
    name: str


# TODO use them in dal.py as well
