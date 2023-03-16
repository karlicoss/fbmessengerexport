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


class ThreadHelper(NamedTuple):
    db: sqlite3.Connection
    thread: Thread

    def iter_messages(self, order_by: str='timestamp') -> Iterator[Message]:
        for row in self.db.execute('SELECT * FROM messages WHERE thread_id=? ORDER BY ?', (self.thread.id, order_by)):
            yield Message(row=row, thread=self.thread)


def _dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


class DAL(ContextDecorator):
    def __init__(self, db_path: PathIsh) -> None:
        self.db = sqlite3.connect(f'file:{db_path}?immutable=1', uri=True)
        self.db.row_factory = _dict_factory

    def iter_threads(self, order_by: str='name') -> Iterator[ThreadHelper]:
        for row in self.db.execute('SELECT * FROM threads ORDER BY ?', (order_by, )):
            thread = Thread(row)
            yield ThreadHelper(db=self.db, thread=thread)

    def __enter__(self) -> DAL:
        return self

    def __exit__(self, *exc) -> None:
        self.db.close()


def demo(dal: DAL) -> None:
    with dal:
        for t in dal.iter_threads():
            msgs = list(t.iter_messages())
            print(f"Conversation with {t.thread.name}: {len(msgs)} messages")


if __name__ == '__main__':
    dal_helper.main(DAL=DAL, demo=demo, single_source=True)
