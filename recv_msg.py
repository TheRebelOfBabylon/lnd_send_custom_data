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
