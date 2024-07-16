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

# Function to calculate CPU mask for a single core
calculate_cpu_mask_for_core() {
    local core_index=$1
    local mask=$((1 << core_index))
    printf "%x" "$mask"
}

# 1. Map interrupts to of queues 0-11 to cores 12-23 
map_interrupts() {
    for queue_num in {0..11}; do
        # Calculate the corresponding core for the queue (12-23 for queues 0-11)
        local core_id=$((queue_num + 12))
        # Calculate the CPU mask for the core
        local cpu_mask=$(calculate_cpu_mask_for_core $core_id)
        # Find the IRQ number for the queue
        local irq_num=$(grep -E "TxRx-$queue_num" /proc/interrupts | cut -d: -f1 | tr -d ' ')
        # Set the smp_affinity for the IRQ to the CPU mask
        echo "Setting IRQ $irq_num (Queue $queue_num) affinity to core $core_id (mask $cpu_mask)"
        echo $cpu_mask > /proc/irq/$irq_num/smp_affinity
    done
}

# 2. Map traffic generated on cpu cores 0-11 to queues 0-11
configure_xps() {
    local start_core=0
    local end_core=11
    local total_cores=$((end_core - start_core + 1))
    local tx_queues=(/sys/class/net/$INTERFACE/queues/tx-*)

    for queue_index in {0..11}; do
        local assigned_core=$((start_core + queue_index % total_cores))
        local cpu_mask=$(calculate_cpu_mask_for_core $assigned_core)
        local txq=${tx_queues[$queue_index]}
        echo "Setting XPS for $txq to CPU mask $cpu_mask (Core $assigned_core)"
        echo $cpu_mask > "$txq"/xps_cpus
    done
}

# Function to configure RSS based on the specified core range
configure_rss() {
    local start_core=$1
    local end_core=$2
    echo "Configuring RSS to have 12 queues..."
    ethtool -X $INTERFACE equal 12

    echo "Setting IRQ affinity..."
    local cpu_core=$start_core
    local irq_count=0
    for irq in $(grep $INTERFACE /proc/interrupts | awk '{print $1}' | tr -d ':'); do
        if [[ $irq_count -lt 12 ]]; then
            echo "Setting affinity for IRQ $irq to CPU core $cpu_core"
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

END_CORE_ID=$((START_CORE_ID + 11))

# Disable and stop irqbalance
disable_irqbalance

# Remove all existing n-tuple rules
remove_existing_rules


# Configure RSS or XPS based on the specified core range
if [ "$START_CORE_ID" -eq 12 ]; then
    map_interrupts
    configure_xps 
else
    configure_rss $START_CORE_ID $END_CORE_ID
fi

echo "Script execution completed."
