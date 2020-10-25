#!/usr/bin/env python3
import argparse
from collections import OrderedDict
from pathlib import Path
import itertools
import json
import logging
import sys
from typing import List, Iterator, Union, TypeVar, Optional, Tuple

import dataset # type: ignore

import fbchat # type: ignore
### see https://github.com/fbchat-dev/fbchat/issues/615#issuecomment-710127001 
import re
fbchat._util.USER_AGENTS    = ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.75 Safari/537.36"]
fbchat._state.FB_DTSG_REGEX = re.compile(r'"name":"fb_dtsg","value":"(.*?)"')
###
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

    # TODO add explanations to readme of all deleted stuff?
    def insert_thread(self, thread: Thread) -> None:
        dd = vars(thread)
        delk(dd, 'type') # user vs group? fine without it for now
      
        col = 'color'
        c = dd[col]
        if c is not None:
            dd[col] = c.value # map from enum to value

        delk(dd, 'nicknames')
        delk(dd, 'admins')
        delk(dd, 'approval_requests')

        delk(dd, 'participants') # FIXME def would be nice to keep this one..

        lts = 'last_message_timestamp'
        dd[lts] = int(dd[lts]) # makes more sense for queries?
    
        delk(dd, 'plan') # it's unclear, why is this baked into the plan? and what if the plan changes?

        self.ttable.upsert(OrderedDict(sorted(dd.items())), ['uid'])

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

        self.mtable.upsert(OrderedDict(sorted(dd.items())), ['uid'])

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

    def check_fetched_all(self, thread: Thread) -> Iterator[Exception]:
        if 'messages' not in self.db.tables:
            return # meh, but works I guess

        query = 'SELECT COUNT(*) FROM messages WHERE thread_id={}'.format(thread.uid)
        [res] = list(self.db.query(query))
        cnt = res['COUNT(*)']
        if cnt != thread.message_count:
            yield RuntimeError('Expected {} messages in thread {}, got {}'.format(thread.message_count, thread.name, cnt))



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
    logger.info('thread %s: fetching messages before %s', tname, before)

    last_ts: int = thread.last_message_timestamp if before is None else before

    last_msg: Optional[Message] = None
    done = 0
    while True:
        logger.debug('thread %s: fetched %d starting from %s (total %d)', tname, done, last_ts, thread.message_count)

        before = last_ts if last_msg is None else last_msg.timestamp
        # TODO make this defensive? implement some logic for fetching gaps
        try:
            chunk = fetchThreadMessagesRetry(client, tid, before=before, limit=FETCH_THREAD_MESSAGES_LIMIT)
        except Exception as e:
            # could happen if there is some internal fbchat error. Not much we can do so we just bail.
            yield e
            break
            
        if len(chunk) == 0:
            # not sure if can actually happen??
            yield RuntimeError("Expected non-empty chunk")
            break

        if last_msg is not None:
            assert last_msg.uid == chunk[0].uid
            del chunk[0]

        if len(chunk) == 0:
            # TODO uhoh.. careful if chunk size is 1?
            break # hopefully means that there are no more messages to fetch?

        for m in chunk:
            if last_msg is not None:
                # paranoid assert because we rely on message ordering
                assert int(last_msg.timestamp) >= int(m.timestamp)
            yield m
            last_msg = m
            done += 1


def process_all(client: Client, db: ExportDb) -> Iterator[Exception]:
    logger = get_logger()

    locs = [
        ThreadLocation.ARCHIVED, # not sure what that means.. apparently groups you don't have access to anymore?
        ThreadLocation.INBOX,    # most of messages are here.
        ThreadLocation.OTHER,    # apparently, keeps hidden conversations? Although doesn't returl all of them for me...
        # ThreadLocation.PENDING, # what is it???
    ]
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
        # sadly, api only allows us to fetch messages from newest to oldest
        # that means that we have no means of keeping contiguous chunk of messages in the database,
        # and 'extending' it both ways
        # we can do extend if to the left (i.e. to the oldest)
        # but all newer messages have to be accumulated and written in a single transaction

        def error(e: Exception) -> Iterator[Exception]:
            logger.error('While processing thread %s', thread)
            logger.exception(e)
            yield e

        # this would handle both 'first import' properly and 'extending' oldest to the left if it wasn't None
        iter_oldest = iter_thread(client=client, thread=thread, before=oldest)
        for r in iter_oldest:
            if isinstance(r, Exception):
                yield from error(r)
            else:
                db.insert_message(thread, r)

        if newest is not None:
            # and we want to fetch everything until we encounter newest
            iter_newest = iter_thread(client=client, thread=thread, before=None)
            with db.db: # transaction. that's *necessary* for new messages to extend fetched data to the right
                for r in iter_newest:
                    if isinstance(r, Exception):
                        yield from error(r)
                    else:
                        mts = int(r.timestamp)
                        if newest > mts:
                            logger.info('%s: fetched all new messages (up to %s)', thread.name, newest)
                            break # interrupt, thus preventing from fetching unnecessary data
                        db.insert_message(thread, r)

        # TODO not if should be defensive? could be an indication of a serious issue...
        yield from db.check_fetched_all(thread)


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
    patch_marketplace(client=client)
    

    edb = ExportDb(db)

    errors = list(process_all(client=client, db=edb))

    if len(errors) > 0:
        logger.error('Had %d errors during export', len(errors))
        sys.exit(1)
    else:
        logger.info('Success!')


def main():
    logger = get_logger()
    from export_helper import setup_logger
    setup_logger(logger, level='DEBUG')
    setup_logger('backoff', level='DEBUG')

    parser = make_parser()
    args = parser.parse_args()

    if args.login:
        do_login()
        return

    params = args.params

    db = args.db; assert db is not None
    run(cookies=params['cookies'], db=db)


def make_parser():
    from export_helper import setup_parser, Parser
    parser = Parser('''
Export your personal Facebook chat/Messenger data into an sqlite database.

Main difference from "Download your information" export is that this tool can be run automatically and doesn't require remembering to go onto Facebook website, reentering password, downloading archive, etc.

Note that at the moment it exports *text only*, images or videos are not exported.
I recommend checking the database after initial export to make sure it contains everything you want from the tool! 
I cleaned up some things I assumed weren't useful from raw responses, but I could be misinterpreting something as I'm not a heavy Facebook user.
Feel free to open a github issue if you think something about storage should be changed.
'''.strip())
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


def patch_marketplace(client):
    """
    Marketplace messages aren't handled by fbchat at the moment, this hack makes the client skip them
    see https://github.com/carpedm20/fbchat/issues/408
    """
    logger = get_logger()

    orig_fn = client.graphql_requests
    def patched_graphql_requests(*queries, orig_fn=orig_fn):
        results = orig_fn(*queries)
        # patched = []
        for r in results:
            nodes = r.get("viewer", {}).get("message_threads", {}).get("nodes", [])
            if len(nodes) == 0:
                continue
            good = [n for n in nodes if n.get("thread_type") != "MARKETPLACE"]
            filtered_out = len(nodes) - len(good)
            if filtered_out > 0:
                # TODO would be nice to propagate the errors up properly and fail script with exit code 1?
                logger.warning("Filtered out %d threads of type MARKETPLACE. See https://github.com/carpedm20/fbchat/issues/408", filtered_out)
            r["viewer"]["message_threads"]["nodes"] = good
        return results
    client.graphql_requests = patched_graphql_requests


if __name__ == '__main__':
    main()


