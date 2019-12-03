#!/usr/bin/env python3
import argparse
import json

import fbchat # type: ignore
from fbchat import Client


def run(cookies: str):
    client = Client(
        'dummy_email',
        'dummy_password',
        session_cookies=json.loads(cookies),
    )
    threads = client.fetchThreadList()
    print(threads)


def main():
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
