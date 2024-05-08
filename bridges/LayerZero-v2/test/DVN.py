# Import Library
from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware
import asyncio
from eth_account.messages import encode_defunct
from utils import load_contract, call_contract_fn, print_log

"""
function for retrieveing packet payload from PacketSent event and verifier fees
@event: PacketSent event object
@web3: Web3 provider of the source chain that emited the event
@endpoint: LayerZero endpoint contract object that emited the event
@return: packet header, hash of packet payload, and DVN fees 
"""


def retrieve_packetsent(event, web3, endpoint):
    receipt = web3.eth.wait_for_transaction_receipt(event["transactionHash"])
    result = endpoint.events.PacketSent().process_receipt(receipt)  # Modification
    packet = result[0]["args"]

    print(
        "Found PacketSent event with following payload:\n"
        + str(Web3.to_hex(packet["encodedPayload"]))
        + "\nLooking for DVNFeePaid event"
    )
    packet_header = packet["encodedPayload"][:81]
    payload_hash = Web3.keccak(packet["encodedPayload"][81:])
    if print_log:
        print(
            "Splitting payload into\nheader:"
            + str(Web3.to_hex(packet_header))
            + "\npayload hash:"
            + str(Web3.to_hex(payload_hash))
        )

    event_signature_hash = Web3.keccak(
        text="DVNFeePaid(address[],address[],uint256[])"
    ).hex()
    event_filter = web3.eth.filter(
        {
            "address": packet["sendLibrary"],
            "topics": [event_signature_hash],
        }
    )
    dvn_events = event_filter.get_all_entries()
    if dvn_events is None:
        print("No DVNFeePaid event found. Aborting transaction...")
        exit(1)
    else:  # here we perform a quick and dirt verification of the fee just to mve forward in the workflow
        print("Found DVNFeePaid events...parsing them...")
        receipt = web3.eth.wait_for_transaction_receipt(
            dvn_events[0]["transactionHash"]
        )
        sendLibrary = load_contract("SendUln302", packet["sendLibrary"], web3)
        result = sendLibrary.events.DVNFeePaid().process_receipt(receipt)
        fee = result[0]["args"]

        return packet, packet_header, payload_hash, fee


"""
function for retrieveing packet payload from PacketVerified event 
@web3: Web3 provider of the source chain that emited the event
@endpoint: LayerZero endpoint contract object that emited the event
@return: packet payload 
"""


def retrieve_packetverified(web3, endpoint):
    event_signature_hash = Web3.keccak(
        text="PacketVerified((uint32,bytes32,uint64),address,bytes32)"
    ).hex()
    event_filter = web3.eth.filter(
        {
            "address": endpoint.address,
            "topics": [event_signature_hash],
        }
    )
    dvn_events = event_filter.get_all_entries()
    if len(dvn_events) == 0:
        print("No PacketVerified event found. Aborting transaction...")
        exit(1)

    print("Found PacketVerified event...parsing it...")
    receipt = web3.eth.wait_for_transaction_receipt(dvn_events[0]["transactionHash"])
    result = endpoint.events.PacketVerified().process_receipt(receipt)
    packet = result[0]["args"]

    print("Retrieved following packet verified object:" + str(packet))
    return packet


"""
function that parses the retrieved verifier fees and provides the required paid dvns that must execute the verification flow
@fee: object fee that contains the required_dvns and the paid fees
@dvn_stack: current dvn stack with all DVNs between two chains
@required_dvns: list of DVN objects that must execute the verification flow
"""


def get_required_dvns(fee, dvn_stack):
    required_dvns = []
    for required_dvn in dvn_stack["dst"]:
        dvn = required_dvn["dvn"]
        dvn_is_required = dvn.address in fee["requiredDVNs"]
        if dvn_is_required:
            dvn_index = fee["requiredDVNs"].index(dvn.address)
            if fee["fees"] is None or fee["fees"][dvn_index] == 0:
                print("No fee paid for this DVN...nothing to do about it...")
                continue
            else:
                required_dvns.append(required_dvn)
        else:
            print(
                "DVN with address "
                + dvn.address
                + " not required to verify. Looking for other DVNs"
            )
            continue
    return required_dvns


"""
function that executes verify/commitVerification on behalf of the required DVNs
@required_dvns: list of DVN objects required to verify packet
@web3: Web3 provider for destination chain where packet must be verified 
@verify_fn: function name that must be executed = verify/commitVerification
@receive_lib: receive_lib contract object on destination chain
@uln_config: ULN configuration retrieved from receive library
@packet_header
@payload_hash
@returns: True and PacketVerified event if execution completed successfully
          False if packet was not verified
"""


def execute_dvn_verify(
    required_dvns,
    web3,
    verify_fn,
    receive_lib,
    uln_config,
    packet_header,
    payload_hash,
):
    print("packet_header:", packet_header)
    print("payload_hash:", payload_hash)
    for required_dvn in required_dvns:
        # point to contract object
        dvn = required_dvn["dvn"]
        print(
            "DVN " + dvn.address + " required for " + verify_fn + ". Starting to work"
        )
        # prepare data to call ReceiveUln302.verify through DVN.execute
        expiration = web3.eth.get_block("latest")["timestamp"] + 1000
        verify_args = []
        if verify_fn == "verify":
            verify_args = [packet_header, payload_hash, uln_config[0]]
        else:
            verify_args = [packet_header, payload_hash]
        verify_calldata = receive_lib.encodeABI(fn_name=verify_fn, args=verify_args)
        print("verify_calldata:", verify_calldata)
        verify_hash = dvn.caller.hashCallData(
            required_dvn["id"],
            receive_lib.address,
            verify_calldata,
            expiration,
        )
        verify_hash = encode_defunct(verify_hash)
        if print_log:
            print(
                "Using following varifyCalldata:"
                + str(verify_calldata)
                + "\nand hash of execution parameters:"
                + str(Web3.to_hex(verify_hash.body))
            )
        quorum_signatures = ""
        for signer in required_dvn["signers"]:
            signed_msg = web3.eth.account.sign_message(verify_hash, private_key=signer)
            if print_log:
                print(
                    "Generated following signature encoding:"
                    + signed_msg.signature.hex()
                )
            quorum_signatures += signed_msg.signature.hex()[2:]

        quorum_signatures = Web3.to_hex(hexstr=quorum_signatures)
        execute_params = (
            [
                (
                    required_dvn["id"],
                    receive_lib.address,
                    verify_calldata,
                    expiration,
                    quorum_signatures,
                ),
            ],
        )
        nonce = web3.eth.get_transaction_count(required_dvn["admin"]["address"])
        tx_data = {
            "from": required_dvn["admin"]["address"],
            "gas": 30000000,  # Trying to make it dynamic..
            "gasPrice": web3.eth.gas_price,  # Get Gas Price
            "nonce": nonce,
        }
        try:
            # execute local call first to catch any error first
            # we execute verify_fn on receive_lib impersonated as the DVN contract
            receive_lib.functions[verify_fn](*verify_args).call({"from": dvn.address})
        except Exception as e:
            print(
                "Got following exception during DVN execution of "
                + verify_fn
                + " function:"
                + str(repr(e))
            )
            print("Aborting current transaction")
            exit(1)
        # if no error caught, then we can proceed with real transaction call
        call_contract_fn(dvn, "execute", web3, tx_data, execute_params)
        # check verification state of packet per dvn after execution (only for verify)
        if print_log:
            print(
                "Querying ReceiveUln302 lib for result of "
                + verify_fn
                + ":"
                + str(
                    receive_lib.caller.hashLookup(
                        Web3.keccak(packet_header), payload_hash, dvn.address
                    )
                )
            )
        # for commitVerification is sufficient for one DVN to call it
        # a single commitVerification call deletes the hashLookups of all DVNs
        if verify_fn == "commitVerification":
            break


""""
function to handle PacketSent events from DVN side
@event: PacketSent event
@src_web3: web3 provider from source chain
@dst_web3: web3 provider from destination chain
@src_endpoint: LZ endpoint contract object from source chain
@dst_endpoint: LZ endpoint contract object from destination chain
@dvn_stack: dvn security stack between the two chains 
@oApp: address of oApp contract receiving the message payload
@return: response payloads of PacketSent and PacketVerified events
"""


def handle_PacketSent_DVN(
    event, src_web3, dst_web3, src_endpoint, dst_endpoint, dvn_stack, oApp
):
    packet_sent, packet_header, payload_hash, fee = retrieve_packetsent(
        event, src_web3, src_endpoint
    )
    required_dvns = get_required_dvns(fee, dvn_stack)
    if required_dvns is None:
        print("No required DVNs found for verification! Aborting transaction...")
        exit(1)

    print("DVN fees paid. Starting verification workflow...")
    receive_lib = dst_endpoint.caller.getReceiveLibrary(oApp, src_web3.eth.chain_id)
    receive_lib = load_contract("ReceiveUln302", receive_lib[0], dst_web3)
    uln_config = receive_lib.caller.getUlnConfig(oApp, src_web3.eth.chain_id)
    print(
        "Getting ULN configuration from ReceiveUln302 library:"
        + receive_lib.address
        + "\nMust wait for "
        + str(uln_config[0])
        + " block confirmations before proceeding further"
    )

    # execute verify for each required DVN
    execute_dvn_verify(
        required_dvns,
        dst_web3,
        "verify",
        receive_lib,
        uln_config,
        packet_header,
        payload_hash,
    )
    # check global verification state of packet
    verifiable = receive_lib.caller.verifiable(
        uln_config, Web3.keccak(packet_header), payload_hash
    )
    print(
        "Querying ReceiveUln302 lib to see if packet is verifiable:" + str(verifiable)
    )

    if verifiable is False:
        print("Packet is not verifiable. Cannot commit on it, aborting transaction...")
        exit(1)

    # if packet is verifiable then we can commit on it
    execute_dvn_verify(
        required_dvns,
        dst_web3,
        "commitVerification",
        receive_lib,
        uln_config,
        packet_header,
        payload_hash,
    )

    # listen for PacketVerified to assert commitment of verification
    packet_verified = retrieve_packetverified(dst_web3, dst_endpoint)
    return (packet_sent, packet_verified)


""""
asynchronous defined function to loop
this loop sets up an event filter and is looking for new entires for the "PacketSent" event
this loop runs on a poll interval
"""


async def DVN_PacketSent_loop(
    event_filter,
    poll_interval,
    src_web3,
    dst_web3,
    src_endpoint,
    dst_endpoint,
    dvn_stack,
    oApp,
):
    # as we mimic a DVN, we will look at one event only
    for PacketSent in event_filter.get_all_entries():
        # we only care about first encoutered event
        return handle_PacketSent_DVN(
            PacketSent, src_web3, dst_web3, src_endpoint, dst_endpoint, dvn_stack, oApp
        )
    # if no events arrived, keep polling the filter
    await asyncio.sleep(poll_interval)


"""
function for retrieving dvn stack configuration for LZ deployed between 2 chains
@src_web3, dst_web3: web3 provider objects for the 2 chains
@src_chain, dst_chain: chain identifiers as defined in bridge_config json
@bridge_config: current LayerZero bridge configuration between 2 chains
@return: returns dictionary of DVN contracts and signers for the two chains
"""


def get_dvn_stack(src_web3, dst_web3, src_chain, dst_chain, bridge_config):
    src_stack = []
    dst_stack = []
    # we now that chains share same configuration of DVN stack, thus same number of DVNs
    dvn_num = len(bridge_config[src_chain]["contracts"]["DVNs"])
    for i in range(dvn_num):
        # load contract objects for future usage
        src_dvn = load_contract(
            "DVN",
            bridge_config[src_chain]["contracts"]["DVNs"][i]["address"],
            src_web3,
        )
        dst_dvn = load_contract(
            "DVN",
            bridge_config[dst_chain]["contracts"]["DVNs"][i]["address"],
            dst_web3,
        )
        # register verifierAdmin for transaction signing
        src_web3.middleware_onion.add(
            construct_sign_and_send_raw_middleware(
                bridge_config[src_chain]["accounts"]["verifierAdmin"]["private_key"]
            )
        )
        dst_web3.middleware_onion.add(
            construct_sign_and_send_raw_middleware(
                bridge_config[dst_chain]["accounts"]["verifierAdmin"]["private_key"]
            )
        )
        src_stack.append(
            {
                "dvn": src_dvn,
                "id": bridge_config[src_chain]["contracts"]["DVNs"][i]["id"],
                "signers": bridge_config[src_chain]["contracts"]["DVNs"][i]["signers"],
                "admin": bridge_config[src_chain]["accounts"]["verifierAdmin"],
            }
        )
        dst_stack.append(
            {
                "dvn": dst_dvn,
                "id": bridge_config[dst_chain]["contracts"]["DVNs"][i]["id"],
                "signers": bridge_config[dst_chain]["contracts"]["DVNs"][i]["signers"],
                "admin": bridge_config[dst_chain]["accounts"]["verifierAdmin"],
            }
        )
    dvn_stack = {
        "src": src_stack,
        "dst": dst_stack,
    }
    return dvn_stack


"""
function for executing verification as a DVN worker
@src_web3: web3 provider for src chain
@dst_web3: web3 procider for dst chain
@src_endpoint: LZ EndpointV2 contract object from src chain
@dst_endpoint: LZ EndpointV2 contract object from dst chain
@dvn_stack: dvn configuration which is common for both chains
@oApp: oApp contract address that should receive token/msg 
"""


def verify_tx(src_web3, dst_web3, src_endpoint, dst_endpoint, dvn_stack, oApp):
    # listen for the PacketSent event from src_chain
    print("Listenning for sent event")
    event_signature_hash = Web3.keccak(text="PacketSent(bytes,bytes,address)").hex()
    event_filter = src_web3.eth.filter(
        {
            "toBlock": "pending",
            "address": src_endpoint.address,
            "topics": [event_signature_hash],
        }
    )

    packets = asyncio.run(
        DVN_PacketSent_loop(
            event_filter,
            2,
            src_web3,
            dst_web3,
            src_endpoint,
            dst_endpoint,
            dvn_stack,
            oApp,
        )
    )

    print("Finished off-chain flow for all DVN parties")
    return packets
