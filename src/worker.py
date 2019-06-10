#! /usr/bin/python
import os

import redis
import json
import argparse

"""
This module serves as lowest layer in our system, tasked with accepting messages regarding user 
changes, storing data about those users to Redis, and broadcasting messages when and if appropriate.
"""


class BadMessageException(Exception):
    pass


def config():
    parser = argparse.ArgumentParser()
    parser.add_argument('--redis_host_url', type=str, help='URL pointing to our Redis instance')
    parser.add_argument('--listen_topic', type=str, help='Topic for messages sent by API layer')
    parser.add_argument('--broadcast_topic', type=str,
                        help='Topic for messages to be sent to all API instances')
    args = parser.parse_args()
    return args


class Worker:
    def __init__(self, config):
        self.redis_host_url = config.redis_host_url
        self.listen_topic = config.listen_topic
        self.broadcast_topic = config.broadcast_topic

        if not self.redis_host_url:
            self.redis_host_url = os.environ['REDIS_URL']

        url, port = self.redis_host_url.split(':')
        self.redis_host = redis.Redis(host=url, port=port)

        self.redis_actions = {
            'set': self.set_user_action,
            'get': self.get_users_action
        }

        self.post_actions = {
            'set': self.post_set,
            'get': self.post_get
        }

    def listen_to_msgs(self):
        pubsub = self.redis_host.pubsub()
        pubsub.subscribe(self.listen_topic)

        for msg in pubsub.listen():
            self.process_msg(msg)

    def process_msg(self, msg):
        if msg['data'] == 1:
            # connected to topic
            return

        converted_msg = json.loads(msg['data'].decode('ascii'))

        try:
            result = self.redis_actions[converted_msg['type']](converted_msg)
        except KeyError:
            raise BadMessageException

        self.post_actions[converted_msg['type']](result)

    def set_user_action(self, converted_msg):
        if "user" not in converted_msg.keys():
            raise BadMessageException

        if 'fav_num' not in converted_msg.keys():
            raise BadMessageException

        self.redis_host.set(converted_msg['user'], converted_msg['fav_num'])

    def get_users_action(self, converted_msg):
        # Will need to include information about client somehow
        try:
            client_id = converted_msg['client_id']
        except KeyError:
            raise BadMessageException

        return client_id, self.get_users()

    def post_set(self, result):
        all_users_and_nums = self.get_users()
        all_users_and_nums_for_redis = str(list(all_users_and_nums))
        self.redis_host.publish(self.broadcast_topic, all_users_and_nums_for_redis)

    def post_get(self, result):
        client_id, all_users_and_nums = result
        all_users_and_nums_for_redis = str(list(all_users_and_nums))
        self.redis_host.publish(client_id, all_users_and_nums_for_redis)

    def get_users(self):
        """
         Think of what to pass in message to identify client
         on the other side
        """

        # as far as I understood from searching and documentation, there is no way
        # for redis to return sorted list of keys, so we'll have to do it ourselves

        # As this may become unwieldy for large batches (I guess >1M let's say), at some point
        # we'd want to batch this
        all_sorted_keys = sorted(self.redis_host.keys('*'))

        for key in all_sorted_keys:
            value = self.redis_host.get(key)
            yield (key, value)


if __name__ == "__main__":
    c = config()
    w = Worker(c)

    w.listen_to_msgs()
