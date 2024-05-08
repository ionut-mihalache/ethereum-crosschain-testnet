from utils import load_contract, call_contract_fn
from web3.middleware import construct_sign_and_send_raw_middleware

"""
function for executing nativeDropAndExecute302 smart contract function on executor behalf
@dst_web: Web3 provder for destination chain of transaction
@packets: tuple of packet sent and packet received objects
@executor_address: Executor smart contract address
@executor_admin: admin user allowed to perform nativeDropAndExecute302
"""


def execute_lzreceive(dst_web3, packets, executor_address, executor_admin):
    dst_web3.middleware_onion.add(
        construct_sign_and_send_raw_middleware(executor_admin["private_key"])
    )
    packet_sent = packets[0]
    packet_received = packets[1]
    guid = packet_sent["encodedPayload"][81:113]
    message = packet_sent["encodedPayload"][113:]
    executor = load_contract("Executor", executor_address, dst_web3)

    print(packet_sent)
    print(packet_received)
    print(guid)
    print(message)

    # 85c1350d551e3ea8abb3f88557d950926d872e3335aa3d24d103fcef92a04462
    # 010000000000000001000004d2000000000000000000000000a7edcb97b20d725b5d4dc82c0971dca2e42a482d000010e1000000000000000000000000a7edcb97b20d725b5d4dc82c0971dca2e42a482d85c1350d551e3ea8abb3f88557d950926d872e3335aa3d24d103fcef92a0446200000000000000000000000032715f1b6596dee3c8572a71bb1e0cb5f4cedbfe00000000000f4240

    # we don't perform any native drop, only receive
    native_drop = []
    origin = (
        packet_received["origin"]["srcEid"],
        packet_received["origin"]["sender"],
        packet_received["origin"]["nonce"],
    )
    # gas limit set to maximum limit of 200000
    # this corresponds to the LzExecutor options set on source chain
    execution_params = (
        packet_received["receiver"],
        origin,
        guid,
        message,
        b"",
        200000,
    )
    # only admin role user can perform this transaction call
    tx_data = {"from": executor_admin["address"]}
    print(tx_data)
    print(execution_params)
    # first try to execute it locally to catch any possible errors
    try:
        executor.caller(tx_data).nativeDropAndExecute302(
            native_drop, 0, execution_params
        )
    except Exception as e:
        print(repr(e))
        exit(1)
    # if no error thrown, we can safely execute it on chain
    print("lzReceive tx hash:", call_contract_fn(
        executor,
        "nativeDropAndExecute302",
        dst_web3,
        tx_data,
        (native_drop, 0, execution_params),
    ))


# # Online Python compiler (interpreter) to run Python online.
# # Write Python 3 code in this online editor and run it.
# import binascii

# hex1 = b'\x85\xc15\rU\x1e>\xa8\xab\xb3\xf8\x85W\xd9P\x92m\x87.35\xaa=$\xd1\x03\xfc\xef\x92\xa0Db'.hex()
# print(hex1)

# # hex2 = b'\x01\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x04\xd2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa7\xed\xcb\x97\xb2\rr[]M\xc8,\tq\xdc\xa2\xe4*H-\x00\x00\x10\xe1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa7\xed\xcb\x97\xb2\rr[]M\xc8,\tq\xdc\xa2\xe4*H-\x85\xc15\rU\x1e>\xa8\xab\xb3\xf8\x85W\xd9P\x92m\x87.35\xaa=$\xd1\x03\xfc\xef\x92\xa0Db\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x002q_\x1be\x96\xde\xe3\xc8W*q\xbb\x1e\x0c\xb5\xf4\xce\xdb\xfe\x00\x00\x00\x00\x00\x0fB@'.hex()
# hex2 = b'\x01\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x04\xd2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa7\xed\xcb\x97\xb2\rr[]M\xc8,\tq\xdc\xa2\xe4*H-\x00\x00\x10\xe1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa7\xed\xcb\x97\xb2\rr[]M\xc8,\tq\xdc\xa2\xe4*H-\xd2(4\xede\xdf\xf8D\x9b\xfe\x8boR\xd9\xe1\xeb\xaa\x86\xe3\xa2h]L\xf7\xdfD\xd9\xfa~a\xae\x87\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x002q_\x1be\x96\xde\xe3\xc8W*q\xbb\x1e\x0c\xb5\xf4\xce\xdb\xfe\x00\x00\x00\x00\x00\x0fB@'.hex()
# print(hex2)

# hex3 = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x002q_\x1be\x96\xde\xe3\xc8W*q\xbb\x1e\x0c\xb5\xf4\xce\xdb\xfe\x00\x00\x00\x00\x00\x0fB@'.hex()
# print(hex3)

# int1 = [int(hex1[i:i+2],16) for i in range(0,len(hex1),2)]
# print(int1)

# int2 = [int(hex2[i:i+2],16) for i in range(0,len(hex2),2)]
# print(int2)

# int3 = [int(hex3[i:i+2],16) for i in range(0,len(hex3),2)]
# print(int3)

# header_hex = b'\x01\x00\x00\x00\x00\x00\x00\x00#\x00\x00\x04\xd2\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa7\xed\xcb\x97\xb2\rr[]M\xc8,\tq\xdc\xa2\xe4*H-\x00\x00\x10\xe1\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xa7\xed\xcb\x97\xb2\rr[]M\xc8,\tq\xdc\xa2\xe4*H-'.hex()
# print(header_hex)