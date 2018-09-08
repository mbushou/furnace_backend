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
#import hashlib
import binascii

import zlib

class AppBE(object):

    def __init__(self, ctx):
        be.log('in memdump constructor')
        be.set_name('memdump')
        self.felist = {}
        self.cycle_count = 1
        self.stime = 0.0
        self.zdo = zlib.decompressobj()
        self.decompressed_data = b''
        self.total_recv_bytes = 0
        self.ix_recv = {}

        be.event_register({'event_type': be.FE, 'callback': self.fe_callback})

        '''
        e = {'event_type': be.TIMER, 'time_value': 2.0,  # seconds
             'callback': self.timer_callback}
        be.event_register(e)
'''

        be.log('leaving memdump constructor')

    #ctx = self.Context(ident=ident.decode(), sync=sync, message=val.decode())
    def fe_callback(self, ctx):
        be.log('FE CALLBACK')
        if ctx.sync == be.SYNC:  # the FE is blocking on our reply
            msg = f'ok: {id(ctx)}'
            be.log('returning: {msg}')
            return msg

        # msg format: {'cmd': 'foo', 'data': 'bar'}
        # ALL ASYNC
        # FE: hi, waiting, memdump_running, memdump_done, error
        # BE: memdump_cmd: go, stop
        feid = ctx.ident
        msg = json.loads(ctx.message)
        record = self.felist.get(feid, {'last_contact': time.time(), 'state': None, 'bytes':b''})
        record['state'] = msg['cmd']

        if msg['cmd'] in ['hi', 'waiting']:
            if self.cycle_count > 0:
                self.cycle_count -= 1
                be.notify(feid, json.dumps({'cmd': 'memdump_cmd', 'data': 'go'}))
                self.stime = time.time()
            else:
                be.log('cycle_count < 1')

        elif msg['cmd'] in ['memdump_running']:
            be.log(f'{feid} memdump_running')

        elif msg['cmd'] in ['memdump']:

            res = ''
            compressed_size = 0

            for chunk in msg['data']:
                compressed_size += len(chunk)
                cres = self.zdo.decompress(binascii.a2b_base64(chunk.encode()))
                self.total_recv_bytes += len(cres)
                #res += cres

            #shahash = hashlib.sha256(res).hexdigest()
            #orighash = msg['hash']
            ix = msg['ix']
            try:
                self.ix_recv[feid].append(ix)
            except KeyError:
                self.ix_recv[feid] = [ix]

            be.log(f'{feid} got memdump ix={ix}:{compressed_size} -> {self.total_recv_bytes} B')
            #be.log(f'{feid} theirs={orighash}')
            #be.log(f'{feid} mine  ={shahash}')

            # TODO: for benchmarking, we dump the bytes right on the ground
            # instead, they could be saved to disk
            #record['bytes'] += res  # need to eventually bytes() this

            #recsize = len(record['bytes'])
            #be.log(f'{feid} current memdump: recordsize={recsize} B')

        elif msg['cmd'] in ['memdump_done']:
            rt = round(time.time()-self.stime,2)
            #rate = round((len(record['bytes'])/rt) / 1000000, 2)
            rate = round((self.total_recv_bytes/rt) / 1000000, 2)
            be.log(f'{feid} memdump finished')
            be.log(f'{feid} total_recv_bytes={self.total_recv_bytes}, runtime={rt}, rate={rate} MBps')
            be.log(f'{self.ix_recv}')
            be.log('exiting...')
            for feid in self.felist:
                be.log(f'telling {feid} to exit')
                be.notify(feid, json.dumps({'cmd': 'memdump_cmd', 'data': 'exit'}))
            be.exit()

        elif msg['cmd'] in ['error']:
            be.log(f'{feid} error: {msg["data"]}')

        if feid not in self.felist:
            self.felist[feid] = record

            '''
    # ctx == 'timer triggered'
    def timer_callback(self, ctx):
        be.log('BE TIMER')
        be.log(f'list of FEs: {self.felist}')
        for key in self.felist:
            if key[-1] == 'd':
                be.log(f'notifying {key}')
                be.notify(key, f'hi {key}')
'''
