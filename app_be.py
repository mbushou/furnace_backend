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


class AppBE(object):

    def __init__(self, ctx):
        """
        Tenant's backend constructor
        :param ctx: Currently unused, passed as an empty dict.
        """
        be.log('in example constructor')
        be.set_name('example_backend')
        self.felist = {}

        e = {'event_type': be.FE,
             'callback': self.fe_callback}
        be.event_register(e)

        e = {'event_type': be.TIMER, 'time_value': 2.0,  # seconds
             'callback': self.timer_callback}
        be.event_register(e)

        be.log('leaving example constructor')


    def fe_callback(self, ctx):
        """
        Called when messages arrive from apps
        :param ctx: a ctx named tuple collections.namedtuple('ctx', 'ident sync message')
             ident (string): ID of sending app.
             sync (bool): if True, the app is blocking on a response.
             message (string): Contents of message.
        :returns: a string reply to send to the app
        """
        be.log('BE CALLBACK')
        be.log(f'in: {ctx}')
        self.felist[ctx.ident] = time.time()
        if ctx.sync == be.SYNC:  # the FE is blocking on our reply
            msg = f'ok: {id(ctx)}'
            be.log('returning: {msg}')
            return msg


    def timer_callback(self, ctx):
        """
        Called on timer timeouts
        :param ctx: Presently unused, passes as a static "timer triggered" string
        :returns: Nothing.
        """
        be.log('BE TIMER')
        be.log(f'FEs I have seen: {self.felist}')
        for key, last_seen in self.felist.items():
            if key[-1] == 'd':
                be.log(f'notifying {key}')
                be.notify(key, f'hi {key}')
