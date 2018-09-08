#!/usr/bin/python3 -EOO

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
Command line interface to start a tenant backend.
"""

# stdlib
import sys
import argparse
import os

# furnace
import furnace_backend as be

def main():
    """
    Parses command line input, sets up env, then runs the tenant's desired backend.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', dest='component', default='app_be', metavar='component',
                        help='Component FILE without the .py extension, i.e., for app_be.py this would be app_be (default: app_be)')
    parser.add_argument('-m', dest='module', default='AppBE', metavar='module',
                        help='Python MODULE inside that file (default: AppBE)')
    parser.add_argument('-d', dest='debug', default=False, action='store_true',
                        help='Enable debugging to console')
    parser.add_argument('--ep', dest='be_ip', required=True, metavar='be_ip',
                        help='IP of backend')
    parser.add_argument('--et', dest='be_base_port', required=True, type=int, metavar='be_base_port',
                        help='Base port of backend to connect to (RTR, PUB, ->DLR<-, SUB)')
    parser.add_argument('--ak', dest='ak', required=True, metavar='appkey',
                        help='The Curve public key used by any connecting VMI apps')
    parser.add_argument('--bk', dest='bk', required=True, metavar='bekey',
                        help='The Curve public and private keys for this backend')
    args = parser.parse_args()
    print(f'{"#"*10}\nmain, starting Backend with args: {args}\n{"#"*10}')

    if not os.path.isfile(args.ak) \
        or not os.path.isfile(args.bk):
        print(f'ERROR: either {args.ak} or {args.bk} is missing!')
        sys.exit()
    kp = {'be_key': args.bk,
          'app_key': args.ak}
    print(f'startup: keys OK')

    target_component = args.component
    target_module = args.module

    bei = be.BE(kp, debug=args.debug, be_ip=args.be_ip, be_base_port=args.be_base_port)
    bei.module_register()

    # unused for now, but could be used to pass metadata into the tenant's backend constructor.
    ctx = {}

    comp = __import__(target_component, fromlist=[target_module])
    appClass = getattr(comp, target_module)
    app = appClass(ctx)

    bei.post_app_init(app=app)
    bei.loop()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('caught keyboard interrupt')
