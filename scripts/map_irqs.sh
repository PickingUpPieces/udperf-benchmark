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

# INFO: Interrupts with wrapping around
# Map interrupts of queues 0-11 to specified CPU cores
map_interrupts2() {
    local start_core=$1
    local end_core=$((start_core + 11))
    local cpu_core=$1
    local irq_count=0

    for irq in $(grep $INTERFACE /proc/interrupts | awk '{print $1}' | tr -d ':'); do
        echo "Setting affinity for IRQ $irq to CPU core $cpu_core (Mask: $((1 << $cpu_core)) )"
        sudo sh -c "echo $((1 << $cpu_core)) > /proc/irq/$irq/smp_affinity"
        irq_count=$((irq_count + 1))
        cpu_core=$((cpu_core + 1))
        if [ $cpu_core -gt $end_core ]; then
            cpu_core=$start_core
        fi
    done
}

# Map interrupts of queues 0-11 to specified CPU cores
map_interrupts() {
    local cpu_core=$1
    local irq_count=0

    for irq in $(grep $INTERFACE /proc/interrupts | awk '{print $1}' | tr -d ':'); do
        if [[ $irq_count -lt 12 ]]; then
            echo "Setting affinity for IRQ $irq to CPU core $cpu_core (Mask: $((1 << $cpu_core)) )"
            sudo sh -c "echo $((1 << $cpu_core)) > /proc/irq/$irq/smp_affinity"
            cpu_core=$((cpu_core + 1))
            irq_count=$((irq_count + 1))
        else
            break
        fi
    done
}

# Function to configure XPS 1-1 with TX-queues for cores 0-11 
# INFO: Alternative function which sets XPS for each queue to the unused cores
configure_xps2() {
    local start_core=$1
    local end_core=$((start_core + 11))
    local cpu_core=$1
    local tx_queues=$(ls /sys/class/net/$INTERFACE/queues/tx-*/xps_cpus | sort --field-separator='-' -k2n)

    for txq in $tx_queues; do
        echo "Setting XPS for $txq to core $cpu_core (Mask: $((1 << $cpu_core)) )"
        sudo sh -c "echo $((1 << $cpu_core)) > $txq"

        # Wrap around to the start core if we reach the end core
        cpu_core=$((cpu_core + 1))
        if [ $cpu_core -gt $end_core ]; then
            cpu_core=$start_core
        fi
    done
}

# Function to configure XPS 1-1 with TX-queues for cores 0-11 
configure_xps() {
    local cpu_core=$1

    for queue_index in {0..11}; do
        local txq="/sys/class/net/$INTERFACE/queues/tx-$queue_index"
        echo "Setting XPS for $txq to xore $cpu_core (Mask: $((1 << $cpu_core)) )"
        sudo sh -c "echo $((1 << $cpu_core)) > $txq/xps_cpus"
        cpu_core=$((cpu_core + 1))
    done
}

# Function to configure RSS based on the specified core range
configure_rss() {
    local start_core=$1
    echo "Configuring RSS to have 12 queues..."
    ethtool -X $INTERFACE equal 12

    echo "Setting IRQ affinity..."
    local cpu_core=$start_core
    local irq_count=0
    for irq in $(grep $INTERFACE /proc/interrupts | awk '{print $1}' | tr -d ':'); do
        if [[ $irq_count -lt 12 ]]; then
            echo "Setting affinity for IRQ $irq to CPU core $cpu_core (Mask: $((1 << $cpu_core)) )"
            sudo sh -c "echo $((1 << $cpu_core)) > /proc/irq/$irq/smp_affinity"
            cpu_core=$((cpu_core + 1))
            irq_count=$((irq_count + 1))
        else
            break
        fi
    done

    # Add new n-tuple rules for destination ports 45001 to 45012
    echo "Adding new n-tuple rules..."
    QUEUE=0
    for ((PORT=BASE_PORT; PORT<=LAST_PORT; PORT++)); do
        echo "Adding rule for port $PORT to queue $QUEUE"
        sudo ethtool -N $INTERFACE flow-type udp4 dst-port $PORT action $QUEUE
        QUEUE=$((QUEUE + 1))
    done
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


# Configure RSS or XPS based on the specified core range
# When START_CORE_ID is 12, assume it's the sender and configure XPS
if [ "$START_CORE_ID" -eq 12 ]; then
    #map_interrupts $START_CORE_ID
    #map_interrupts2 $START_CORE_ID
    #configure_xps 0
    configure_xps2 $START_CORE_ID
else
    # Remove all existing n-tuple rules
    remove_existing_rules

    configure_rss $START_CORE_ID
fi

echo "Script execution completed."
