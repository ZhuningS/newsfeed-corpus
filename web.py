#!/bin/env python3

""" Web server """

from datetime import datetime
from multiprocessing import cpu_count
from functools import lru_cache
from mako.template import Template
from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Sanic
from sanic.exceptions import FileNotFound, NotFound
from sanic.response import json, text, html
from config import log, DEBUG, BIND_ADDRESS, HTTP_PORT, MONGO_SERVER, DATABASE_NAME
from common import connect_redis, REDIS_NAMESPACE
from aiocache import cached, SimpleMemoryCache

app = Sanic(__name__)
layout = Template(filename='views/layout.tpl')

redis = None
db = None

@app.listener('after_server_start')
def init_connections(sanic, loop):
    global redis, db
    redis = connect_redis()
    motor = AsyncIOMotorClient(MONGO_SERVER, io_loop=loop)
    db = motor[DATABASE_NAME]


@app.route('/', methods=['GET'])
async def homepage(req):
    """Main page"""
    return html(layout.render(timestr=datetime.now().strftime("%H:%M:%S.%f")))


@app.route('/test', methods=['GET'])
async def get_name(req):
    return text("test")

@app.route('/status', methods=['GET'])
async def get_status(req):
    return json({
        "feed_count": await redis.hget(REDIS_NAMESPACE + 'status', 'feed_count'),
        "item_count": await redis.hget(REDIS_NAMESPACE + 'status', 'item_count')
    })


@app.route('/feeds/<order>', methods=['GET'])
@app.route('/feeds/<order>/<last_id>', methods=['GET'])
@cached(ttl=20)
async def get_feeds(req, order, last_id=None):
    limit = 50
    fields = {'_id': 1, 'title': 1, 'last_fetched': 1, 'last_status': 1}
    if last_id:
        data = await db.feeds.find({last_id < '_id'},
                                   fields).sort(order).limit(limit).to_list(limit)
    else:
        data = await db.feeds.find({},
                                   fields).sort(order).limit(limit).to_list(limit)
    return json(data)

app.static('/', './static')

log.debug("Beginning run.")
app.run(host=BIND_ADDRESS, port=HTTP_PORT, workers=cpu_count(), debug=DEBUG)
