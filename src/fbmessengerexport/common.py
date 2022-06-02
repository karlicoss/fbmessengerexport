import sys
from typing import Optional, TYPE_CHECKING, Dict

if sys.version_info[:2] >= (3, 8):
    from typing import TypedDict
else:
    TypedDict = Dict


class MessageRow(TypedDict):
    uid: str
    timestamp: int
    text: Optional[str]

class ThreadRow(TypedDict):
    uid: str
    name: str

# TODO use them in dal.py as well
