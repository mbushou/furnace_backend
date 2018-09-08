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

# stdlib
import atexit
import signal
import time
import logging
import logging.handlers
import os
import sys

MAXLINE = 400  # number of chars to print on log msgs

class FurnaceRuntime(object):

    def __init__(self, debug=False):

        atexit.register(self.shutdown)
        self._time_start = time.time()
        self._pid = os.getpid()
        self.tick = 0
        self.msgin = 0
        self.msgout = 0
        self.name = 'unk'
        self.print_debug = debug

        self.start_logs()

        #signal.signal(signal.SIGINT, self.signal_handler)
        #signal.signal(signal.SIGTERM, self.signal_handler)


    def run(self):
        self.tprint('info', 'Starting event loop')

    def start_logs(self):

        self.logger = logging.getLogger(str(self._pid))  # Catch furnace messages
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')  # Set format.

        # Log file handler and formatting.
        #fh = logging.handlers.RotatingFileHandler('%s.log' % (self.name,), backupCount=10, maxBytes=33554432)  # 2^25 B
        #fh.setFormatter(formatter)
        #fh.setLevel(logging.INFO)
        #self.logger.addHandler(fh)  # Assign file handler to loggers.

        # Console handler.
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        print(f'setting debug logging to {self.print_debug}')
        ch.setLevel(logging.DEBUG) if self.print_debug else ch.setLevel(logging.INFO)
        self.logger.addHandler(ch)  # Assign console handler to loggers.


    def tprint(self, log_type, entry):
        output = '%s: %s' % (self.tick, entry)
        if log_type == 'debug':
            self.logger.debug(output[:MAXLINE])
        elif log_type == 'info':
            self.logger.info(output[:MAXLINE])
        elif log_type == 'notice':
            self.logger.info(output[:MAXLINE])
        elif log_type in ['warning', 'warn']:
            self.logger.warning(output[:MAXLINE])
        elif log_type in ['error', 'err']:
            self.logger.error(output[:MAXLINE])
        elif log_type in ['crit', 'critical']:
            self.logger.critical(output[:MAXLINE])


    def signal_handler(self, rcv_signal, frame):
        self.tprint('info', 'caught signal %s' % rcv_signal)
        if rcv_signal == signal.SIGINT:
            sys.exit(0)
        else:
            self.tprint('error', 'unregistered signal!')
            sys.exit(0)

    def shutdown(self):
        endtime = time.time()
        self.tprint('info', 'shutting down after %s ticks (%s sec), %s inbound and %s outbound messages' % (self.tick, round(endtime - self._time_start, 3), self.msgin, self.msgout))
        self.tprint('info', '%s msgs per second' % (round((self.msgin + self.msgout) / (endtime - self._time_start), 3)))
