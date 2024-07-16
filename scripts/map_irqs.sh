#!/bin/bash

INTERFACE="ens6f0np0"
BASE_PORT=45001
LAST_PORT=45012

# Function to disable and stop irqbalance
disable_irqbalance() {
    echo "Disabling irqbalance service..."
    sudo systemctl disable irqbalance
    sudo systemctl stop irqbalance

    echo "Checking if any irqbalance processes are running..."
    if ps aux | grep irqbalance | grep -v grep > /dev/null; then
        echo "irqbalance is still running. Killing all irqbalance processes..."
        sudo pkill irqbalance
        echo "All irqbalance processes have been killed."
    else
        echo "No irqbalance processes are running."
    fi
}

# Function to remove all existing n-tuple rules
remove_existing_rules() {
    echo "Removing existing n-tuple rules..."
    local rule_id
    while read -r line; do
        if [[ $line =~ ^Filter:\ ([0-9]+) ]]; then
            rule_id=${BASH_REMATCH[1]}
            echo "Deleting rule ID: $rule_id"
            sudo ethtool -N $INTERFACE delete $rule_id
        fi
    done <<< "$(sudo ethtool -n $INTERFACE 2>/dev/null)"
}


# Parse command line argument for starting core ID
if [ $# -eq 0 ]; then
    echo "Usage: $0 <starting_core_id>"
    exit 1
else
    START_CORE_ID=$1
fi

# Ensure START_CORE_ID is a number
if ! [[ "$START_CORE_ID" =~ ^[0-9]+$ ]]; then
    echo "Error: Starting core ID must be a number."
    exit 1
fi

# Disable and stop irqbalance
disable_irqbalance

# Remove all existing n-tuple rules
remove_existing_rules

# Add new n-tuple rules for destination ports 45001 to 45012
echo "Adding new n-tuple rules..."
QUEUE=0
for ((PORT=BASE_PORT; PORT<=LAST_PORT; PORT++)); do
    echo "Adding rule for port $PORT to queue $QUEUE"
    sudo ethtool -N $INTERFACE flow-type udp4 dst-port $PORT action $QUEUE
    QUEUE=$((QUEUE + 1))
done

# Configure RSS
echo "Configuring RSS to have 12 queues..."
sudo ethtool -X $INTERFACE equal 12

# Set IRQ affinity
echo "Setting IRQ affinity..."
CPU_CORE=$START_CORE_ID
IRQ_COUNT=0
for IRQ in $(grep $INTERFACE /proc/interrupts | awk '{print $1}' | tr -d ':'); do
    if [[ $IRQ_COUNT -lt 12 ]]; then
        echo "Setting affinity for IRQ $IRQ to CPU core $CPU_CORE"
        sudo sh -c "echo $((1 << $CPU_CORE)) > /proc/irq/$IRQ/smp_affinity"
        CPU_CORE=$((CPU_CORE + 1))
        IRQ_COUNT=$((IRQ_COUNT + 1))
    else
        break
    fi
done

echo "Script execution completed."
