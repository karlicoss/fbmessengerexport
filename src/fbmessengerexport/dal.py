#!/usr/bin/env python3
from __future__ import annotations

from contextlib import ContextDecorator
from datetime import datetime, timezone
import sqlite3
from typing import Iterator, Optional, NamedTuple

from .exporthelpers import dal_helper
from .exporthelpers.dal_helper import PathIsh, datetime_aware
from .common import MessageRow, ThreadRow


class Message(NamedTuple):
    row: MessageRow
    thread: Thread

    @property
    def id(self) -> str:
        return self.row['uid']

    @property
    def dt(self) -> datetime_aware:
        # compared it against old messages in a different timezone, and it does seem to be UTC?
        return datetime.fromtimestamp(self.row['timestamp'] / 1000, tz=timezone.utc)

    @property
    def text(self) -> Optional[str]:
        # NOTE: it also might be empty string -- not sure what it means
        return self.row['text']


class Thread(NamedTuple):
    db: sqlite3.Connection
    row: ThreadRow

    @property
    def id(self) -> str:
        return self.row['uid']

    @property
    def name(self) -> str:
        name = self.row['name']
        if name is None:
            # TODO eh. must be group chat??
            return self.id
        return name

    @property
    def thread_id(self) -> str:
        # todo deprecate
        return self.id

    def iter_messages(self, order_by: str='timestamp') -> Iterator[Message]:
        for row in self.db.execute('SELECT * FROM messages WHERE thread_id=? ORDER BY ?', (self.thread_id, order_by)):
            yield Message(row=row, thread=self)


class DAL(ContextDecorator):
    def __init__(self, db_path: PathIsh) -> None:
        self.db = sqlite3.connect(f'file:{db_path}?immutable=1', uri=True)
        self.db.row_factory = sqlite3.Row

    def iter_threads(self, order_by: str='name') -> Iterator[Thread]:
        for row in self.db.execute('SELECT * FROM threads ORDER BY ?', (order_by, )):
            yield Thread(db=self.db, row=row)

    def __enter__(self) -> DAL:
        return self

    def __exit__(self, *exc) -> None:
        self.db.close()


def demo(dal: DAL) -> None:
    with dal:
        for t in dal.iter_threads():
            msgs = list(t.iter_messages())
            print(f"Conversation with {t.name}: {len(msgs)} messages")


if __name__ == '__main__':
    dal_helper.main(DAL=DAL, demo=demo, single_source=True)
