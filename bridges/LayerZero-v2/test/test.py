# Import Library
from web3 import Web3
import os.path
import json
import argparse
from web3.middleware import construct_sign_and_send_raw_middleware
from decimal import Decimal
from web3.exceptions import ContractCustomError
from utils import call_contract_fn, load_contract, get_chain_id, get_provider
import DVN
import Executor

###################### Global variables ###########################
mint_accounts = True  # flag for minting CTKNs to accounts
mint_balance = 100
###################################################################


"""
function for loading account addresses, minting CTKNs, and getting initial balances
@web3: Web3 provider for chain
@ctkn_contract: CTKN contract
@accounts: accounts dictionary from bridge_config json
@return: disctionary containing initial accounts and balances
"""


def init_accounts(web3, ctkn_contract, accounts):
    # read accounts from local db
    oAppOwner = accounts["oAppOwner"]
    account1 = accounts["test_account1"]
    account2 = accounts["test_account2"]
    # add signatures to middleware
    web3.middleware_onion.add(
        construct_sign_and_send_raw_middleware(oAppOwner["private_key"])
    )
    web3.eth.default_account = oAppOwner["address"]
    web3.middleware_onion.add(
        construct_sign_and_send_raw_middleware(account1["private_key"])
    )
    web3.middleware_onion.add(
        construct_sign_and_send_raw_middleware(account2["private_key"])
    )
    # mint CTKN tokens if flag is set to True
    if mint_accounts:
        nonce = web3.eth.get_transaction_count(oAppOwner["address"])
        tx_data = {
            "from": oAppOwner["address"],
            "gas": 30000000,  # Trying to make it dynamic..
            "gasPrice": web3.eth.gas_price,  # Get Gas Price
            "nonce": nonce,
        }
        call_contract_fn(
            ctkn_contract,
            "mint",
            web3,
            tx_data,
            (oAppOwner["address"], web3.to_wei(mint_balance, "ether")),
        )
        tx_data.update(
            {
                "nonce": nonce + 1,
            }
        )
        call_contract_fn(
            ctkn_contract,
            "mint",
            web3,
            tx_data,
            (account1["address"], web3.to_wei(mint_balance, "ether")),
        )
        tx_data.update(
            {
                "nonce": nonce + 2,
            }
        )
        call_contract_fn(
            ctkn_contract,
            "mint",
            web3,
            tx_data,
            (account2["address"], web3.to_wei(mint_balance, "ether")),
        )

    # Read balances for all accounts
    ctkn_balance_before = ctkn_contract.caller.balanceOf(oAppOwner["address"])
    ctkn_balance1_before = ctkn_contract.caller.balanceOf(account1["address"])
    ctkn_balance2_before = ctkn_contract.caller.balanceOf(account2["address"])
    eth_balance_before = web3.from_wei(
        web3.eth.get_balance(oAppOwner["address"]), "ether"
    )
    eth_balance1_before = web3.from_wei(
        web3.eth.get_balance(account1["address"]), "ether"
    )
    eth_balance2_before = web3.from_wei(
        web3.eth.get_balance(account2["address"]), "ether"
    )

    print(
        "Balance of "
        + account1["address"]
        + " on chain "
        + str(web3.eth.chain_id)
        + " before tx:"
        + str(ctkn_balance1_before)
        + " ctkns and "
        + str(eth_balance1_before)
        + " ethers"
    )
    print(
        "Balance of "
        + account2["address"]
        + " on chain "
        + str(web3.eth.chain_id)
        + " before tx:"
        + str(ctkn_balance2_before)
        + " ctkns and "
        + str(eth_balance2_before)
        + " ethers"
    )

    return {
        "oAppOwner": {
            "address": oAppOwner["address"],
            "ctkn_balance": ctkn_balance_before,
            "eth_balance": eth_balance_before,
        },
        "account1": {
            "address": account1["address"],
            "ctkn_balance": ctkn_balance1_before,
            "eth_balance": eth_balance1_before,
        },
        "account2": {
            "address": account2["address"],
            "ctkn_balance": ctkn_balance2_before,
            "eth_balance": eth_balance2_before,
        },
    }


"""
function for sending tokens(value_to_tx) from a source account to a dst account on a different chain
@web3: web3 povider for source chain executing send operation
@ctkn: contract object of token as descibed by OFT contract in LZ docs
@src_account
@dst_chain
@dst_account
@value_to_tx
@return: will return a tuple containing all data needed for performing lzReceive
"""


def send_token(web3, ctkn, src_account, dst_chain, dst_account, value_to_tx):
    print("Quoting send operaion to get message fee")
    sendParam = (
        dst_chain,
        Web3.to_bytes(hexstr=dst_account).rjust(32, b"\0"),
        value_to_tx,
        value_to_tx,
        Web3.to_bytes(hexstr="0x00030100110100000000000000000000000000030d40"),
        b"",
        b"",
    )
    nonce = web3.eth.get_transaction_count(src_account)
    tx_data = {
        "from": src_account,
        "gas": 30000000,  # Trying to make it dynamic..
        "gasPrice": web3.eth.gas_price,  # Get Gas Price
        "nonce": nonce,
    }
    try:
        quote = ctkn.caller(tx_data).quoteSend(sendParam, False)
    except ContractCustomError as e:
        print("Received following contract error during quoteSend:" + str(e))
        exit(1)

    print(
        "Received following quote:"
        + str(quote)
        + ". Attempting to execute transaction with it."
    )

    print("Calling send function from first chain")
    # function send(SendParam calldata _sendParam, MessagingFee calldata _fee, address _refundAddress)
    # struct SendParam {
    #   uint32 dstEid; // Destination endpoint ID.
    #   bytes32 to; // Recipient address.
    #   uint256 amountLD; // Amount to send in local decimals.
    #   uint256 minAmountLD; // Minimum amount to send in local decimals.
    #   bytes extraOptions; // Additional options supplied by the caller to be used in the LayerZero message.
    #   bytes composeMsg; // The composed message for the send() operation.
    #   bytes oftCmd; // The OFT command to be executed, unused in default OFT implementations.
    # }
    # struct MessagingFee {
    #   uint nativeFee; // gas amount in native gas token
    #   uint lzTokenFee; // gas amount in ZRO token
    # }
    tx_data.update(
        {
            "value": quote[0],
        }
    )
    try:
        msg = ctkn.caller().buildMsgAndOptions(
            sendParam, web3.to_wei(Decimal(value_to_tx), "ether")
        )
        msg_receipt, oft_receipt = ctkn.caller(tx_data).send(
            sendParam, quote, src_account
        )
    except Exception as e:
        print("Received following error while performing send transaction:" + str(e))
        exit(1)
    # if local call passed without errors than we can perform public tx
    fargs = (sendParam, quote, src_account)
    call_contract_fn(ctkn, "send", web3, tx_data, fargs)
    print(
        "Send operation performed on first chain with following OFT receipt:"
        + str(oft_receipt)
        + "\nMsg receipt: "
        + str(msg_receipt)
        + " \nMsg payload: "
        + str(msg)
    )

    # @param _origin The origin information containing the source endpoint and sender address.
    #   - srcEid: The source chain endpoint ID.
    #   - sender: The sender address on the src chain.
    #   - nonce: The nonce of the message.
    # @dev MessagingReceipt: LayerZero msg receipt
    #   - guid: The unique identifier for the sent message.
    #   - nonce: The nonce of the sent message.
    #   - fee: The LayerZero fee incurred for the message.
    origin = (web3.eth.chain_id, ctkn.address, msg_receipt[1])
    return origin, msg_receipt[0], msg[0]


"""
function for executing ping-pong cross-chain tx test
the function will perform txs between test accounts in the config file
@bridge_config: bridge configuration dictionary
@src_web3: web3 provider for source of transaction
@dst_web3: web3 provider for destination of transaction
@src_chain: chain identifier for source of transaction (possible values: chain1/chain2 as defined in bridge_config json)
@dst_chain: chain identifier for destination of transaction (possible values: chain2/chain1 as defined in bridge_config json)
@value_to_tx: value to tx in ethers unit
"""


def ping_pong_tx(
    bridge_config,
    src_web3,
    dst_web3,
    src_chain="chain1",
    dst_chain="chain2",
    value_to_tx="1",
):
    print("Retrieving CTKN smart contracts from chains")
    src_ctkn = load_contract(
        "CTKN", bridge_config[src_chain]["contracts"]["CTKN"], src_web3
    )
    dst_ctkn = load_contract(
        "CTKN", bridge_config[dst_chain]["contracts"]["CTKN"], dst_web3
    )

    print("Initiating involved accounts in both chains")
    if mint_accounts:
        print(
            "Minting initial balance of "
            + str(mint_balance)
            + " tokens to accounts in first chain"
        )
    src_accounts = init_accounts(
        src_web3,
        src_ctkn,
        bridge_config[src_chain]["accounts"],
    )
    if mint_accounts:
        print(
            "Minting initial balance of "
            + str(mint_balance)
            + " tokens to accounts in second chain"
        )
    dst_accounts = init_accounts(
        dst_web3,
        dst_ctkn,
        bridge_config[dst_chain]["accounts"],
    )

    print("Executing LayerZero send tx from " + src_chain + "  to " + dst_chain)
    origin, guid, message = send_token(
        src_web3,
        src_ctkn,
        src_accounts["account1"]["address"],
        bridge_config[dst_chain]["chain_id"],
        dst_accounts["account2"]["address"],
        src_web3.to_wei(Decimal(value_to_tx), "ether"),
    )

    print("Getting DVN Security Stack")
    dvn_stack = DVN.get_dvn_stack(
        src_web3, dst_web3, src_chain, dst_chain, bridge_config
    )
    src_endpoint = load_contract(
        "EndpointV2", bridge_config[src_chain]["contracts"]["EndpointV2"], src_web3
    )
    dst_endpoint = load_contract(
        "EndpointV2", bridge_config[dst_chain]["contracts"]["EndpointV2"], dst_web3
    )
    print("Performing verification on behalf of DVNs")
    packets = DVN.verify_tx(
        src_web3,
        dst_web3,
        src_endpoint,
        dst_endpoint,
        dvn_stack,
        dst_ctkn.address,
    )

    print("Finished DVN worflow. Performing lzReceive as Executor")
    Executor.execute_lzreceive(
        dst_web3,
        packets,
        bridge_config[dst_chain]["contracts"]["Executor"],
        bridge_config[dst_chain]["accounts"]["executorAdmin"],
    )
    print("Checking that lzReceive operation completed successfuly on " + dst_chain)

    ###################### Check balances after tx executed on both chains ########################
    ctkn_balance1_after = src_ctkn.caller.balanceOf(src_accounts["account1"]["address"])
    ctkn_balance2_after = dst_ctkn.caller.balanceOf(dst_accounts["account2"]["address"])
    eth_balance1_after = src_web3.from_wei(
        src_web3.eth.get_balance(src_accounts["account1"]["address"]), "ether"
    )
    eth_balance2_after = dst_web3.from_wei(
        dst_web3.eth.get_balance(dst_accounts["account2"]["address"]), "ether"
    )
    print(
        "Balance of "
        + src_accounts["account1"]["address"]
        + " on "
        + src_chain
        + " after tx:"
        + str(ctkn_balance1_after)
        + " ctkns and "
        + str(eth_balance1_after)
        + " ethers"
    )
    print(
        "Balance of "
        + dst_accounts["account2"]["address"]
        + " on "
        + dst_chain
        + " chain after tx:"
        + str(ctkn_balance2_after)
        + " ctkns and "
        + str(eth_balance2_after)
        + " ethers"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Quick test of intrachain/interchain transactioning"
    )
    parser.add_argument(
        "--chain1", type=int, default=1, help="Chain1 involved in LayerZero tx"
    )
    parser.add_argument(
        "--chain2", type=int, default=2, help="Chain2 involved in LayerZero tx"
    )
    parser.add_argument("--value", type=str, default="1", help="Value to send")
    args = parser.parse_args()

    chain1_id = get_chain_id(args.chain1)
    chain2_id = get_chain_id(args.chain2)
    # first check if we don't already have a bridge between these two chains
    # search by bridge name which is a concatenation of the two chains ids in ascending order
    if chain1_id < chain2_id:
        bridge_name = str(chain1_id) + "_" + str(chain2_id)
    else:
        bridge_name = str(chain2_id) + "_" + str(chain1_id)

    bridge_config = {}
    if os.path.isfile("bridges/LayerZero-v2/lz_config.json"):
        with open("bridges/LayerZero-v2/lz_config.json") as f:
            f.seek(0, os.SEEK_END)  # go to end of file
            if f.tell():  # if current position is truish (i.e != 0)
                f.seek(0)  # rewind the file for later use
                config = json.loads(f.read())
                for bridge in config:
                    if bridge["bridge"] == bridge_name:
                        print("Found bridge between provided chains.")
                        bridge_config = bridge
                        break
            f.close()

    if bridge_config is None:
        print("Could not find bridge for provided chains! Aborting test...")
        exit(1)

    print("Connecting to source and destination chains available nodes")
    chain1_web3 = get_provider(bridge_config["chain1"]["nodes"][0])
    chain2_web3 = get_provider(bridge_config["chain2"]["nodes"][0])

    print("Performing a ping-pong tx test between the two chains")
    print("Sending transaction from first chain to second chain")
    ping_pong_tx(
        bridge_config,
        chain1_web3,
        chain2_web3,
        "chain" + str(args.chain1),
        "chain" + str(args.chain2),
        args.value,
    )
    print("Sending transaction from second chain to first chain")
    ping_pong_tx(
        bridge_config,
        chain2_web3,
        chain1_web3,
        "chain" + str(args.chain2),
        "chain" + str(args.chain1),
        args.value,
    )


if __name__ == "__main__":
    main()
