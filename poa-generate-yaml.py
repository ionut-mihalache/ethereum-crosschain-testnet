import json
import yaml
import sys
import os
from collections import OrderedDict
# python poa-generate-yaml.py number_node number_chains local_path

number_node = int(sys.argv[1])
number_chains = int(sys.argv[2])
config_file = "./seed_data/blockchain{}_config.json"

if len(sys.argv) > 3:
    local_path = sys.argv[3]
else:
    local_path = os.path.dirname(os.path.abspath(__file__)) + "/seed_data"


# chain_number = 0 -> we generate the node structure that will be deployed as part of a single chain of N nodes
# chain_number > 0 -> we generate the node structure for chain i in a network of M chains of N nodes each
def generate_nodes(chain_number=0, nodes={}):
    for i in range(1, number_node + 1):
        # declare node structure to hold all information
        node = {}
        node["hostname"] = "node_" + str(chain_number) + str(i)
        node["image"] = "ethereum/client-go:release-1.10"

        # declare&define volumes
        volumes = []
        volumes.append(
            "${DATA_PATH_PREFIX}/seed_data/node_"
            + str(i)
            + "/keys/password:/root/files/password:ro"
        )
        volumes.append(
            "${DATA_PATH_PREFIX}/seed_data/node_"
            + str(i)
            + "/keys/priv.key:/root/files/priv.key:ro"
        )
        if chain_number == 0:
            volumes.append(
                "${DATA_PATH_PREFIX}/seed_data/genesis.json:/root/files/genesis.json:ro"
            )
            volumes.append(
                "${DATA_PATH_PREFIX}/seed_data/node_" + str(i) + "/data:/root/data:ro"
            )
        else:
            volumes.append(
                "${DATA_PATH_PREFIX}/seed_data/genesis"
                + str(chain_number)
                + ".json:/root/files/genesis.json:ro"
            )
            volumes.append(
                "${DATA_PATH_PREFIX}/seed_data/node_"
                + str(i)
                + "/data"
                + str(chain_number)
                + ":/root/data:ro"
            )

        # declare&define port forwarding
        ports = []
        if chain_number == 0:
            port = str(30312 + i)
            http_port = str(8502 + i)
            ws_port = str(33444 + i)
        else:
            port = str(30312 + i + (chain_number - 1) * 128)
            http_port = str(8502 + i + (chain_number - 1) * 128)
            ws_port = str(33444 + i + (chain_number - 1) * 128)
        ports.append(http_port + ":" + http_port)
        ports.append(port + ":" + port)
        ports.append(ws_port + ":" + ws_port)

        # create geth command based on chain_id from config file
        if chain_number > 0:
            local_file = config_file.format(chain_number)
        else:
            local_file = config_file.format("")
        with open(local_file, "r") as f:
            config = json.load(f)
            chain_id = config.get("chain_id", 42)

        command = (
            "cp -r /root/data /root/data2 ; "
            "geth account import --datadir /root/data2 --password /root/files/password /root/files/priv.key ; "
            "geth --datadir /root/data2 init /root/files/genesis.json ; "
            "geth --datadir /root/data2 --nodiscover --syncmode full --nodekey /root/files/priv.key --port "
            + str(port)
            + " "
            '--http --http.addr "0.0.0.0" --http.vhosts="*" --http.corsdomain="*" --http.port '
            + str(http_port)
            + " "
            "--http.api db,eth,net,web3,admin,personal,miner,signer:insecure_unlock_protect --networkid "
            + str(chain_id)
            + " "
            "--unlock 0 --password /root/files/password --mine --allow-insecure-unlock --ws --ws.port "
            + str(ws_port)
            + " "
            '--ws.addr "0.0.0.0" --ws.origins="*" --ws.api eth,net,web3'
        )

        # update node structure
        node["command"] = [command]
        node["entrypoint"] = "/bin/sh -c"
        node["volumes"] = volumes
        node["ports"] = ports
        if chain_number == 0:
            nodes.update({"node" + str(i): node})
        else:
            nodes.update({"node" + str(i) + "_chain" + str(chain_number): node})
    # return updated node structure for single chain
    return nodes


yaml_file = {"version": "3"}
nodes = {}
if number_chains == 1:
    # generate node structure for a single chain use-case
    nodes = generate_nodes()
elif number_chains > 1:
    # generate node structure for all chains in a multi-chain environment
    for chain in range(1, number_chains + 1):
        nodes = generate_nodes(chain, nodes)
# update yaml file with final node structure
yaml_file["services"] = nodes
stream = open("docker-compose.yaml", "w")
yaml.dump(yaml_file, stream)

# node['command']= ("/bin/sh -c '"
#                     "cp -r /root/data /root/data2;
#                     'geth account import  --datadir /root/data2 --password /root/files/password /root/files/priv.key; '
#                     'geth --datadir  /root/data2 init /root/files/genesis.json; ' +
#                     'geth --datadir /root/data2 --nodiscover --syncmode full --nodekey /root/files/priv.key --port '+ str(http_port)+
#                     ' --http --http.addr "0.0.0.0" --http.vhosts="*" --http.corsdomain="*" --http.port '+str(port)+
#                     ' --http.api db,eth,net,web3,admin,personal,miner,signer:insecure_unlock_protect  --networkid '+str(chain_id)+
#                     ' --unlock 0 --password /root/files/password --mine --allow-insecure-unlock  --ws --ws.port '+str(ws_port)+
#                     ' --ws.addr "0.0.0.0" --ws.origins="*" --ws.api eth,net,web3')
