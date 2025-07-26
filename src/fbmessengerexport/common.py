from typing import Optional, TypedDict


class MessageRow(TypedDict):
    uid: str
    timestamp: int
    text: Optional[str]


class ThreadRow(TypedDict):
    uid: str
    name: str


# TODO use them in dal.py as well
