#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path
from typing import Collection, Dict, Iterator, List, Sequence

import dataset # type: ignore


from .exporthelpers import dal_helper
from .exporthelpers.dal_helper import PathIsh


class Message:
    def __init__(self, row: Dict, thread: 'Thread') -> None:
        self.row = row
        self.thread = thread

    @property
    def id(self) -> str:
        return self.row['id']

    @property
    def dt(self) -> datetime:
        # ugh. feels like that it's returning timestamps with respect to your 'current' timezone???
        # this might give a clue.. https://github.com/fbchat-dev/fbchat/pull/472/files
        return datetime.fromtimestamp(self.row['timestamp'] / 1000)

    @property
    def text(self) -> str:
        # TODO optional??
        return self.row['text']


class Thread:
    def __init__(self, mt: dataset.Table, row: Dict) -> None:
        self.row = row
        self.mt = mt

    @property
    def name(self) -> str:
        name = self.row['name']
        if name is None:
            # TODO eh. must be group chat??
            return self.thread_id
        return name

    @property
    def id(self) -> str:
        return self.row['uid']

    @property
    def thread_id(self) -> str:
        # todo deprecate
        return self.id

    def iter_messages(self, order_by='timestamp') -> Iterator[Message]:
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

    def iter_threads(self, order_by='name') -> Iterator[Thread]:
        for row in self.tt.all(order_by=order_by):
            yield Thread(mt=self.mt, row=row)


def demo(dal: DAL):
    for t in dal.iter_threads():
        msgs = list(t.iter_messages())
        print(f"Conversation with {t.name}: {len(msgs)} messages")


if __name__ == '__main__':
    dal_helper.main(DAL=DAL, demo=demo, single_source=True)
