#!/usr/bin/env python3
import json

import fbchat

Cookies = str

def login(*, email: str, password: str) -> Cookies:
    # TODO check old cookies first??
    uag = fbchat._util.USER_AGENTS[0] # choose deterministic to prevent alerts from FB
    client = fbchat.Client(email=email, password=password, user_agent=uag)
    return json.dumps(client.getSession())


def main():
    import getpass
    email = input('email:')
    password = getpass.getpass('password:')
    # TODO FIXME input instead??
    cookies = login(email=email, password=password)
    print("Your cookies string (put it in 'cookies' variable in secrets.py):")
    print("'{}'".format(cookies))


if __name__ == '__main__':
    main()
