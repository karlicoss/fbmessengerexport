#!/usr/bin/env python3
import argparse
import json
import logging
from typing import List, Iterator, Union, TypeVar, Optional

import fbchat # type: ignore
from fbchat import Client, Thread, Message, ThreadLocation


T = TypeVar('T')
Res = Union[T, Exception]

def get_logger():
    return logging.getLogger('fbchatexport')


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
        chunk = client.fetchThreadMessages(tid, before=before)
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


def iter_all(client: Client):
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

    # TODO def should be defensive...
    threads = threads[:1] + threads[2:3] # TODO FIXME 
    for thread in threads:
        messages: List[Message] = []
        for r in iter_thread(client=client, thread=thread):
            if isinstance(r, Exception):
                yield r
            else:
                messages.append(r)

    # from IPython import embed; embed()

def run(cookies: str):
    client = Client(
        'dummy_email',
        'dummy_password',
        session_cookies=json.loads(cookies),
    )
    list(iter_all(client=client)) # FIXME force it

def main():
    logger = get_logger()
    from kython.klogging import setup_logzero
    setup_logzero(logger, level=logging.DEBUG)
    # logging.basicConfig(level=logging.INFO)

    # TODO move setup_logger there as well?
    from export_helper import setup_parser
    parser = argparse.ArgumentParser("Tool to export your personal Facebook chat/Messenger data")
    setup_parser(parser=parser, params=['cookies'])
    args = parser.parse_args()

    params = args.params
    dumper = args.dumper

    # TODO FIXME not sure how feasible is json for people who have LOTS of messages
    # but that requires a whole different, incremental approach (e.g. like Telegram exporter)
    # j = get_json(**params)
    # js = json.dumps(j, ensure_ascii=False, indent=1)
    # dumper(js)

    run(cookies=params['cookies'])

if __name__ == '__main__':
    main()

# TODO mention: asks for 2FA
# TODO shit, asks for 2FA again. wonder if can preserve session??

# TODO ok, so this fetches only top 20
# need a way to export all?
# https://fbchat.readthedocs.io/en/stable/examples.html#examples
