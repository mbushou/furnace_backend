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

class App(object):

    def __init__(self, ctx):
        be.log('in be_pslist constructor')

        be.set_name('be_pslist')
        self.felist = {}

        e = {'event_type': be.TIMER, 'time_value': 10.0,  # seconds
             'callback': self.timer_callback}
        be.event_register(e)

        e = {'event_type': be.FE,
             'callback': self.be_callback}
        be.event_register(e)

        be.log('leaving be_pslist constructor')

    def shutdown(self):
        pass

    def be_callback(self, ctx):
        be.log('BE CALLBACK')
        be.log('    passed: {ctx}'.format(ctx=ctx))
        self.felist[ctx['ident']] = time.time()
        if ctx['sync'] == be.SYNC:
            be.log('returning "got it! %s"' % (ctx,))
            return 'got it! %s' % (ctx,)

    def timer_callback(self, ctx):
        be.log('TIMER CALLBACK')
        be.log('    passed: {ctx}'.format(ctx=ctx))

        msg = 'cmd:pslist'
        be.broadcast(msg)

        be.log(self.felist)
