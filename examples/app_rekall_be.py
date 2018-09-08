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

import furnace_backend as be
import time
import json
import zmq

class AppBE(object):

    def __init__(self, ctx):
        be.log('in rekall constructor')
        be.set_name('rekall')
        self.felist = {}
        self.rekall_cmds = [
            '/opt/rekall/bin/rekal -p /opt/kernels/rekall/win7ie11.rekall.json -f /home/furnace pslist',
            '/opt/rekall/bin/rekal -p /opt/kernels/rekall/win7ie11.rekall.json -f /home/furnace netscan',
            '/opt/rekall/bin/rekal -p /opt/kernels/rekall/win7ie11.rekall.json -f /home/furnace netstat',
            '/opt/rekall/bin/rekal -p /opt/kernels/rekall/win7ie11.rekall.json -f /home/furnace pstree',
            '/opt/rekall/bin/rekal -p /opt/kernels/rekall/win7ie11.rekall.json -f /home/furnace modscan',
            '/opt/rekall/bin/rekal -p /opt/kernels/rekall/win7ie11.rekall.json -f /home/furnace psxview',
        ]

        self.cycle_count = 1

        integration = True  # if True, starts up subscriber for external commands
        if integration:
            rekall_unix = 'ipc:///tmp/rekall'
            self.sub = be.bei.context.socket(zmq.SUB)
            self.sub.setsockopt(zmq.SUBSCRIBE, b'')
            self.sub.connect(rekall_unix)

            e = {'event_type': be.TIMER, 'time_value': 1.0,
                'callback': self.timer_callback}
            be.event_register(e)

        e = {'event_type': be.FE,
             'callback': self.fe_callback}
        be.event_register(e)

        be.log('leaving rekall constructor')

    #ctx = self.Context(ident=ident.decode(), sync=sync, message=val.decode())
    def fe_callback(self, ctx):
        be.log('FE CALLBACK')
        be.log(f'in: {ctx}')
        if ctx.sync == be.SYNC:  # the FE is blocking on our reply
            msg = f'ok: {id(ctx)}'
            be.log('returning: {msg}')
            return msg

        # msg format: {'cmd': 'foo', 'data': 'bar'}
        # ALL ASYNC
        # FE: hi, waiting, rekall_running, rekall_done
        # BE: rekall_cmd
        feid = ctx.ident
        msg = json.loads(ctx.message)
        record = self.felist.get(feid, {'last_contact': time.time(), 'state': None, 'cmd_index': 0})
        record['state'] = msg['cmd']

        if msg['cmd'] in ['hi', 'waiting']:
            if self.cycle_count > 0:
                self.cycle_count -= 1
                ix = (record['cmd_index'] + 1) % len(self.rekall_cmds)
                record['cmd_index'] = ix
                be.notify(feid, json.dumps({'cmd': 'rekall_cmd', 'data': self.rekall_cmds[ix]}))
            else:
                be.log('cycle_count < 1')

        elif msg['cmd'] in ['rekall_running']:
            be.log(f'{feid} rekall_running')

        elif msg['cmd'] in ['rekall_done']:
            results = msg['data']
            be.log(f'{feid} rekall_done: {results}')
            print(results)

        if feid not in self.felist:
            self.felist[feid] = record

    # ctx == 'timer triggered'
    def timer_callback(self, ctx):
        be.log('BE TIMER')
        try:
            cmd = self.sub.recv(flags=zmq.NOBLOCK)
            be.log(f'got command: {cmd}')
        except zmq.ZMQError:
            be.log('no msgs')

