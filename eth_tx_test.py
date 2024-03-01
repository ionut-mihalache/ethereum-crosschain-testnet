# Import Library
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from python_on_whales import DockerClient
import argparse

default_port = 8503  # first assigned port


# chain=0 is the default value for a single chain network
# chain>0 is the value of the current queried chain in a multi-chain network
def test_intrachain_tx(
    chain=0,
    value_to_tx=1000,
    tx_gas_price=1,
    tx_gas=200000,
    docker_manager="worker-001",
):
    if chain == 0:
        config_file = "./seed_data/blockchain_config.json"
        with open(config_file) as f:
            config = json.load(f)
            chain_id = config.get("chain_id", 42)
    else:
        config_file = "./seed_data/blockchain" + str(chain) + "_config.json"
        with open(config_file) as f:
            config = json.load(f)
            chain_id = config.get("chain_id", 42)

    docker_client = DockerClient(host="ssh://" + docker_manager)

    if chain == 0:
        # get hostname of first worker node in swarm
        hostname = docker_client.node.list()[1].description.hostname
        # get http port(which is always first) of first node in swarm
        service_id = docker_client.node.ps(hostname)[0].service_id
        port = docker_client.service.inspect(service_id).endpoint.ports[0].target_port
    else:
        print("Looking for an available worker node to connect to...")
        nodes = docker_client.node.list()
        for n in nodes:
            hostname = n.description.hostname
            tasks = docker_client.node.ps(hostname)
            port_match = False
            for t in tasks:
                port = (
                    docker_client.service.inspect(t.service_id)
                    .endpoint.ports[0]
                    .target_port
                )
                if (port - default_port) // 128 == chain - 1:
                    port_match = True
                    break
            if port_match:
                break

    # connect to worker node and perform tx
    worker_endpoint = "http://" + hostname + ":" + str(port)
    w3 = Web3(Web3.HTTPProvider(worker_endpoint))
    print(
        "Connected to worker "
        + hostname
        + ":"
        + str(port)
        + "="
        + str(w3.is_connected())
    )
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    with open("./seed_data/accounts.json", "r") as f:
        array = json.loads(f.read())

    account1_address = array[0]["address"]
    account1_key = array[0][
        "private_key"
    ]  # only read private key for first account in order to sign tx
    account2_address = array[1]["address"]

    print("Loaded account:" + account1_address)
    print("Loaded account:" + account2_address)

    balance1_before = w3.eth.get_balance(account1_address)
    balance2_before = w3.eth.get_balance(account2_address)
    print("Balance of " + account1_address + " before tx:" + str(balance1_before))
    print("Balance of " + account2_address + " before tx:" + str(balance2_before))

    nonce = w3.eth.get_transaction_count(account1_address)
    transaction = {
        "to": account2_address,
        "value": value_to_tx,
        "gas": tx_gas,
        "gasPrice": tx_gas_price,
        "chainId": chain_id,
        "nonce": nonce,
    }

    signed = w3.eth.account.sign_transaction(transaction, account1_key)
    # when using one of its generated test accounts,
    # eth-tester signs the tx (under the hood) before sending:
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)

    tx = w3.eth.get_transaction(tx_hash)
    assert tx["from"] == account1_address
    assert tx["to"] == account2_address

    print("Tx created...waiting to be added to block")

    tx_receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=360, poll_latency=0.1
    )

    print("Tx added to block...checking updated balances.")

    balance1_after = w3.eth.get_balance(account1_address)
    balance2_after = w3.eth.get_balance(account2_address)
    print("Balance of " + account1_address + " after tx:" + str(balance1_after))
    print("Balance of " + account2_address + " after tx:" + str(balance2_after))

    assert (
        balance1_before - value_to_tx - (tx_receipt["gasUsed"] * tx_gas_price)
    ) == balance1_after
    assert (balance2_before + value_to_tx) == balance2_after
    print("Tx completed successfuly")


def main():
    parser = argparse.ArgumentParser(
        description="Quick test of intrachain/interchain transactioning"
    )
    parser.add_argument(
        "--chain", type=int, default=0, help="Chain number of intra/inter-chain tx"
    )
    parser.add_argument("--value", type=int, default=100, help="Value to send")
    parser.add_argument("--gas-price", type=int, default=1, help="Gas price for tx")
    parser.add_argument(
        "--docker-manager",
        type=str,
        default="worker-001",
        help="Docker swarm manager hostname",
    )
    args = parser.parse_args()
    print(
        "Testing intrachain transaction for chain "
        + str(args.chain)
        + " with a tx amount of "
        + str(args.value)
    )
    test_intrachain_tx(
        args.chain, args.value, args.gas_price, 200000, args.docker_manager
    )


if __name__ == "__main__":
    main()
