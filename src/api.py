#! /usr/bin/python
import os
import sys
import uuid
import multiprocessing
import argparse
import socket

import redis


def config():
    parser = argparse.ArgumentParser()
    parser.add_argument('--listening_port', default=0, type=int, help='Port where we listen to requests')
    parser.add_argument('--redis_host_url', type=str, help='URL pointing to our Redis instance')
    parser.add_argument('--send_topic', type=str,
                        help='Topic for messages sent by API layer to service layer')
    parser.add_argument('--broadcast_topic', type=str,
                        help='Topic for messages to be sent to all API instances')

    args = parser.parse_args()
    return args


class BadRequest(Exception):
    pass


class Listener:
    def __init__(self, config):
        self.listening_port = config.listening_port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("", config.listening_port))

        sys.stderr.write("Listening on: {}:{}\n".format(self.get_ip(), self.sock.getsockname()[1]))
        sys.stderr.flush()

        self.redis_host_url = config.redis_host_url
        self.send_topic = config.send_topic
        self.broadcast_topic = config.broadcast_topic

        if not self.redis_host_url:
            self.redis_host_url = os.environ['REDIS_URL']
        url, port = self.redis_host_url.split(':')
        self.redis_host = redis.Redis(host=url, port=port)

        self.connections = set()
        self.queue = multiprocessing.Queue()
        self.connection = None

        self.process_inbound = {
            'get': self.get_all,
            'set': self.set_name
        }

    @staticmethod
    def get_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

    def run(self):
        while True:
            self.sock.listen()
            self.connection, address = self.sock.accept()
            with self.connection:
                changes_process = multiprocessing.Process(target=self.emmit_changes)
                changes_process.start()
                while True:
                    # This is all we need, if message is larger we have an issue
                    data = self.connection.recv(1024)

                    try:
                        self.process_message(data.decode('ascii'))
                    except BadRequest:
                        self.connection.send('Bad request: {}\n'.format(data).encode('ascii'))

    def process_message(self, msg):
        try:
            return_data = self.process_inbound[msg[:3]](msg)
        except KeyError:
            self.return_bad_request_and_close()
            raise BadRequest

        if return_data:
            self.connection.send('{}\n'.format(return_data).encode('ascii'))

    def emmit_changes(self):
        pubsub = self.redis_host.pubsub()
        pubsub.subscribe(self.broadcast_topic)

        while True:
            if not self.queue.empty():
                host_msg = self.queue.get()

                if host_msg == 'exit':
                    return

            msg = pubsub.get_message(ignore_subscribe_messages=True)

            if msg:
                self.connection.send('{}\n'.format(msg['data']).encode('ascii'))

    def get_all(self, msg):
        id = str(uuid.uuid4())
        pubsub = self.redis_host.pubsub()

        pubsub.subscribe(id)
        if pubsub.listen().__next__()['data'] != 1:
            raise ConnectionError

        self.redis_host.publish(self.send_topic, '{{"type": "get", "client_id": "{}"}}'.format(id))
        return_data = pubsub.listen().__next__()['data']
        pubsub.unsubscribe(id)
        return return_data.decode('ascii')

    def set_name(self, msg):
        # first one is type. we obviously know that
        _, user, num = msg.split()

        try:
            num = int(num)
        except ValueError:
            raise BadRequest

        self.redis_host.publish(
            self.send_topic, '{{"type": "set", "user": "{}", "fav_num": {}}}'.format(user, num)
        )

    def return_bad_request_and_close(self):
        pass


if __name__ == "__main__":
    config = config()
    listener = Listener(config)

    listener.run()
