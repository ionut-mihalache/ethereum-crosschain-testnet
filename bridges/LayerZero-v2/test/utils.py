from web3 import Web3
import json
from web3.middleware import geth_poa_middleware
from web3.gas_strategies.rpc import rpc_gas_price_strategy

print_log = False

"""
@abi: abi json of smart contract
@function_name: functiona that will be called
@function_args: arguments passed to function
                need to be passed as tuple, even for a single argument
                internal structures of solidity must be passed also as tuple
                in case of bytes argument, encode must be applied before calling this function
@return: returnes dictionary of argument name and argument value pairs as detailed in abi
"""


def build_args(abi, function_name, function_args):
    functionABI = None
    for item in abi:
        if "name" in item and item["name"] == function_name:
            functionABI = item
            break
    if functionABI is None:
        print("Could not find the specified function in the provided ABI!")
        exit(1)
    argumentNames = []
    for functionArgument in functionABI["inputs"]:
        argumentNames.append(functionArgument["name"])
    packedArgs = {}
    for functionArgument in range(len(function_args)):
        packedArgs[argumentNames[functionArgument]] = function_args[functionArgument]
    return packedArgs


"""
function for loading a contract object
@name: name of the contract as defined by LayerZero
@address: address of the deployed contract
@web3: web3 provider object for chain
"""


def load_contract(name, address, web3):
    # retrieve abi from CTKN contract json
    with open("bridges/LayerZero-v2/oapp/out/" + name + ".sol/" + name + ".json") as f:
        contract_json = json.load(f)
        abi = contract_json.get("abi")
    return web3.eth.contract(address=address, abi=abi)


"""
wrapper for calling a function inside a smart contract
@contract: contract object
@function_name: name of function being called
@signer: account structure used to send and sign tx of function call
@web3: web3 provider used to make function call
@function_args: arguments passed to function
@return: tx hash for future reference
"""


def call_contract_fn(contract, function_name, web3, tx_data, function_args=None):
    function = contract.functions[function_name]
    packed_args = {}
    if function_args is not None:
        packed_args = build_args(contract.abi, function_name, function_args)
        if print_log:
            print("Executing " + function_name + " with " + str(packed_args))
    elif print_log:
        print("Executing " + function_name)
    # build and sign transaction
    tx_hash = function(**packed_args).transact(tx_data)
    tx_receipt = web3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=360, poll_latency=0.1
    )
    if tx_receipt["status"] == 0:
        print("Failed to deploy contract with following tx receipt:" + str(tx_receipt))
        exit(1)
    if print_log:
        print("Successfuly executed function")
        print("tx_hash:" + tx_hash.hex())
    return tx_hash


"""
given a chain index from N spawned chain retrieve its chain id
"""


def get_chain_id(chain):
    config_file = "./seed_data/blockchain" + str(chain) + "_config.json"
    with open(config_file) as f:
        config = json.load(f)
        chain_id = config.get("chain_id", 42)
    return chain_id


"""
@chain: chain identifier as used when deployed in docker swarm
@docker_client: docker instance of manager used to retrieve a worker node
@return: the web3 provider and chain id for the specified chain identifier 
"""


def get_provider(worker_endpoint):
    web3 = Web3(Web3.HTTPProvider(worker_endpoint))
    print("Connected to worker " + worker_endpoint + "=" + str(web3.is_connected()))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    web3.strict_bytes_type_checking = False
    web3.eth.set_gas_price_strategy(rpc_gas_price_strategy)
    return web3
