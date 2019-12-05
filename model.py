#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Collection, Dict, Iterator, List, Sequence, Union

import dataset # type: ignore


class Message:
    def __init__(self, row: Dict) -> None:
        self.row = row


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
            yield Message(row)


class Model:
    def __init__(self, db_path: Union[Path, str]) -> None:
        self.db = dataset.connect('sqlite:///{}'.format(db_path))
        self.tt = self.db['threads']
        self.mt = self.db['messages']

    def iter_threads(self, order_by='name') -> Iterator[Thread]:
        # TODO FIXME order_by??
        for row in self.tt.all(order_by=order_by):
            yield Thread(mt=self.mt, row=row)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--db', type=Path, required=True)
    args = p.parse_args()

    model = Model(db_path=args.db)
    for t in model.iter_threads():
        msgs = list(t.iter_messages())
        print(f"Thread {t.name}: {len(msgs)} messages")


if __name__ == '__main__':
    main()
