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
