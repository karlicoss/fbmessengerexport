#!/usr/bin/env python3
import argparse
from pathlib import Path
import itertools
import json
import logging
import sys
from typing import List, Iterator, Union, TypeVar, Optional, Tuple

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
        self.ttable = self.db.get_table('threads' , primary_id='uid', primary_type=self.db.types.text)
        self.mtable = self.db.get_table('messages', primary_id='uid', primary_type=self.db.types.text)

    def insert_thread(self, thread: Thread) -> None:
        dd = vars(thread)
        delk(dd, 'type') # user vs group? fine without it for now
        # TODO could remove remaining crap, e.g. color/emoji/plan, but for now don't bother

        delk(dd, 'nicknames')
        delk(dd, 'admins')
        delk(dd, 'approval_requests')

        delk(dd, 'participants') # FIXME def would be nice to keep this one..

        lts = 'last_message_timestamp'
        dd[lts] = int(dd[lts]) # makes more sense for queries?

        self.ttable.upsert(dd, ['uid'])

    def insert_message(self, thread: Thread, message: Message) -> None:
        dd = vars(message)
        # TODO just store as sqlite json?? not sure if makes sense

        # delete lists, not sure how to handle
        delk(dd, 'mentions')
        delk(dd, 'read_by')
        delk(dd, 'attachments') # TODO not sure, what if urls??
        delk(dd, 'quick_replies')
        delk(dd, 'reactions')

        delk(dd, 'sticker') # Sticker type
        delk(dd, 'emoji_size') # EmojiType

        delk(dd, 'replied_to') # we've got reply_to_id anyway

        ts = 'timestamp'
        dd[ts] = int(dd[ts]) # makes more sense for queries?

        dd['thread_id'] = thread.uid

        self.mtable.upsert(dd, ['uid'])

    def get_oldest_and_newest(self, thread: Thread) -> Optional[Tuple[int, int]]:
        if 'messages' not in self.db.tables:
            return None # meh, but works I guess

        # TODO use sql placeholders?
        query = 'SELECT MIN(timestamp), MAX(timestamp) FROM messages WHERE thread_id={}'.format(thread.uid)
        [res] = list(self.db.query(query))
        mints = res['MIN(timestamp)']
        maxts = res['MAX(timestamp)']
        if mints is None:
            assert maxts is None
            return None
        return int(mints), int(maxts)

    def check_fetched_all(self, thread: Thread) -> None:
        if 'messages' not in self.db.tables:
            return # meh, but works I guess

        query = 'SELECT COUNT(*) FROM messages WHERE thread_id={}'.format(thread.uid)
        [res] = list(self.db.query(query))
        cnt = res['COUNT(*)']
        if cnt != thread.message_count:
            raise RuntimeError('Expected {} messages in thread {}, got {}'.format(thread.message_count, thread.name, cnt))



# doc doesn't say anything about cap and default is 20. for me 100 seems to work too
# https://fbchat.readthedocs.io/en/stable/api.html#fbchat.Client.fetchThreadMessages
FETCH_THREAD_MESSAGES_LIMIT = 100



import backoff # type: ignore

class RetryMe(Exception):
    pass


@backoff.on_exception(backoff.expo, RetryMe, max_time=10 * 60)
def fetchThreadMessagesRetry(client, *args, **kwargs):
    try:
        return client.fetchThreadMessages(*args, **kwargs)
    except fbchat.FBchatFacebookError as e:
        # eh, happens sometimes for no apparent reason? after a while goes away?
        # fbchat._exception.FBchatFacebookError: GraphQL error #None: Errors while executing operation "MessengerThreads": At Query.message_thread:MessageThread.messages:MessagesOfThreadConnection.page_info: Field implementation threw an exception. Check your server logs for more information. / None
        logger = get_logger()
        if 'Field implementation threw an exception' in str(e):
            # TODO not sure if this is better or relying on 'backoff' logger?
            # logger.exception(e)
            # logger.warning('likely not a real error, retrying..')
            raise RetryMe
        else:
            raise e


def iter_thread(client: Client, thread: Thread, before: Optional[int]=None) -> Iterator[Res[Message]]:
    """
    Returns messages in thread (from newer to older)
    """
    logger = get_logger()
    tid = thread.uid
    tname = thread.name

    last_ts: int = thread.last_message_timestamp if before is None else before

    last_msg: Optional[Message] = None
    done = 0
    while True:
        logger.debug('thread %s: fetched %d starting from %s (total %d)', tname, done, last_ts, thread.message_count)

        before = last_ts if last_msg is None else last_msg.timestamp
        # TODO make this defensive? implement some logic for fetching gaps
        chunk = fetchThreadMessagesRetry(client, tid, before=before, limit=FETCH_THREAD_MESSAGES_LIMIT)
        if len(chunk) == 0:
            # not sure if can actually happen??
            yield RuntimeError("Expected non-empty chunk")
            break

        if last_msg is not None:
            assert last_msg.uid == chunk[0].uid
            del chunk[0]

        if len(chunk) == 0:
            break # hopefully means that there are no more messages to fetch?

        yield from chunk
        done += len(chunk)
        last_msg = chunk[-1]


def process_all(client: Client, db: ExportDb) -> Iterator[Exception]:
    logger = get_logger()

    # TODO what is ThreadLocation.PENDING?
    locs = [ThreadLocation.INBOX, ThreadLocation.ARCHIVED]
    threads: List[Thread] = []
    for loc in locs:
        logger.debug('fetching threads: %s', loc)
        # fetches all threads by default
        thr = client.fetchThreads(loc)
        threads.extend(thr)

    for thread in threads:
        db.insert_thread(thread)

    for thread in threads:
        on = db.get_oldest_and_newest(thread)
        if on is None:
            oldest = None
            newest = None
        else:
            oldest, newest = on
        # the assumption is that everything in [newest, oldest] is already fetched

        # so we want to fetch [oldest: ] in case we've been interrupted before
        iter_oldest = iter_thread(client=client, thread=thread, before=oldest)

        # and we want to fetch everything until we encounter newest
        iter_newest = iter_thread(client=client, thread=thread, before=None)

        for r in itertools.chain(iter_oldest, iter_newest):
            if isinstance(r, Exception):
                logger.exception(r)
                yield r
            else:
                mts = int(r.timestamp)
                if newest is not None and oldest is not None and newest > mts > oldest:
                    logger.info('Fetched everything for %s, interrupting', thread.name)
                    break # interrupt, thus interrupting fetching unnecessary data
                db.insert_message(thread, r)

        # TODO not sure if that should be more defensive?
        db.check_fetched_all(thread)


def run(*, cookies: str, db: Path):
    logger = get_logger()
    uag = fbchat._util.USER_AGENTS[0] # choose deterministic to prevent alerts from FB
    client = Client(
        # rely on cookies for login
        'dummy_email',
        'dummy_password',
        user_agent=uag,
        session_cookies=json.loads(cookies),
    )

    edb = ExportDb(db)

    errors = list(process_all(client=client, db=edb))
    if len(errors) > 0:
        logger.error('Had errors during processing')
        sys.exit(1)
    else:
        logger.info('Success!')


def main():
    logger = get_logger()
    from kython.klogging import setup_logzero
    setup_logzero(logger, level=logging.DEBUG) # TODO FIXME remove
    setup_logzero(logging.getLogger('backoff'), level=logging.DEBUG)
    # logging.basicConfig(level=logging.DEBUG)

    parser = make_parser()
    args = parser.parse_args()

    if args.login:
        do_login()
        return

    params = args.params

    db = args.db; assert db is not None
    run(cookies=params['cookies'], db=db)


def make_parser():
    # TODO move setup_logger there as well?
    from export_helper import setup_parser, Parser
    parser = Parser('Export your personal Facebook chat/Messenger data')
    setup_parser(
        parser=parser,
        params=['cookies'],
    )
    parser.add_argument('--db', type=Path, help='Path to result sqlite database')
    parser.add_argument('--login', action='store_true', help='Pass when using for the first time to login and get cookies')
    return parser


def login(*, email: str, password: str):
    # TODO check old cookies first??
    uag = fbchat._util.USER_AGENTS[0] # choose deterministic to prevent alerts from FB
    client = fbchat.Client(email=email, password=password, user_agent=uag)
    return client.getSession()


# TODO hmm, 'app password' didn't work
def do_login():
    """
    Facebook doesn't have an API, so you'll have to use cookies.

    Ideally this step needs to be done once, after that just use cookies to access your data.

    Note that this step might prompt you for two factor auth.

    Also Facebook will likely *notify you about unusual login*, so make sure to approve it in
    [[https://www.facebook.com/settings?tab=security][security settings]].
    """
    import getpass
    email = input('email:')
    password = getpass.getpass("password (won't be stored):")
    # TODO FIXME input instead??
    cookies = login(email=email, password=password)
    print("Your cookies string (put it in 'cookies' variable in secrets.py):")
    print("'{}'".format(json.dumps(cookies)))


if __name__ == '__main__':
    main()
