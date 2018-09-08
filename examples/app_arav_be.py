#-------------------------
# Furnace (c) 2017-2018 Micah Bushouse
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------

import be
import time
import json
import zmq


class AppBE(object):

    def __init__(self, ctx):
        be.log('in arav be constructor')
        be.set_name('arav')
        self.felist = {}

        be.log('connecting to main')
        #self.main_ctx = zmq.Context()

        arav_unix = 'ipc:///tmp/arav'
        self.pub = be.bei.context.socket(zmq.PUB)
        r = self.pub.connect(arav_unix)
        be.log(f'connected: {r}')
        self.pub.send(b'hello from arav!')

        e = {'event_type': be.FE,
             'callback': self.fe_callback}
        be.event_register(e)

        e = {'event_type': be.TIMER, 'time_value': 2.0,  # seconds
             'callback': self.timer_callback}
        be.event_register(e)

        be.log('leaving arav constructor')

    #ctx = self.Context(ident=ident.decode(), sync=sync, message=val.decode())
    def fe_callback(self, ctx):
        be.log('FE CALLBACK')
        be.log(f'in: {ctx}')
        if ctx.sync == be.SYNC:  # the FE is blocking on our reply
            msg = f'ok: {id(ctx)}'
            be.log('returning: {msg}')
            return msg

        feid = ctx.ident
        msg = json.loads(ctx.message)
        record = self.felist.get(feid, {'last_contact': time.time(), 'state': None, 'cmd_index': 0})

        if feid not in self.felist:
            self.felist[feid] = record

        be.log(f'{self.felist}')
        be.log(f'sending to main')
        self.pub.send(json.dumps(ctx._asdict()).encode())

    def timer_callback(self, ctx):
        be.log('timer_callback')
        self.pub.send(b'arav heartbeat')

