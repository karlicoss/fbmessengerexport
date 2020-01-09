#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path
from typing import Collection, Dict, Iterator, List, Sequence, Union

import dataset # type: ignore


class Message:
    def __init__(self, row: Dict, thread: 'Thread') -> None:
        self.row = row
        self.thread = thread

    @property
    def dt(self) -> datetime:
        # TODO FIXME timezone??
        return datetime.utcfromtimestamp(self.row['timestamp'] / 1000)

    @property
    def text(self) -> str:
        # TODO opetional??
        return self.row['text']


class Thread:
    def __init__(self, mt: dataset.Table, row: Dict) -> None:
        self.row = row
        self.mt = mt

    @property
    def name(self) -> str:
        # TODO cache?
        name = self.row['name']
        if name is None:
            # TODO FIXME eh. must be group chat??
            return self.thread_id
        return name

    @property
    def thread_id(self) -> str:
        return self.row['uid']

    def iter_messages(self, order_by='timestamp') -> Iterator[Message]:
        for row in self.mt.find(thread_id=self.thread_id, order_by=order_by):
            yield Message(row=row, thread=self)


class DAL:
    def __init__(self, db_path: Union[Path, str]) -> None:
        self.db = dataset.connect('sqlite:///{}'.format(db_path))
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
    import dal_helper
    dal_helper.main(DAL=DAL, demo=demo, single_source=True)
