#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Collection, Iterator, List, Sequence, Optional

import dataset # type: ignore


from .exporthelpers import dal_helper
from .exporthelpers.dal_helper import PathIsh, datetime_aware
from .common import MessageRow, ThreadRow


class Message:
    def __init__(self, *, row: MessageRow, thread: Thread) -> None:
        self.row = row
        self.thread = thread

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


class Thread:
    def __init__(self, *, mt: dataset.Table, row: ThreadRow) -> None:
        self.row = row
        self.mt = mt

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
        for row in self.mt.find(thread_id=self.thread_id, order_by=order_by):
            yield Message(row=row, thread=self)


class DAL:
    def __init__(self, db_path: PathIsh) -> None:
        import sqlite3
        # https://www.sqlite.org/draft/uri.html#uriimmutable
        creator = lambda: sqlite3.connect(f'file:{db_path}?immutable=1', uri=True)
        self.db = dataset.connect('sqlite:///', engine_kwargs={'creator': creator})
        self.tt = self.db['threads']
        self.mt = self.db['messages']

    def iter_threads(self, order_by: str='name') -> Iterator[Thread]:
        for row in self.tt.all(order_by=order_by):
            yield Thread(mt=self.mt, row=row)


def demo(dal: DAL) -> None:
    for t in dal.iter_threads():
        msgs = list(t.iter_messages())
        print(f"Conversation with {t.name}: {len(msgs)} messages")


if __name__ == '__main__':
    dal_helper.main(DAL=DAL, demo=demo, single_source=True)
