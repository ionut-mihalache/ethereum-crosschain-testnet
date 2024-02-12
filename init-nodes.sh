#!/usr/bin/env bash
echo $BASH_VERSION
#title           : start.sh
#description     : Build private containerized ethereum blockchain.
#author		     : ET-TAOUSY Zouhair
#date            : 20111101
#version         : 0.4
#usage		     : sh start.sh
#bash_version    : 4.1.5(1)-release
#modified by     : raresifrim@github
#==========================================================================

number_node=${1:-4}
number_chain=${2:-1}

nodes_path=./seed_data
account_file=seed_data/accounts.json
config_path=seed_data
extra_allocation_file=seed_data/extra_allocation.json
# Generate the cryptographic material for all nodes
createNodes(){
    if [ $number_chain -eq 1 ]
    then
	for i in $(seq 1 $number_node); do
        	if [ -d "$nodes_path/node_$i" ]; then rm -Rf "$nodes_path/node_$i"; fi
                mkdir -p "$nodes_path/node_$i"
		mkdir -p "$nodes_path/node_$i/data"
	done
    else
	for i in $(seq 1 $number_node); do
            	if [ -d "$nodes_path/node_$i" ]; then rm -Rf "$nodes_path/node_$i"; fi
            	mkdir -p "$nodes_path/node_$i"
	    	for j in $(seq 1 $number_chain); do
 			mkdir -p "$nodes_path/node_$i/data$j"
            	done
        done
    fi

    for i in $(seq 1 $number_node); do
        mkdir -p "$nodes_path/node_$i/keys"
        keys_path="$nodes_path/node_$i/keys"
        openssl ecparam -name secp256k1 -genkey -noout | openssl ec -text -noout > $keys_path/key
        echo "node_$i" > $keys_path/password
        cat $keys_path/key | grep pub -A 5 | tail -n +2 | tr -d "\n[:space:]:" | sed "s/^04//" > $keys_path/pub.key
        cat $keys_path/key | grep priv -A 3 | tail -n +2 | tr -d "\n[:space:]:" | sed "s/^00//" > $keys_path/priv.key
    done

# We must generate the genesis for all blockchains -> only difference is the config_file
    if [ $number_chain -eq 1 ]
    then
	config_file="${config_path}/blockchain_config.json"
        python3 poa-genesis-gen.py "$nodes_path" "$number_node" "$config_file" "$account_file" "$extra_allocation_file"
    else
        for i in $(seq 1 $number_chain); do
    	   config_file="${config_path}/blockchain${i}_config.json"
           python3 poa-genesis-gen.py "$nodes_path" "$number_node" "$config_file" "$account_file" "$extra_allocation_file" "$nodes_path/genesis$i.json"
        done
    fi
}
# Import the generated nodes cryptographics materials to the blockchain network
# Skipped, import in docker entry command

# Initialise the nodes data folder with genesis block configuration
# Skipped, init in docker entry command

# Generate the enodes keys to sync nodes each others
getEnodesByIndex(){
    enodes=()
    for i in $(seq 1 $number_node); do
        if [ "$i" != "$1" ]
        then
            if [ $number_chain -eq 1 ]
            then
               port=$((30312+$i))
            else
               port=$((30312 + $i + $((128 * $(($2-1))))))
            fi
            path="${nodes_path}/node_${i}/keys/pub.key"
	    line=$(head -n 1  "$path")
            lf="$(($number_node-1))"
            if [ "$i" -eq "$number_node" ]
            then
                enodes+='"enode://'$line'@'${addresses[${i}]}':'$port'"'$'\r'
            elif [ "$number_node" -eq "$1" ] && [ "$i" -eq "$lf" ]
            then
                if [ $number_chain -eq 1 ]
		then
			enodes+='"enode://'$line'@node'${i}':'$port'"'$'\r'
            	else
 			enodes+='"enode://'$line'@node'${i}'_chain'$2':'$port'"'$'\r'
		fi    
	    else
                if [ $number_chain -eq 1 ]
		then
			enodes+='"enode://'$line'@node'${i}':'$port'",'$'\r'
		else
			enodes+='"enode://'$line'@node'${i}'_chain'$2':'$port'",'$'\r'
		fi
	    fi
        fi
    done
    echo "${enodes[@]}"
}

# Save enodes in every node's data folder & export docker-compose file
saveEnodes(){
    if [ $number_chain -eq 1 ]
    then
	for i in $(seq 1 $number_node); do
        	data_path="$nodes_path/node_$i/data"
        	echo "[" > "$data_path/static-nodes.json"
        	enodes=$(getEnodesByIndex $i)
        	printf "%s\n" "${enodes[@]}" >> "$data_path/static-nodes.json"
        	echo "]" >> "$data_path/static-nodes.json"
      	done
    else
	for k in $(seq 1 $number_chain); do 
		for i in $(seq 1 $number_node); do
           		data_path="$nodes_path/node_$i/data$k"
           		echo "[" > "$data_path/static-nodes.json"
           		enodes=$(getEnodesByIndex $i $k)
           		printf "%s\n" "${enodes[@]}" >> "$data_path/static-nodes.json"
           		echo "]" >> "$data_path/static-nodes.json"
        	done
      	done
    fi
    python3 poa-generate-yaml.py "$number_node" "$number_chain"
}

createNodes
saveEnodes
