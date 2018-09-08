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
"""
Main Furnace backend library.  Exposes API to tenant code. Formats and sends IPC.
"""

import os
import time
import sys
import logging
from pprint import pformat as pf
from pprint import pprint as pp
import uuid
import re
import collections

# 3p
import zmq
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
from google.protobuf.internal import api_implementation

# internal
from constants import *
import furnace_runtime
import facilities_pb2

bei = None
broadcast = None
notify = None
event_register = None
event_clear = None
log = None
set_name = None
exit = None


class BE(furnace_runtime.FurnaceRuntime):
    """
    Main Furnace backend class.  Actions all API calls.
    """

    def __init__(self, kp, debug=False, be_ip='127.0.0.1', be_base_port=5561):
        """
        Constructor, ZMQ connections are built here.
        :param kp: The keypair to use, in the form {'be_key': '[path]', 'app_key': '[path]'}
        """

        super(BE, self).__init__(debug=debug)

        self.be_ip = be_ip
        self.be_base_port = be_base_port
        self.kp = kp
        self.name = 'UNK_BE'
        self.start_time = time.time()
        self.already_shutdown = False

        self.timerlist = {}
        self.next_tid = 0
        self.fe_info = None
        self.Context = collections.namedtuple('ctx', 'ident sync message')

        self.msg_in = facilities_pb2.FacMessage()
        self.msg_out = facilities_pb2.FacMessage()
        self.context = zmq.Context(io_threads=2)

        # crypto bootstrap
        auth = ThreadAuthenticator(self.context)
        auth.start()
        auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)

        pub_public, pub_secret = zmq.auth.load_certificate(kp['be_key'])
        sub_public, sub_secret = zmq.auth.load_certificate(kp['app_key'])

        TCP_BE_DLR = f'tcp://{self.be_ip}:{self.be_base_port+0}'
        TCP_BE_SUB = f'tcp://{self.be_ip}:{self.be_base_port+1}'

        # use this to receive and send messages to FEs
        self.dealer_be = self.context.socket(zmq.DEALER)
        # crypto start
        self.dealer_be.curve_publickey = pub_public
        self.dealer_be.curve_secretkey = pub_secret
        self.dealer_be.curve_server = True
        # crypto end
        self.tprint('info', f'PXY--BE: Binding as Dealer to {TCP_BE_DLR}')
        self.dealer_be.bind(TCP_BE_DLR)

        # outgoing pub messages to FEs
        self.pub_be = self.context.socket(zmq.PUB)
        # crypto start
        self.pub_be.curve_publickey = pub_public
        self.pub_be.curve_secretkey = pub_secret
        self.pub_be.curve_server = True
        # crypto end
        self.tprint('info', f'PXY--BE: Binding as Subscriber to {TCP_BE_SUB}')
        self.pub_be.bind(TCP_BE_SUB)

        self.poller = zmq.Poller()
        self.poller.register(self.dealer_be, zmq.POLLIN)


    def module_register(self):
        """
        Internal use only.
        Glues together namespaces.
        :returns: Nothing.
        """
        global bei
        global broadcast, notify
        global event_register, event_clear, log, set_name
        global request
        global exit
        bei = self
        broadcast = self.broadcast
        notify = self.notify
        #broadcast_py = self.broadcast_py
        #notify_py = self.notify_py
        event_register = self.event_register
        event_clear = self.event_clear
        log = self.log
        set_name = self.set_name
        exit = self.exit


    def post_app_init(self, app):
        """
        Internal use only.
        Called by bemain after the tenant backend's constructor runs.  Checks to ensure the constructor registered exactly one FE callback.
        :param app: The tenant's app instance.
        :returns: Nothing.
        :raises: Exception when caller attempts to register 2 or more FE callbacks.
        :raises: Exception when caller failed register any FE callback.
        """
        self.app = app
        be_ok = False
        for tk in self.timerlist:
            tv = self.timerlist[tk]
            if tv['event_type'] == FE:
                if be_ok:
                    raise Exception('Tenant backend cannot register more than one FE callback')
                fe_ok = True
        if not fe_ok:
            raise Exception('Tenant backend failed to register a FE callback')
        self.tprint('debug', 'post_app_init TIMERLIST:\n{timerlist}'.format(timerlist=pf(self.timerlist)))


    def loop(self):
        """
        Internal use only.
        Main event loop.  Polls (with timeout) on ZMQ sockets waiting for data from tenant apps.  Calls tenant-registered callbacks.
        :returns: Nothing.
        """
        cleanup_tids = list()

        while True:
            socks = dict(self.poller.poll(TIMEOUT_BE))

            # Message from a Frontend
            if self.dealer_be in socks:
                pkt = self.dealer_be.recv_multipart()
                self.msgin += 1
                if len(pkt) == 3:  # SYNC message, FE is blocked until our reply
                    sync = SYNC
                    ident, empty, raw_msg = pkt
                    self.msg_in.ParseFromString(raw_msg)

                    index = 0
                    submsg_list = getattr(self.msg_in, 'be_msg')
                    val = submsg_list[index].value
                    ctx = self.Context(ident=ident.decode(), sync=sync, message=val.decode())
                    '''
                    cb_data = {'ident': ident.decode(),
                               'sync': sync,
                               'message': val.decode()}
                    ret_data = self.fe_info['callback'](cb_data)
                    '''
                    ret_data = self.fe_info['callback'](ctx)
                    self.check_encoding(ret_data)

                    self.msg_out.Clear()
                    msgnum = self.msg_out.__getattribute__('BE_MSG_RET')
                    self.msg_out.type.append(msgnum)
                    submsg = getattr(self.msg_out, 'be_msg_ret').add()
                    submsg.status = VMI_SUCCESS
                    submsg.value = str(ret_data)
                    raw_out = self.msg_out.SerializeToString()

                    self.tprint('debug', 'sending %dB sync to %s' % (len(raw_out), ident))
                    self.dealer_be.send_multipart([ident, b'', raw_out])
                    self.msgout += 1

                elif len(pkt) == 2:  # ASYNC message from FE
                    sync = ASYNC
                    ident, raw_msg = pkt
                    self.msg_in.ParseFromString(raw_msg)

                    index = 0
                    submsg_list = getattr(self.msg_in, 'be_msg')
                    val = submsg_list[index].value
                    '''
                    cb_data = {'ident': ident.decode(),
                               'sync': sync,
                               'message': val}
                    ret_data = self.fe_info['callback'](cb_data)
                    '''
                    ctx = self.Context(ident=ident.decode(), sync=sync, message=val)
                    self.fe_info['callback'](ctx)

            curtime = time.time()
            for tk in self.timerlist:
                tv = self.timerlist[tk]

                if tv['status'] != ACTIVE:
                    cleanup_tids.append(ek)
                    continue

                if tv['event_type'] == TIMER \
                        and tv['last_called'] + tv['time_value'] < curtime:
                    tv['last_called'] = curtime
                    d = 'timer triggered'
                    tv['callback'](d)

            while len(cleanup_tids):
                del self.timerlist[cleanup_tids.pop()]

            self.tick += 1

    #---------------------------------------------

    def check_encoding(self, val):
        """
        Internal use only.
        Fun.  Now with more Unicode.
        :param val: Is this variable a string?
        :returns: Nothing.
        :raises: TypeError if val is not a string.
        """
        if not isinstance(val, str):
            raise TypeError('Error: value is not of type str')


    def mmsg_helper(self, msgtype):
        """
        Internal use only.
        Helper function to add another repeated field to a protobuf.
        :param msgtype: string matching the name of a field (see .proto for valid field names)
        :returns: The submsg, ready to be populated.
        """
        self.msg_out.Clear()
        msgnum = self.msg_out.__getattribute__(msgtype)
        self.msg_out.type.append(msgnum)
        submsg = getattr(self.msg_out, msgtype.lower()).add()
        return submsg


    def msg_helper(self, msgtype):
        """
        Internal use only.
        Helper function to add a single field to a protobuf.
        :param msgtype: string matching the name of a field (see .proto for valid field names)
        :returns: The submsg, ready to be populated.
        """
        self.msg_out.Clear()
        msgnum = self.msg_out.__getattribute__(msgtype)
        self.msg_out.type.append(msgnum)
        submsg = getattr(self.msg_out, msgtype.lower())
        return submsg


    def send_default_reply(self):
        """
        Internal use only.
        Helper function to send a prepared protobuf (self.msg_out), then block until a response is returned.
        :returns: Nothing.
        """
        self.req_fac.send(self.msg_out.SerializeToString())
        self.msgout += 1
        self.msg_out.Clear()
        self.msg_out.ParseFromString(self.req_fac.recv())
        self.msgin += 1
        return


    def mget_status_result(self, msgtype, index):
        """
        Internal use only.
        Helper function to retrieve the result and status of an inbound protobuf.
        :param msgtype: String matching the name of a field (see .proto for valid field names).
        :param index: Which index (for repeated fields)?
        :returns: Tuple of (status, result).
        """
        submsg_list = getattr(self.msg_out, msgtype.lower()+'_ret')
        status = int(submsg_list[index].status)
        result = submsg_list[index].result
        return status, result


    def mget_status(self, msgtype, index):
        """
        Internal use only.
        Helper function to retrieve the status of an inbound protobuf.
        :param msgtype: String matching the name of a field (see .proto for valid field names).
        :param index: Which index (for repeated fields)?
        :returns: status
        """
        submsg_list = getattr(self.msg_out, msgtype.lower()+'_ret')
        status = int(submsg_list[index].status)
        return status


    def get_status_result(self, msgtype):
        """
        Internal use only.
        Helper function to retrieve the result and status of an inbound protobuf.
        :param msgtype: String matching the name of a field (see .proto for valid field names).
        :returns: Tuple of (status, result).
        """
        submsg_list = getattr(self.msg_out, msgtype.lower()+'_ret')
        status = int(submsg_list.status)
        result = int(submsg_list.result)
        return status, result


    def get_status(self, msgtype):
        """
        Internal use only.
        Helper function to retrieve the status of an inbound protobuf.
        :param msgtype: String matching the name of a field (see .proto for valid field names).
        :param index: Which index (for repeated fields)?
        :returns: status
        """
        submsg_list = getattr(self.msg_out, msgtype.lower()+'_ret')
        status = int(submsg_list.status)
        return status

    #---------------------------------------------

    def broadcast(self, msg):
        """
        Supported API call.
        Send an async message to all registered tenant apps.  Uses the ZMQ publisher channel.  Immediately returns regardless of delivery.
        :param msg: String to send.
        :returns: Nothing.
        """
        self.check_encoding(msg)
        msgtype = 'BE_MSG'
        submsg = self.mmsg_helper(msgtype)
        submsg.status = VMI_SUCCESS
        submsg.value = str(msg).encode()
        self.pub_be.send(self.msg_out.SerializeToString())
        self.msgout += 1
        self.tprint('debug', 'sending broadcast')


    def notify(self, feid, msg):
        """
        Supported API call.
        Send an async message to a single registered tenant app.  Immediately returns regardless of delivery.
        :param feid: String matching desired app's ID.
        :param msg: String to send.
        :returns: Nothing.
        """
        self.check_encoding(msg)
        self.check_encoding(feid)
        msgtype = 'BE_MSG'
        submsg = self.mmsg_helper(msgtype)
        submsg.status = VMI_SUCCESS
        submsg.value = msg.encode()
        raw_out = self.msg_out.SerializeToString()
        self.dealer_be.send_multipart([feid.encode(), raw_out])
        self.msgout += 1
        self.tprint('debug', 'sending %dB message to %s' % (len(raw_out), feid))


    def event_register(self, edata):
        """
        Supported API call.
        Register a callback for a certain event.
        :param edata: A dict containing registration info, including the following key:value pairs.
            'event_type': Event type constant, see constants.py.
            'callback': Tenant function pointer to call when matching event arrives.
            if event_type == TIMER, also include these key:value pairs:
                'time_value': (float) call this callback every X seconds.
        :returns: event ID.  Can be later used to clear this event.
        :raises: Exception for unknown event type.
        :raises: Generic catchall failure (this should never occur).
        """

        callback = edata.pop('callback')
        etype = edata.pop('event_type')
        candidate = {'event_type': etype,
                     'callback': callback,
                     'status': ACTIVE}

        if etype == FE:
            tid = self.next_tid
            self.next_tid += 1
            self.timerlist[tid] = candidate
            self.fe_info = candidate
            return tid

        elif etype == TIMER:
            tid = self.next_tid
            self.next_tid += 1
            candidate['time_value'] = float(edata.pop('time_value'))
            candidate['last_called'] = 0.0
            self.timerlist[tid] = candidate
            return tid

        else:
            raise Exception('unknown event_type')

        raise Exception('failed to register event')  # catchall


    def event_clear(self, unsafe_tid):
        """
        Supported API call.
        Clear a callback for a certain event.
        :param tid: Event ID, returned from event_register.
        :returns: Nothing.
        :raises: Exception for an unknown timer.
        :raises: Exception if the caller attempts to clear the FE callback.
        """
        tid = int(unsafe_tid)
        try:
            e = self.timerlist[tid]
        except KeyError:
            raise Exception(f'unknown timer id: {tid}')

        if e['event_type'] == TIMER:
            self.timerlist[tid]['status'] = INACTIVE
            return True

        elif e['event_type'] == FE:
            raise Exception('cannot unregister from FE event source')


    def log(self, data):
        """
        Supported API call.
        :param data: Write this data to the backend's logging mechanism.
        :returns: Nothing.
        """
        self.tprint('info', str(data))


    def set_name(self, name):
        """
        Supported API call.
        :param name: The backend's name (must be alphanum and <=16 characters).
        :returns: Nothing.
        :raises: Exception if malformed.
        """
        self.check_encoding(name)
        if 0 < len(name) < 17 \
                and re.match('^[\w-]+$', name):
            self.name = name
            self.tprint('debug', 'setting app name to %s' % (name,))
            return

        raise Exception('could not set app name, must be alphanum,-,_ and 0 < len(name) < 17')


    def exit(self):
        """
        Supported API call.
        Exit without tearing down.
        :returns: Nothing.
        """
        time.sleep(1)  # briefly wait to clear msg queues
        sys.exit()


    def shutdown(self):
        """
        Supported API call.
        Exit cleanly.
        :returns: Nothing.
        """
        if self.already_shutdown:
            self.tprint('error', 'already shutdown?')
            return

        self.already_shutdown = True
        self.tprint('warn', 'shutting down')
        try:
            self.app.shutdown()
        except:
            self.tprint('err', 'error during app shutdown')
            pass
        self.poller.unregister(self.dealer_be)
        self.pub_be.close()
        self.dealer_be.close()
        self.context.destroy()
        super(BE, self).shutdown()
