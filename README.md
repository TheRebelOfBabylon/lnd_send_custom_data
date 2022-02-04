# Send Custom Data with LND
Do you like Sphinx Chat? Do you think Impervious is pretty cool? Ever wondered how they manage to use the Lightning Network to send custom data? Look no further, this repo explains how you too can do it.

# How To Guide

## Step 1: Setup a couple of Simnet nodes

We want don't want to use actual sats right now since this is just a proof-of-concept. You can either follow the tutorial [here](https://dev.lightning.community/tutorial/01-lncli/index.html) or spin up a simnet with [Polar](https://lightningpolar.com). I haven't had the chance to fully dive into Polar, so I will just follow the tutorial. If someone wants to do this in Polar, feel free to make a merge request and I'll gladly add a section describing how to do it with Polar. 

I recommend compiling LND from source instead of downloading binaries because we are gonna run some custom install flags to make certain RPC endpoints available.
```
$ git clone git@github.com:lightningnetwork/lnd.git
$ cd lnd
$ git checkout v0.14.2-beta                                             #Use latest release
$ make && make install tags="signrpc walletrpc chainrpc invoicesrpc"
```
Don't forget to either modify `lnd.conf` and uncomment `accept-amp=true` or set the flag when running the `lnd` command: `$ lnd --accept-amp`. Once your Alice, Bob and Charlie are connected and have a couple of channels with simnet sats between them, it's time to write some code.

## Step 2: Making a virtual-environemnt and installing necessary dependencies

I am copying the `python.md` file from the `docs/grpc` directory in LND. Make yourself a virtual-environemnt `$ python3 -m venv venv`, activate it `$ source venv/bin/activate` and make a directory called `protos`: `(venv) $ mkdir protos && cd protos`.
Install the following:
```
(venv) $ pip install grpcio grpcio-tools googleapis-common-protos
(venv) $ git clone https://github.com/googleapis/googleapis.git
(venv) $ curl -o lightning.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/master/lnrpc/lightning.proto
(venv) $ curl -o router.proto -s https://raw.githubusercontent.com/lightningnetwork/lnd/master/lnrpc/routerrpc/router.proto
```
Then we will generate the python stubs.
```
(venv) $ python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. lightning.proto
(venv) $ python -m grpc_tools.protoc --proto_path=googleapis:. --python_out=. --grpc_python_out=. router.proto
```
Because our stubs are in the `protos` folder, we need to edit the generated files to import properly.
`lightning_pb2_grpc.py`
```
import protos.lightning_pb2 as lightning__pb2
```
`router_pb2.py`
```
import protos.lightning_pb2 as lightning__pb2
```
`router_pb2_grpc.py`
```
import protos.lightning_pb2 as lightning__pb2
import protos.router_pb2 as router__pb2
```

## Step 3: SendPaymentV2

Let's create the script that will send a payment with a custom record attached.
`send_msg.py`
```
import protos.router_pb2 as router
import protos.router_pb2_grpc as routerrpc
import grpc
import os
import codecs

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handhsake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

with open(os.path.expanduser('~/go/dev/alice/data/chain/bitcoin/simnet/admin.macaroon'), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

cert = open(os.path.expanduser('~/Library/Application Support/Lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10001', creds)
stub = routerrpc.RouterStub(channel)
for resp in stub.SendPaymentV2(router.SendPaymentRequest(
     dest=bytes.fromhex("02bd54561cb8d140703e57a9ea2cd4dccbf6fba6cbfaeaf352a8e8d96c1f7c9486"),
     amt=1,
     timeout_seconds=15,
     fee_limit_sat=1000000,
     dest_custom_records={
         400000: bytes("test", 'utf-8')
     },
     amp=True,
 ), metadata=[('macaroon', macaroon)]):
     print(resp)
```
There are a couple of key things to mention. One, we are using the `routerrpc` rpc method `SendPaymentV2` as opposed to the deprecated `SendPayment`. I'm fairly certain it would work with `SendPayment` after examining the code as `SendPaymentV2` just seems to be optimized for concurrency. We also must specify `amp=true` otherwise, it will fail. Now the really important thing to notice is all we have to do to set a custom record is set `dest_custom_records`. That's it. The available literature around this topic makes it seem like you have to build your own HTLCs and then attach the custom data in the `lnwire` message in TLV format, but thankfully `lnd` has built a simple API that takes care of all of this for us. 

It's important that any custom record have a key value greater than `65536` as any key value below this has been reserved. A reasonably high fee limit must also be set to pay for the routing fee otherwise, the payment can't be sent.

## Step 4: SubscribeInvoices

Whenever we attach a custom record to a payment, the receiver will not reject it thankfully. No kind of base code modifications need be done nor special configuration parameters need be set. All we need to do is to use the `SubscribeInvoices()` rpc method which is just a server->client uni-directional stream.
`recv_msg.py`
```
import protos.lightning_pb2 as ln
import protos.lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handhsake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

with open(os.path.expanduser('~/go/dev/charlie/data/chain/bitcoin/simnet/admin.macaroon'), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

cert = open(os.path.expanduser('~/Library/Application Support/Lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10003', creds)
stub = lnrpc.LightningStub(channel)
for resp in stub.SubscribeInvoices(ln.InvoiceSubscription(), metadata=[('macaroon', macaroon)]):
    for htlc in resp.htlcs:
        print(htlc.custom_records[400000].decode('utf-8'))
```
So here we listen for any new payments that node encounters and will print the `400000` custom record value in the htlcs array. Pretty simple stuff. Now Let's test it.

## Step 5: Testing It

`recv_msg.py`
```
(venv) $ python recv_msg.py
test
^C
(venv) $
```
`send_msg.py`
```
(venv) $ python send_msg.py
payment_hash: "c04317014e61c27e3ade9b9e0bedb16237b12a7b50cc92c71107d15bca978faa"
value: 1
creation_date: 1643995964
payment_preimage: "0000000000000000000000000000000000000000000000000000000000000000"
value_sat: 1
value_msat: 1000
status: IN_FLIGHT
creation_time_ns: 1643995964573455000
payment_index: 9

payment_hash: "c04317014e61c27e3ade9b9e0bedb16237b12a7b50cc92c71107d15bca978faa"
value: 1
creation_date: 1643995964
payment_preimage: "0000000000000000000000000000000000000000000000000000000000000000"
value_sat: 1
value_msat: 1000
status: IN_FLIGHT
creation_time_ns: 1643995964573455000
htlcs {
  route {
    total_time_lock: 3805
    total_fees: 1
    total_amt: 2
    hops {
      chan_id: 4067093511208960
      chan_capacity: 1000000
      amt_to_forward: 1
      fee: 1
      expiry: 3765
      amt_to_forward_msat: 1000
      fee_msat: 1000
      pub_key: "02656675c15be159f47f29df13c3f31f798350e7dcb68750a252005e3ede24b621"
      tlv_payload: true
    }
    hops {
      chan_id: 4080287650742272
      chan_capacity: 800000
      amt_to_forward: 1
      expiry: 3765
      amt_to_forward_msat: 1000
      pub_key: "02bd54561cb8d140703e57a9ea2cd4dccbf6fba6cbfaeaf352a8e8d96c1f7c9486"
      tlv_payload: true
      mpp_record {
        total_amt_msat: 1000
        payment_addr: "c\211\376\303Bk\002\n\222\320j\026.\252\306G\246\"4z\225\321>rD\214\355\276\305\030}\305"
      }
      custom_records {
        key: 400000
        value: "test"
      }
    }
    total_fees_msat: 1000
    total_amt_msat: 2000
  }
  attempt_time_ns: 1643995964602013000
  attempt_id: 6
}
payment_index: 9

payment_hash: "c04317014e61c27e3ade9b9e0bedb16237b12a7b50cc92c71107d15bca978faa"
value: 1
creation_date: 1643995964
fee: 1
payment_preimage: "d2592fa66da4f1f70eefd899df3d218a98d557aefa0a5065a47779b5515fd10d"
value_sat: 1
value_msat: 1000
status: SUCCEEDED
fee_sat: 1
fee_msat: 1000
creation_time_ns: 1643995964573455000
htlcs {
  status: SUCCEEDED
  route {
    total_time_lock: 3805
    total_fees: 1
    total_amt: 2
    hops {
      chan_id: 4067093511208960
      chan_capacity: 1000000
      amt_to_forward: 1
      fee: 1
      expiry: 3765
      amt_to_forward_msat: 1000
      fee_msat: 1000
      pub_key: "02656675c15be159f47f29df13c3f31f798350e7dcb68750a252005e3ede24b621"
      tlv_payload: true
    }
    hops {
      chan_id: 4080287650742272
      chan_capacity: 800000
      amt_to_forward: 1
      expiry: 3765
      amt_to_forward_msat: 1000
      pub_key: "02bd54561cb8d140703e57a9ea2cd4dccbf6fba6cbfaeaf352a8e8d96c1f7c9486"
      tlv_payload: true
      mpp_record {
        total_amt_msat: 1000
        payment_addr: "c\211\376\303Bk\002\n\222\320j\026.\252\306G\246\"4z\225\321>rD\214\355\276\305\030}\305"
      }
      custom_records {
        key: 400000
        value: "test"
      }
    }
    total_fees_msat: 1000
    total_amt_msat: 2000
  }
  attempt_time_ns: 1643995964602013000
  resolve_time_ns: 1643995965027839000
  preimage: "\322Y/\246m\244\361\367\016\357\330\231\337=!\212\230\325W\256\372\nPe\244wy\265Q_\321\r"
  attempt_id: 6
}
payment_index: 9

(venv) $
```
That's pretty much it! The key is making sure your channels have enough inboud and outbound liquidity to start. You can easily modify both scripts so the sender is Charlie and the receiver Alice, it works. You can also extend them to take text input from the command prompt and send that instead of a fixed string like `"test"`. You can create a script to break up a file into chunks and use lightning as the transport layer. The possibilities are endless.

# Bonus Section - Sending a Custom Message Without a Payment

If for whatever reason you want to use the encrypted communication layer between two LN nodes but don't want your custom records to be attached to a payment, LND has an easy solution for that as well. For the sender, we use the `lnrpc` method `SendCustomMessage` and the receiver must listen for custom messages with `SubscribeCustomMessages`. The issue with using this as opposed to attaching a custom record to a payment is that you can only send messages to peers you are directly connected to. A channel between you is not necessary but other nodes will not route your messages for you, you must be directly connected. Also, because here the `type` field in the `SendCustomMessageRequest` is a `uint32` instead of `utin64`, the range of acceptable values is `32768 <=> 65535`.
`send_msg.py`
```
import protos.lightning_pb2 as ln
import protos.lightning_pb2_grpc as lnrpc
import protos.router_pb2 as router
import protos.router_pb2_grpc as routerrpc
import grpc
import os
import codecs

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handhsake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

with open(os.path.expanduser('~/go/dev/alice/data/chain/bitcoin/simnet/admin.macaroon'), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

cert = open(os.path.expanduser('~/Library/Application Support/Lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10001', creds)
#stub = routerrpc.RouterStub(channel)
stub = lnrpc.LightningStub(channel)
# for resp in stub.SendPaymentV2(router.SendPaymentRequest(
#     dest=bytes.fromhex("02bd54561cb8d140703e57a9ea2cd4dccbf6fba6cbfaeaf352a8e8d96c1f7c9486"),
#     amt=1,
#     timeout_seconds=15,
#     fee_limit_sat=1000000,
#     dest_custom_records={
#         400000: bytes("test", 'utf-8')
#     },
#     amp=True,
# ), metadata=[('macaroon', macaroon)]):
#     print(resp)
print(stub.SendCustomMessage(ln.SendCustomMessageRequest(
    peer=bytes.fromhex("02bd54561cb8d140703e57a9ea2cd4dccbf6fba6cbfaeaf352a8e8d96c1f7c9486"),
    type=42069,
    data=bytes("test", 'utf-8'),
), metadata=[('macaroon', macaroon)]))
```
`recv_msg.py`
```
import protos.lightning_pb2 as ln
import protos.lightning_pb2_grpc as lnrpc
import grpc
import os
import codecs

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handhsake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

with open(os.path.expanduser('~/go/dev/charlie/data/chain/bitcoin/simnet/admin.macaroon'), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

cert = open(os.path.expanduser('~/Library/Application Support/Lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10003', creds)
stub = lnrpc.LightningStub(channel)
# for resp in stub.SubscribeInvoices(ln.InvoiceSubscription(), metadata=[('macaroon', macaroon)]):
#     for htlc in resp.htlcs:
#         print(htlc.custom_records[400000].decode('utf-8'))
for resp in stub.SubscribeCustomMessages(ln.SubscribeCustomMessagesRequest(), metadata=[('macaroon', macaroon)]):
    print(resp)
```
And then if we run both of these scripts, we get the following.
`recv_msg.py`
```
(venv) (venv) $ python recv_msg.py 
peer: "\003Y\341\22476-VD\260\346\026\336\034\245\336\345\0013\377?M\355\330\202]K\377@\220\324[\216"
type: 42069
data: "test"

^C
(venv) (venv) $
```
`send_msg.py`
```
(venv) (venv) $ python send_msg.py 

(venv) (venv) $
```