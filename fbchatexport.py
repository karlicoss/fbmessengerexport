#!/usr/bin/env python3
import argparse
from pathlib import Path
import json
import logging
import sys
from typing import List, Iterator, Union, TypeVar, Optional

import dataset # type: ignore

import fbchat # type: ignore
from fbchat import Client, Thread, Message, ThreadLocation


T = TypeVar('T')
Res = Union[T, Exception]

def get_logger():
    return logging.getLogger('fbchatexport')


def delk(d, key: str):
    if key in d:
        del d[key]

class ExportDb:
    def __init__(self, db_path: Path) -> None:
        self.db = dataset.connect('sqlite:///{}'.format(db_path))
        # TODO need to disconnect??
        self.ttable = self.db['threads']
        self.mtable = self.db['messages']

    def insert_thread(self, thread: Thread) -> None:
        dd = vars(thread)
        delk(dd, 'type') # user vs group? fine without it for now
        # TODO could remove remaining crap, e.g. color/emoji/plan, but for now don't bother

        # TODO FIMXE pkey/upsert??
        self.ttable.insert(dd)

    def insert_message(self, message: Message) -> None:
        dd = vars(message)
        # TODO FIMXE just store as sqlite json??
        # delete lists, not sure how to handle
        delk(dd, 'mentions')
        delk(dd, 'read_by')
        delk(dd, 'attachments') # TODO not sure, what if urls??
        delk(dd, 'quick_replies')
        delk(dd, 'reactions')

        delk(dd, 'replied_to') # we've got reply_to_id anyway

        self.mtable.insert(dd)


# doc doesn't say anything about cap and default is 20. for me 100 seems to work too
# https://fbchat.readthedocs.io/en/stable/api.html#fbchat.Client.fetchThreadMessages
FETCH_THREAD_MESSAGES_LIMIT = 100

def iter_thread(client: Client, thread: Thread) -> Iterator[Res[Message]]:
    """
    Returns messages in thread (from newest to oldest)
    """
    logger = get_logger()
    tid = thread.uid
    tname = thread.name

    last_ts = thread.last_message_timestamp
    # TODO not sure how reliable it is, but anyway.. should be consistent?
    limit = thread.message_count

    last_msg: Optional[Message] = None
    done = 0
    while done < limit:
        logger.debug('thread %s: fetching %d/%d', tname, done, limit)

        before = last_ts if last_msg is None else last_msg.timestamp
        chunk = client.fetchThreadMessages(tid, before=before, limit=FETCH_THREAD_MESSAGES_LIMIT)
        if len(chunk) == 0:
            # not sure if can happen??
            yield RuntimeError("Expected non-empty chunk")
            break

        if last_msg is not None:
            assert last_msg.uid == chunk[0].uid
            del chunk[0]

        yield from chunk
        done += len(chunk)
        last_msg = chunk[-1]


# TODO maybe a json for each user? I guess it's ok to start with..
# TODO atomic writes?
def process_all(client: Client, db: ExportDb) -> Iterator[Exception]:
    logger = get_logger()
    # TODO what is pending??
    locs = [ThreadLocation.INBOX, ThreadLocation.ARCHIVED]
    # TODO FIXME more defensive?
    # TODO shit, this def gonna need some sort of checkpointing...
    threads: List[Thread] = []
    for loc in locs:
        logger.debug('fetching threads: %s', loc)
        # fetches all threads by default
        thr = client.fetchThreads(loc)
        threads.extend(thr)

    # TODO save threads as well?
    # vars(thread)
    # vars(msg?)

    # TODO def should be defensive...
    # threads = threads[:1] + threads[2:3] # TODO FIXME 
    # threads = threads[:1] # TODO FIXME
    for thread in threads:
        db.insert_thread(thread)

        for r in iter_thread(client=client, thread=thread):
            if isinstance(r, Exception):
                logger.exception(r)
                yield r
            else:
                # TODO WAL?
                try:
                    db.insert_message(r)
                except Exception as e:
                    logger.exception(e)
                    # TODO FIXME
                    from IPython import embed; embed()


def run(*, cookies: str, db_path: Path):
    logger = get_logger()
    client = Client(
        'dummy_email',
        'dummy_password',
        session_cookies=json.loads(cookies),
    )

    db = ExportDb(db_path)

    errors = list(process_all(client=client, db=db))
    if len(errors) > 0:
        logger.error('Had errors during processing')
        sys.exit(1)


def main():
    logger = get_logger()
    from kython.klogging import setup_logzero
    setup_logzero(logger, level=logging.DEBUG) # TODO FIXME remove
    # logging.basicConfig(level=logging.INFO)

    # TODO move setup_logger there as well?
    from export_helper import setup_parser
    parser = argparse.ArgumentParser("Tool to export your personal Facebook chat/Messenger data")
    setup_parser(parser=parser, params=['cookies'])
    parser.add_argument('--db-path', type=Path, help='Path to result sqlite database with')
    args = parser.parse_args()

    params = args.params

    run(cookies=params['cookies'], db_path=args.db_path)

if __name__ == '__main__':
    main()


# TODO mention: asks for 2FA
# TODO shit, asks for 2FA again. wonder if can preserve session??
