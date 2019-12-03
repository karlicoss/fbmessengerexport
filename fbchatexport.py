#!/usr/bin/env python3

import fbchat # type: ignore
from fbchat import Client

def run():
    client = Client(email, password)

def main():
    run()

if __name__ == '__main__':
    pass

# TODO mention: asks for 2FA
# TODO shit, asks for 2FA again. wonder if can preserve session??

# TODO ok, so this fetches only top 20
# need a way to export all?
# https://fbchat.readthedocs.io/en/stable/examples.html#examples
# threads = client.fetchThreadList()
