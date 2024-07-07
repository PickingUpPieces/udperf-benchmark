#!/bin/bash

INTERFACE="ens6f0np0"
BASE_PORT=45001
LAST_PORT=45012
QUEUE=0

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

# Disable and stop irqbalance
disable_irqbalance

# Remove all existing n-tuple rules
remove_existing_rules

# Add new n-tuple rules for destination ports 45001 to 45012
echo "Adding new n-tuple rules..."
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
CPU_CORE=0
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
