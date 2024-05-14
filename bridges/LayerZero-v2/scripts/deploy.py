# Import Library
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from python_on_whales import DockerClient
import argparse
import os
from web3.middleware import construct_sign_and_send_raw_middleware
from decimal import Decimal
from collections import OrderedDict


default_port = 8503  # first assigned port
ws_default_port = 33444
lz_config = "bridges/LayerZero-v2/lz_config.json"

"""
@web3: web3 provider object for a chain
@dvsn: number of dvns per assigned between two bridges
@dvn_workers: number of signers per dvn
@return: dictionary of account addresses and private keys which will be used during deployment
"""


def set_signers(web3, dvns=2, dvn_workers=2):
    with open("./seed_data/accounts.json", "r") as f:
        array = json.loads(f.read())
    accounts = {}
    # we use addresses from index 100 in our account list
    # we inject the signing private_keys for this node in order to avoid signing each tx manually
    # but we save all accounts as part of config file
    layerzero_address = array[100]["address"]
    layerzero_key = array[100]["private_key"]
    web3.middleware_onion.add(construct_sign_and_send_raw_middleware(layerzero_key))
    executorRoleAdmin_address = array[101]["address"]
    executorRoleAdmin_key = array[101]["private_key"]
    executorAdmin_address = array[102]["address"]
    executorAdmin_key = array[102]["private_key"]
    web3.middleware_onion.add(construct_sign_and_send_raw_middleware(executorAdmin_key))
    verifier_address = array[103]["address"]
    verifier_key = array[103]["private_key"]
    verifierAdmin_address = array[104]["address"]
    verifierAdmin_key = array[104]["private_key"]
    web3.middleware_onion.add(construct_sign_and_send_raw_middleware(verifierAdmin_key))
    oAppOwner_address = array[105]["address"]
    oAppOwner_key = array[105]["private_key"]
    web3.middleware_onion.add(construct_sign_and_send_raw_middleware(oAppOwner_key))
    # handle dvn accounts separately
    current_address = 106
    for dvn in range(dvns):
        for worker in range(dvn_workers):
            signer_address = array[current_address]["address"]
            signer_key = array[current_address]["private_key"]
            index = "dvn_worker" + str(worker + dvns * dvn)
            accounts.update(
                {index: {"address": signer_address, "private_key": signer_key}}
            )
            current_address += 1
    # also test accounts for txs
    accts_nr = 50
    accts = []
    for i in range(accts_nr):
        accts.append({"address": array[i]["address"], "private_key": array[i]["private_key"]})
    # account1 = {"address": array[0]["address"], "private_key": array[0]["private_key"]}
    # account2 = {"address": array[1]["address"], "private_key": array[1]["private_key"]}
    # account3 = {"address": array[2]["address"], "private_key": array[2]["private_key"]}
    # account4 = {"address": array[3]["address"], "private_key": array[3]["private_key"]}
    # account5 = {"address": array[4]["address"], "private_key": array[4]["private_key"]}
    # account6 = {"address": array[5]["address"], "private_key": array[5]["private_key"]}
    # account7 = {"address": array[6]["address"], "private_key": array[6]["private_key"]}
    # account8 = {"address": array[7]["address"], "private_key": array[7]["private_key"]}
    # account9 = {"address": array[8]["address"], "private_key": array[8]["private_key"]}
    # account10 = {"address": array[9]["address"], "private_key": array[9]["private_key"]}
    # account11 = {"address": array[10]["address"], "private_key": array[10]["private_key"]}
    # account12 = {"address": array[11]["address"], "private_key": array[11]["private_key"]}
    # account13 = {"address": array[12]["address"], "private_key": array[12]["private_key"]}
    # account14 = {"address": array[13]["address"], "private_key": array[13]["private_key"]}
    # account15 = {"address": array[14]["address"], "private_key": array[14]["private_key"]}
    # account16 = {"address": array[15]["address"], "private_key": array[15]["private_key"]}
    # account17 = {"address": array[16]["address"], "private_key": array[16]["private_key"]}
    # account18 = {"address": array[17]["address"], "private_key": array[17]["private_key"]}
    # account19 = {"address": array[18]["address"], "private_key": array[18]["private_key"]}
    # account20 = {"address": array[19]["address"], "private_key": array[19]["private_key"]}

    print("Loaded accounts")
    accounts.update(
        {
            "layerzero": {"address": layerzero_address, "private_key": layerzero_key},
            "executorRoleAdmin": {
                "address": executorRoleAdmin_address,
                "private_key": executorRoleAdmin_key,
            },
            "executorAdmin": {
                "address": executorAdmin_address,
                "private_key": executorAdmin_key,
            },
            "verifier": {"address": verifier_address, "private_key": verifier_key},
            "verifierAdmin": {
                "address": verifierAdmin_address,
                "private_key": verifierAdmin_key,
            },
            "oAppOwner": {"address": oAppOwner_address, "private_key": oAppOwner_key},
            "test_accounts": accts
            # "test_account1": account1,
            # "test_account2": account2,
            # "test_account3": account3,
            # "test_account4": account4,
            # "test_account5": account5,
            # "test_account6": account6,
            # "test_account7": account7,
            # "test_account8": account8,
            # "test_account9": account9,
            # "test_account10": account10,
            # "test_account11": account11,
            # "test_account12": account12,
            # "test_account13": account13,
            # "test_account14": account14,
            # "test_account15": account15,
            # "test_account16": account16,
            # "test_account17": account17,
            # "test_account18": account18,
            # "test_account19": account19,
            # "test_account20": account20,
        }
    )
    return accounts


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
        if (
            function_name == "constructor" and item["type"] == "constructor"
        ):  # if you need to find constructor, as it has no name
            functionABI = item
            break
        elif "name" in item and item["name"] == function_name:
            functionABI = item
            break
    argumentNames = []
    for functionArgument in functionABI["inputs"]:
        argumentNames.append(functionArgument["name"])
    packedArgs = {}
    for functionArgument in range(len(function_args)):
        packedArgs[argumentNames[functionArgument]] = function_args[functionArgument]
    return packedArgs


"""
wrapper for deploying a smart contract 
@param path: path to contract JSON that contains abi and bytecode
@sender: account address used to send tx for contract deployment
@signer: private key of sender to sign transaction
@web3: Web3 provider for current chain to deploy transaction
@function_args: parameters needed by contract constructor for deployment
@return: the deployed contact object
"""


def deploy_contract(path, sender, web3, function_args=None):
    # retrieve abi and bytecode from contract json
    with open(path) as f:
        contract_json = json.load(f)
        abi = contract_json.get("abi")
        bytecode = contract_json.get("bytecode")["object"]
    # initialize contract object
    Contract = web3.eth.contract(abi=abi, bytecode=bytecode)
    # prepare transaction details
    nonce = web3.eth.get_transaction_count(sender["address"])
    tx_data = {
        "from": sender["address"],
        "gas": 10000000,  # This is our hard gas limit
        "gasPrice": web3.eth.gas_price,  # Get Gas Price
        "nonce": nonce,
    }
    # build and sign transaction
    packed_args = {}
    if function_args is not None:
        packed_args = build_args(abi, "constructor", function_args)
        print("Deploying contract with constructor arguments:" + str(packed_args))
    tx_hash = Contract.constructor(**packed_args).transact(tx_data)
    tx_receipt = web3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=360, poll_latency=0.1
    )
    if tx_receipt["status"] == 0:
        print("Failed to deploy contract with following tx receipt:" + str(tx_receipt))
        exit(1)
    # return dictionary of deployed contract containing abi and address
    print("Successfuly deployed contract")
    return web3.eth.contract(address=tx_receipt.contractAddress, abi=abi)


"""
wrapper for calling a function inside a smart contract
@contract: contract object
@function_name: name of function being called
@sender: account address used to send tx of function call
@web3: web3 provider used to make function call
@function_args: arguments passed to function
"""


def call_contract_fn(contract, function_name, sender, web3, function_args=None):
    function = contract.functions[function_name]
    nonce = web3.eth.get_transaction_count(sender["address"])
    tx_data = {
        "from": sender["address"],
        "gas": 10000000,  # Trying to make it dynamic..
        "gasPrice": web3.eth.gas_price,  # Get Gas Price
        "nonce": nonce,
    }
    packed_args = {}
    if function_args is not None:
        packed_args = build_args(contract.abi, function_name, function_args)
        print("Executing " + function_name + " with " + str(packed_args))
    else:
        print("Executing " + function_name)
    # build and sign transaction
    tx_hash = function(**packed_args).transact(tx_data)
    tx_receipt = web3.eth.wait_for_transaction_receipt(
        tx_hash, timeout=360, poll_latency=0.1
    )
    if tx_receipt["status"] == 0:
        print("Failed to deploy contract with following tx receipt:" + str(tx_receipt))
        exit(1)

    print("Successfuly executed function")


"""
@chain: chain identifier as used when deployed in docker swarm
@docker_client: docker instance of manager used to retrieve a worker node
@return:the web3 provider
        chain id for the specified chain identifier
        list of all posible worker endpoints
"""


def get_provider(chain, docker_client):
    providers = []
    ws_providers = []
    config_file = "./seed_data/blockchain" + str(chain) + "_config.json"
    with open(config_file) as f:
        config = json.load(f)
        chain_id = config.get("chain_id", 42)
    print("Looking for available worker nodes to connect to both chains...")
    nodes = docker_client.node.list()
    for n in nodes:
        hostname = n.description.hostname
        tasks = docker_client.node.ps(hostname)
        for t in tasks:
            port = (
                docker_client.service.inspect(t.service_id)
                .endpoint.ports[0]
                .target_port
            )
            ws_port = (
                docker_client.service.inspect(t.service_id).endpoint.ports[2].target_port
            )
            if (port - default_port) // 128 == chain - 1 and (ws_port - ws_default_port) // 128 == chain - 1:  # 128 = max number of nodes
                providers.append("http://" + hostname + ":" + str(port))
                ws_providers.append("ws://" + hostname + ":" + str(ws_port))
                break
    # connect to first worker in list
    worker_endpoint = providers[0]
    web3 = Web3(Web3.HTTPProvider(worker_endpoint))
    print("Connected to worker " + worker_endpoint + "=" + str(web3.is_connected()))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)
    web3.strict_bytes_type_checking = False
    return web3, chain_id, providers, ws_providers


"""
@return: list of paths for every smart contract json needed in deployment of LayerZero
"""


def get_contracts():
    paths = {}
    paths.update(
        {"EndpointV2": "bridges/LayerZero-v2/oapp/out/EndpointV2.sol/EndpointV2.json"}
    )
    paths.update(
        {"SendUln302": "bridges/LayerZero-v2/oapp/out/SendUln302.sol/SendUln302.json"}
    )
    paths.update(
        {
            "ReceiveUln302": "bridges/LayerZero-v2/oapp/out/ReceiveUln302.sol/ReceiveUln302.json"
        }
    )
    paths.update(
        {"Executor": "bridges/LayerZero-v2/oapp/out/Executor.sol/Executor.json"}
    )
    paths.update({"DVN": "bridges/LayerZero-v2/oapp/out/DVN.sol/DVN.json"})
    paths.update(
        {"PriceFeed": "bridges/LayerZero-v2/oapp/out/PriceFeed.sol/PriceFeed.json"}
    )
    paths.update({"CTKN": "bridges/LayerZero-v2/oapp/out/CTKN.sol/CTKN.json"})
    paths.update(
        {
            "ExecutorFeeLib": "bridges/LayerZero-v2/oapp/out/ExecutorFeeLib.sol/ExecutorFeeLib.json"
        }
    )
    paths.update(
        {"DVNFeeLib": "bridges/LayerZero-v2/oapp/out/DVNFeeLib.sol/DVNFeeLib.json"}
    )
    return paths


"""
main function for deploying LayzerZero inside source chain
@src_chain: chain id of source chain where all LayerZero contracts will be deployed
@dst_chain: chain id of dst chain that is used as peer for LayerZero protocol
@web3: web3 provider of src_chain for making transactions
@contracts: list of paths to compiled contract jsons that will be deployed 
@signers: accounts involved in sendind and signing transactions
@dvns: number of dvns deployed for the bridge
@dvn_workers: number of workers per dvns
@return: contract object of OFT app
"""


def deploy_lz(src_chain, dst_chain, web3, contracts, signers, dvns, dvn_workers):
    # Phase 1: depoying lz endpoint
    print("Deploying LayerZero Endpoint smart contract")
    # constructor(uint32 _eid, address _owner)
    lz_endpoint = deploy_contract(
        contracts["EndpointV2"],
        signers["layerzero"],
        web3,
        (src_chain, signers["layerzero"]["address"]),
    )

    # Phase 2: deploying and configuring PriceFeed
    print("Deploying and configuring PriceFeed smart contract")
    price_feed = deploy_contract(contracts["PriceFeed"], signers["layerzero"], web3)
    call_contract_fn(
        price_feed,
        "initialize",
        signers["layerzero"],
        web3,
        (signers["layerzero"]["address"],),
    )
    call_contract_fn(
        price_feed, "setEndpoint", signers["layerzero"], web3, (lz_endpoint.address,)
    )
    # function setPrice(UpdatePrice[] calldata _price)
    # struct Price {
    #    uint128 priceRatio; // float value * 10 ^ 20, decimal awared. for aptos to evm, the basis would be (10^18 / 10^8) * 10 ^20 = 10 ^ 30.
    #    uint64 gasPriceInUnit; // for evm, it is in wei, for aptos, it is in octas.
    #    uint32 gasPerByte;
    # }
    # struct UpdatePrice {
    #    uint32 eid;
    #    Price price;
    # }
    fargs = ([(dst_chain, (pow(10, 20), 1, 1))],)
    call_contract_fn(price_feed, "setPrice", signers["layerzero"], web3, fargs)

    # Phase 3: deploy send msg library
    # constructor(address _endpoint, uint256 _treasuryGasLimit, uint256 _treasuryGasForFeeCap)
    print("Deploying SendUln302 smart contract")
    fargs = (lz_endpoint.address, 1000000000000, 100000)
    send_lib = deploy_contract(
        contracts["SendUln302"], signers["layerzero"], web3, fargs
    )

    # Phase 4: deploy receive msg library
    # constructor(address _endpoint)
    print("Deploying ReceiveUln302 smart contract")
    fargs = (lz_endpoint.address,)
    receive_lib = deploy_contract(
        contracts["ReceiveUln302"], signers["layerzero"], web3, fargs
    )

    # Phase 5: Register send and receive libraries into endpoint library manager
    print("Registering send and receive msg libs with endpoint")
    call_contract_fn(
        lz_endpoint, "registerLibrary", signers["layerzero"], web3, (send_lib.address,)
    )
    call_contract_fn(
        lz_endpoint,
        "registerLibrary",
        signers["layerzero"],
        web3,
        (receive_lib.address,),
    )

    # Phase 6: Deploying Executor and DVN Fee libs
    print("Deploying workers fee libs")
    dvn_fee_lib = deploy_contract(
        contracts["DVNFeeLib"], signers["layerzero"], web3, (pow(10, 18),)
    )
    executor_fee_lib = deploy_contract(
        contracts["ExecutorFeeLib"], signers["layerzero"], web3, (pow(10, 18),)
    )

    # Phase 7: Deploy Verifier
    print("Deploying and configuring " + str(dvns) + " DVN networks")
    # constructor(uint32 _vid,address[] memory _messageLibs,address _priceFeed,address[] memory _signers,uint64 _quorum,address[] memory _admins)
    dvn_contracts = []
    dvn_addresses = {}
    for dvn in range(dvns):
        workers = {}
        for worker in range(dvn_workers):
            index = "dvn_worker" + str(worker + dvns * dvn)
            # convert address to int for later sorting
            workers.update(
                {
                    int(signers[index]["address"].lower(), 16): (
                        signers[index]["address"],
                        signers[index]["private_key"],
                    )
                }
            )
        # we must sorter signers by address othereise contract deployment fails
        sorted_workers = list(OrderedDict(sorted(workers.items())).values())
        sorted_workers_addresses, sorted_workers_keys = map(list, zip(*sorted_workers))
        dvn_id = web3.eth.chain_id + dvn
        fargs = (
            dvn_id,  # not allowed to be 0
            [send_lib.address, receive_lib.address],
            price_feed.address,
            sorted_workers_addresses,
            int(dvn_workers / 2 + 1),  # more than half of the workers should sign
            [signers["verifierAdmin"]["address"]],
        )
        dvn = deploy_contract(contracts["DVN"], signers["layerzero"], web3, fargs)
        call_contract_fn(
            dvn,
            "setWorkerFeeLib",
            signers["verifierAdmin"],
            web3,
            (dvn_fee_lib.address,),
        )
        dvn_contracts.append(dvn)
        dvn_addresses.update(
            {int(dvn.address.lower(), 16): (dvn.address, dvn_id, sorted_workers_keys)}
        )

    # Phase 8: Deploy Executor
    print("Deploying and configuring Executor")
    executor = deploy_contract(contracts["Executor"], signers["layerzero"], web3)
    # function initialize(address _endpoint,address _receiveUln301,address[] memory _messageLibs,address _priceFeed,address _roleAdmin,address[] memory _admins)
    fargs = (
        lz_endpoint.address,
        "0x0000000000000000000000000000000000000000",
        [send_lib.address, receive_lib.address],
        price_feed.address,
        signers["executorRoleAdmin"]["address"],
        [signers["executorAdmin"]["address"]],
    )
    call_contract_fn(executor, "initialize", signers["layerzero"], web3, fargs)
    call_contract_fn(
        executor,
        "setWorkerFeeLib",
        signers["executorAdmin"],
        web3,
        (executor_fee_lib.address,),
    )

    # Phase 9: Configure msg libs with executor and verifier workers
    print("Configuring workers for send library")
    # struct UlnConfig {
    #   uint64 confirmations;
    #   uint8 requiredDVNCount; // 0 indicate DEFAULT, NIL_DVN_COUNT indicate NONE (to override the value of default)
    #   uint8 optionalDVNCount; // 0 indicate DEFAULT, NIL_DVN_COUNT indicate NONE (to override the value of default)
    #   uint8 optionalDVNThreshold; // (0, optionalDVNCount]
    #   address[] requiredDVNs; // no duplicates. sorted an an ascending order. allowed overlap with optionalDVNs
    #   address[] optionalDVNs; // no duplicates. sorted an an ascending order. allowed overlap with requiredDVNs
    # }
    # struct SetDefaultUlnConfigParam {
    #   uint32 eid;
    #   UlnConfig config;
    # }
    # function setDefaultUlnConfigs(SetDefaultUlnConfigParam[] calldata _params)

    # retrieve addresses of all DVN contracts and sort them
    sorted_dvns = list(OrderedDict(sorted(dvn_addresses.items())).values())
    sorted_dvns_addresses, sorted_dvns_ids, sorted_dvns_signers = map(
        list, zip(*sorted_dvns)
    )
    sorted_dvns = list(
        map(
            lambda address, id, signers: {
                "address": address,
                "id": id,
                "signers": signers,
            },
            sorted_dvns_addresses,
            sorted_dvns_ids,
            sorted_dvns_signers,
        )
    )
    # as we run this local, we don't expect many block confirmations
    # so we set it to 1 to make sure we can move along in the verification flow
    fargs = ([(dst_chain, (1, dvns, 0, 0, sorted_dvns_addresses, []))],)
    call_contract_fn(
        send_lib, "setDefaultUlnConfigs", signers["layerzero"], web3, fargs
    )
    # struct SetDefaultExecutorConfigParam {
    #   uint32 eid;
    #   ExecutorConfig config;
    # }
    # struct ExecutorConfig {
    #   uint32 maxMessageSize;
    #   address executor;
    # }
    # function setDefaultExecutorConfigs(SetDefaultExecutorConfigParam[] calldata _params)
    fargs = ([(dst_chain, (10000, executor.address))],)
    call_contract_fn(
        send_lib, "setDefaultExecutorConfigs", signers["layerzero"], web3, fargs
    )

    print("Configuring workers for receive library")
    # same configuration as send library
    fargs = ([(dst_chain, (1, dvns, 0, 0, sorted_dvns_addresses, []))],)
    call_contract_fn(
        receive_lib, "setDefaultUlnConfigs", signers["layerzero"], web3, fargs
    )

    # Phase 10: Setting up workers
    print("Setting up executor and verifier")
    # executor config
    # dstConfigParams[j] = IExecutor.DstConfigParam({
    #    dstEid: dstEid,
    #    baseGas: 5000,
    #    multiplierBps: 10000,
    #    floorMarginUSD: 1e10,
    #    nativeCap: executorValueCap
    # });
    # // dvn config
    # dvnConfigParams[j] = IDVN.DstConfigParam({
    #   dstEid: dstEid,
    #   gas: 5000,
    #   multiplierBps: 10000,
    #   floorMarginUSD: 1e10
    # });
    # function setDstConfig(DstConfigParam[] memory _params)
    fargs = (
        [(dst_chain, 5000, 10000, pow(10, 10), web3.to_wei(Decimal("0.1"), "ether"))],
    )
    call_contract_fn(executor, "setDstConfig", signers["executorAdmin"], web3, fargs)
    fargs = ([(dst_chain, 5000, 10000, pow(10, 10))],)
    for dvn in dvn_contracts:
        call_contract_fn(dvn, "setDstConfig", signers["verifierAdmin"], web3, fargs)

    # Phase 11: Mapping send/receive msg libs to endpoint
    print("Mapping send/receive msg libs to endpoint")
    call_contract_fn(
        lz_endpoint,
        "setDefaultSendLibrary",
        signers["layerzero"],
        web3,
        (dst_chain, send_lib.address),
    )
    call_contract_fn(
        lz_endpoint,
        "setDefaultReceiveLibrary",
        signers["layerzero"],
        web3,
        (dst_chain, receive_lib.address, 0),
    )
    # Phase 12: Deploying and configuring OFT app
    print("deploying OFT app")
    ctkn = deploy_contract(
        contracts["CTKN"],
        signers["oAppOwner"],
        web3,
        ("CarbonToken", "CTKN", lz_endpoint.address, signers["oAppOwner"]["address"]),
    )

    contracts = {
        "CTKN": ctkn.address,
        "ReceiveUln302": receive_lib.address,
        "SendUln302": send_lib.address,
        "Executor": executor.address,
        "DVNs": sorted_dvns,
        "EndpointV2": lz_endpoint.address,
    }
    return ctkn, contracts


"""
wrapper for setting dst peer on src oapp
@ctkn: oft contract object
@dst_chain: destination chain id
@dst_oapp: destination oapp address
@oapp_owner: account object for tx signer
@web3: web3 provider for performing tx
"""


def wire_apps(ctkn, dst_chain, dst_oapp, oapp_owner, web3):
    print("Setting peer for " + str(dst_chain))
    # we must convert this address to bytes32 for correct handling by LZ PacketCodec library
    peer_address = Web3.to_bytes(hexstr=dst_oapp).rjust(32, b"\0")
    call_contract_fn(ctkn, "setPeer", oapp_owner, web3, (dst_chain, peer_address))


"""
function for ouptuting current configuration of LayerZero bridge
@bridge_name: a string to uniquely identify a LayerZero bridge
@chain1,chain2: json description of chain and oApp
@config: pass an exisitng config is available, otherwise we search in file
@return: function creates/updates lz_config.json file with new bridge""
"""


def output_config(bridge_name, chain1, chain2, config=[]):
    if config is None:  # if no config provided, search for file
        if os.path.isfile(lz_config):
            with open(lz_config) as f:
                f.seek(0, os.SEEK_END)  # go to end of file and see if it has data first
                if f.tell():  # if current position is truish (i.e != 0)
                    f.seek(0)  # rewind the file
                    config = json.loads(f.read())  # and read current config
                    print(
                        "Found existing LayzerZero config file. Attempting to update it"
                    )
                else:
                    config = []
                    print(
                        "No LayerZero configuration found. Attempting to create a fresh one."
                    )
                f.close()
        else:
            config = []
            print("No LayerZero configuration found. Attempting to create a fresh one.")

    new_config = {"bridge": bridge_name, "chain1": chain1, "chain2": chain2}
    print("Updating LayerZero setup with new configuration:" + str(new_config))
    config.append(new_config)
    return config  # return config in case its needed for further processing


def main():
    parser = argparse.ArgumentParser(
        description="LayerZero OFT deployment between two chains"
    )
    parser.add_argument(
        "--chain1", type=int, default=1, help="Chain1 number for LZ deployment"
    )
    parser.add_argument(
        "--chain2", type=int, default=2, help="Chain2 number for LZ deployment"
    )
    parser.add_argument(
        "--docker-manager",
        type=str,
        default="worker-001",
        help="Docker swarm manager hostname",
    )
    parser.add_argument("--dvns", type=int, default=2, help="Number of DVNs")
    parser.add_argument(
        "--dvn-workers", type=int, default=2, help="Number of workers per DVN"
    )
    args = parser.parse_args()

    print("Connecting to docker manager")
    docker_client = DockerClient(host="ssh://" + args.docker_manager)
    print("Connecting to source and destination chains")
    chain1_web3, chain1_id, chain1_providers, chain1_ws_providers = get_provider(args.chain1, docker_client)
    chain2_web3, chain2_id, chain2_providers, chain2_ws_providers = get_provider(args.chain2, docker_client)

    # first check if we don't already have a bridge between these two chains
    # search by bridge name which is a concatenation of the two chains ids in ascending order
    if chain1_id < chain2_id:
        bridge_name = str(chain1_id) + "_" + str(chain2_id)
    else:
        bridge_name = str(chain2_id) + "_" + str(chain1_id)

    config = []
    if os.path.isfile(lz_config):
        with open(lz_config) as f:
            f.seek(0, os.SEEK_END)  # go to end of file
            if f.tell():  # if current position is truish (i.e != 0)
                f.seek(0)  # rewind the file for later use
                config = json.loads(f.read())
                for bridge in config:
                    if bridge["bridge"] == bridge_name:
                        print(
                            "Found existing configuration for provided chains. Will skip creation of a new bridge!"
                        )
                        exit()
            f.close()  # file was opened in read mode, close it for future open in write mode

    # if no exisitng bridge found, then we can continue
    print("Retrieving contracts and accounts from local db")
    contracts_abi = get_contracts()
    signers = set_signers(chain1_web3)
    set_signers(chain2_web3)  # will use same set returned by first call

    print("Deploying LayerZero bridge between chains")
    chain1_ctkn, chain1_contracts = deploy_lz(
        chain1_id,
        chain2_id,
        chain1_web3,
        contracts_abi,
        signers,
        args.dvns,
        args.dvn_workers,
    )
    chain2_ctkn, chain2_contracts = deploy_lz(
        chain2_id,
        chain1_id,
        chain2_web3,
        contracts_abi,
        signers,
        args.dvns,
        args.dvn_workers,
    )
    print("Successfuly deployed Layerzero between chains!")

    print("Pairing OFT apps between src and dst chains")
    wire_apps(
        chain1_ctkn, chain2_id, chain2_ctkn.address, signers["oAppOwner"], chain1_web3
    )
    wire_apps(
        chain2_ctkn, chain1_id, chain1_ctkn.address, signers["oAppOwner"], chain2_web3
    )

    print("Saving JSON Config for LayerZero setup")
    # remove DVN signer accounts as we store them in the DVN structure directly
    for dvn in range(args.dvns):
        for worker in range(args.dvn_workers):
            index = "dvn_worker" + str(worker + args.dvns * dvn)
            del signers[index]

    chain1 = {
        "id": args.chain1,
        "chain_id": chain1_id,
        "peer_id": chain2_id,
        "contracts": chain1_contracts,
        "accounts": signers,
        "nodes": chain1_providers,
        "ws_nodes": chain1_ws_providers,
    }
    chain2 = {
        "id": args.chain2,
        "chain_id": chain2_id,
        "peer_id": chain1_id,
        "contracts": chain2_contracts,
        "accounts": signers,
        "nodes": chain2_providers,
        "ws_nodes": chain2_ws_providers,
    }

    config = output_config(bridge_name, chain1, chain2, config)
    with open(lz_config, "w") as outfile:
        json.dump(config, outfile, indent=4, separators=(",", ": "))
    print("Configuration finished. LayzerZero bridge can be used!")


if __name__ == "__main__":
    main()
