#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Simplified chat demo for websockets.

Authentication, error handling, etc are left as an exercise for the reader :)
"""

import logging
import tornado.escape
import tornado.ioloop
import tornado.options
import tornado.web
import tornado.websocket
import os.path
import uuid
from collections import deque

from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)


class ChatRoom(object):
    rooms = {}
    cache_size = 200

    def __init__(self, name):
        self.name = name
        self.waiters = set()
        self.rooms[name] = self
        self.cache = deque(maxlen=self.cache_size)

    def __repr__(self):
        return "<ChatRoom name=%s>" % (self.name,)

    @classmethod
    def get_room(cls, name):
        room = cls.rooms.get(name)
        if room is None:
            room = cls.rooms[name] = cls(name)
        return room

    def join(self, handler):
        self.waiters.add(handler)

    def leave(self, handler):
        self.waiters.remove(handler)

    def talk(self, chat):
        self._update_cache(chat)
        self._send_updates(chat)

    def _update_cache(self, chat):
        self.cache.append(chat)

    def _send_updates(self, chat):
        logging.info("(%s) Sending message to %d waiters",
                     self.name, len(self.waiters))
        for h in self.waiters:
            try:
                h.write_message(chat)
            except:
                logging.error("Error sending message", exc_info=True)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
                #(r"/", MainHandler),
            (r"/chat/(.*)", ChatHandler),
            (r"/chatsocket/(.*)", ChatSocketHandler),
        ]
        settings = dict(
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            autoescape=None,
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class ChatHandler(tornado.web.RequestHandler):
    def get(self, room):
        self.render("chat.html",
                    messages=ChatSocketHandler.cache, room=room)

class ChatSocketHandler(tornado.websocket.WebSocketHandler):
    waiters = set()
    cache = []
    cache_size = 200

    def allow_draft76(self):
        # for iOS 5.0 Safari
        return True

    def open(self, name):
        self.room = ChatRoom.get_room(name)
        self.room.join(self)

    def on_close(self):
        self.room.leave(self)
        self.room = None

    def on_message(self, message):
        logging.info("got message %r", message)
        parsed = tornado.escape.json_decode(message)
        chat = {
            "id": str(uuid.uuid4()),
            "body": parsed["body"],
            }
        chat["html"] = self.render_string("message.html", message=chat)
        self.room.talk(chat)

def main():
    tornado.options.parse_command_line()
    app = Application()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()
