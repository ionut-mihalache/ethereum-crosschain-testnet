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
    # first try to execute it locally to catch any possible errors
    try:
        executor.caller(tx_data).nativeDropAndExecute302(
            native_drop, 0, execution_params
        )
    except Exception as e:
        print(repr(e))
        exit(1)
    # if no error thrown, we can safely execute it on chain
    call_contract_fn(
        executor,
        "nativeDropAndExecute302",
        dst_web3,
        tx_data,
        (native_drop, 0, execution_params),
    )
