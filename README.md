Furnace Backend
=======

<img align="right" width=20% src="https://github.com/mbushou/furnace/blob/master/misc/logo_smoke_sm.png">

Introduction
-------
This is Furnace's tenant-side code.  It allows tenant VMI programmers to:
- Start and run VMI app backends that communicate with VMI apps at runtime.
- ~~Interact with Furnace API endpoints to manage VMI apps, retrieve app logs, etc.~~ (under development!)

Please see ./docs for the pydoc documentation.

For more information on the Furnace project, visit its [main repository](https://github.com/mbushou/furnace).

The installation instructions assume a Fedora 28 machine.

Installation
-------
```
# Install dependencies
sudo dnf install zeromq protobuf
sudo pip3 install zmq protobuf

# Clone the repo
git clone https://github.com/mbushou/furnace_backend
cd furnace_backend

# Compile the facilities protobuf
protoc --proto_path=. --python_out=. facilities.proto

# Create a ZMQ Curve keypair for the backend
cd apps
python3 -c "import zmq.auth; zmq.auth.create_certificates('.', 'furnace_be_keypair')"

# Create one or more ZMQ Curve keypairs the matching Furnace app
python3 -c "import zmq.auth; zmq.auth.create_certificates('.', 'furnace_app_keypair_1')"
```

Starting the backend.
You'll need to ensure TCP/5563 is reachable from the Furance sandbox running on
the compute node.  Unless you are running this backend on the compute node
itself, substitute 127.0.0.1 for the correct local (routable) address.
```
# runs the included bare-bones example backend (app_be.py)
./bemain.py -d \
    -c app_be \
    -m AppBE \
    --ep 127.0.0.1 \
    --et 5563 \
    --ak furnace_app_keypair_1.key_secret \
    --bk furnace_be_keypair.key_secret
```

License
-------
Furnace is GPLv3.

However, to use Furnace library with DRAKVUF, you must also comply with DRAKVUF's license.
Including DRAKVUF within commercial applications or appliances generally
requires the purchase of a commercial DRAKVUF license (see
https://github.com/tklengyel/drakvuf/blob/master/LICENSE).
