from flask import Flask, render_template, request, make_response, g
from redis import Redis
import os
import socket
import random
import json
import logging

# Steve Ivy <steveivy@gmail.com>
# http://monkinetic.com

from random import random
from socket import socket, AF_INET, SOCK_DGRAM

class StatsdClient(object):
    SC_TIMING = "ms"
    SC_COUNT = "c"
    SC_GAUGE = "g"
    SC_SET = "s"

    def __init__(self, host='localhost', port=8125):
        """
        Sends statistics to the stats daemon over UDP
        >>> from python_example import StatsdClient
        """
        self.addr = (host, port)

    def timing(self, stats, value):
        """
        Log timing information
        >>> client = StatsdClient()
        >>> client.timing('example.timing', 500)
        >>> client.timing(('example.timing23', 'example.timing29'), 500)
        """
        self.update_stats(stats, value, self.SC_TIMING)

    def gauge(self, stats, value):
        """
        Log gauges
        >>> client = StatsdClient()
        >>> client.gauge('example.gauge', 47)
        >>> client.gauge(('example.gauge41', 'example.gauge43'), 47)
        """
        self.update_stats(stats, value, self.SC_GAUGE)

    def set(self, stats, value):
        """
        Log set
        >>> client = StatsdClient()
        >>> client.set('example.set', "set")
        >>> client.set(('example.set61', 'example.set67'), "2701")
        """
        self.update_stats(stats, value, self.SC_SET)

    def increment(self, stats, sample_rate=1):
        """
        Increments one or more stats counters
        >>> client = StatsdClient()
        >>> client.increment('example.increment')
        >>> client.increment('example.increment', 0.5)
        """
        self.count(stats, 1, sample_rate)

    def decrement(self, stats, sample_rate=1):
        """
        Decrements one or more stats counters
        >>> client = StatsdClient()
        >>> client.decrement('example.decrement')
        """
        self.count(stats, -1, sample_rate)

    def count(self, stats, value, sample_rate=1):
        """
        Updates one or more stats counters by arbitrary value
        >>> client = StatsdClient()
        >>> client.count('example.counter', 17)
        """
        self.update_stats(stats, value, self.SC_COUNT, sample_rate)

    def update_stats(self, stats, value, _type, sample_rate=1):
        """
        Pipeline function that formats data, samples it and passes to send()
        >>> client = StatsdClient()
        >>> client.update_stats('example.update_stats', 73, "c", 0.9)
        """
        stats = self.format(stats, value, _type)
        self.send(self.sample(stats, sample_rate), self.addr)

    @staticmethod
    def format(keys, value, _type):
        """
        General format function.
        >>> StatsdClient.format("example.format", 2, "T")
        {'example.format': '2|T'}
        >>> formatted = StatsdClient.format(("example.format31", "example.format37"), "2", "T")
        >>> formatted['example.format31'] == '2|T'
        True
        >>> formatted['example.format37'] == '2|T'
        True
        >>> len(formatted)
        2
        """
        data = {}
        value = "{0}|{1}".format(value, _type)
        # TODO: Allow any iterable except strings
        if not isinstance(keys, (list, tuple)):
            keys = [keys]
        for key in keys:
            data[key] = value
        return data

    @staticmethod
    def sample(data, sample_rate):
        """
        Sample data dict
        TODO(rbtz@): Convert to generator
        >>> StatsdClient.sample({"example.sample2": "2"}, 1)
        {'example.sample2': '2'}
        >>> StatsdClient.sample({"example.sample3": "3"}, 0)
        {}
        >>> from random import seed
        >>> seed(1)
        >>> sampled = StatsdClient.sample({"example.sample5": "5", "example.sample7": "7"}, 0.99)
        >>> len(sampled)
        2
        >>> sampled['example.sample5']
        '5|@0.99'
        >>> sampled['example.sample7']
        '7|@0.99'
        >>> StatsdClient.sample({"example.sample5": "5", "example.sample7": "7"}, 0.01)
        {}
        """
        if sample_rate >= 1:
            return data
        elif sample_rate < 1:
            if random() <= sample_rate:
                sampled_data = {}
                for stat, value in data.items():
                    sampled_data[stat] = "{0}|@{1}".format(value, sample_rate)
                return sampled_data
        return {}

    @staticmethod
    def send(_dict, addr):
        """
        Sends key/value pairs via UDP.
        >>> StatsdClient.send({"example.send":"11|c"}, ("127.0.0.1", 8125))
        """
        # TODO(rbtz@): IPv6 support
        # TODO(rbtz@): Creating socket on each send is a waste of resources
        udp_sock = socket(AF_INET, SOCK_DGRAM)
        # TODO(rbtz@): Add batch support
        for item in _dict.items():
            udp_sock.sendto(":".join(item).encode('utf-8'), addr)

option_a = os.getenv('OPTION_A', "Cats")
option_b = os.getenv('OPTION_B', "Dogs")
hostname = socket.gethostname()

app = Flask(__name__)

gunicorn_error_logger = logging.getLogger('gunicorn.error')
app.logger.handlers.extend(gunicorn_error_logger.handlers)
app.logger.setLevel(logging.INFO)

def get_redis():
    if not hasattr(g, 'redis'):
        g.redis = Redis(host="redis", db=0, socket_timeout=5)
    return g.redis

@app.route("/", methods=['POST','GET'])
def hello():
    voter_id = request.cookies.get('voter_id')
    if not voter_id:
        voter_id = hex(random.getrandbits(64))[2:-1]

    vote = None

    if request.method == 'POST':
        redis = get_redis()
        vote = request.form['vote']
        app.logger.info('Received vote for %s', vote)
        data = json.dumps({'voter_id': voter_id, 'vote': vote})
        redis.rpush('votes', data)

    resp = make_response(render_template(
        'index.html',
        option_a=option_a,
        option_b=option_b,
        hostname=hostname,
        vote=vote,
    ))
    resp.set_cookie('voter_id', voter_id)
    return resp


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True, threaded=True)
