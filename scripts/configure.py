import argparse
import logging
import subprocess

RESULTS_FILE = "../results/configure.txt"
# UDP socket buffer sizes
NEw_WMEM_MAX = 26214400  # 25MB
NEw_RMEM_MAX = 26214400  # 25MB
NEw_NETDEV_MAX_BACKLOG = 5000


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=RESULTS_FILE, filemode='a')

def execute_command(command: str):
    with open(RESULTS_FILE, 'a') as results_file:
        subprocess.run(command, shell=True, stdout=results_file, stderr=results_file)
    logging.info('----------------------')

def main():
    parser = argparse.ArgumentParser(description="Retrieving system information of host")
    parser.add_argument("interface", type=str, help="The network interface")
    parser.add_argument("ip", type=str, help="The IP address of the network interface")
    args = parser.parse_args()

    logging.info(f'Interface {args.interface} with IP {args.ip}')
    logging.info('----------------------')

    logging.info("Installing required packages")
    install_packages = "apt install -y ethtool net-tools"
    execute_command(install_packages)

    logging.info("Install cargo ")
    install_cargo = "curl https://sh.rustup.rs -sSf | sh -s -- -y"
    execute_command(install_cargo)

    logging.info("Turning off Hyperthreading")
    turn_off_HT = "echo off | tee /sys/devices/system/cpu/smt/control"
    execute_command(turn_off_HT)


    logging.info("Configuring interfaces")
    # Inside main function, after the existing code

    # Construct the command to set the IP address
    set_ip_command = f"ip addr add {args.ip}/24 dev {args.interface}"
    execute_command(set_ip_command)

    # Bring the interface up
    bring_interface_up_command = f"ip link set {args.interface} up"
    execute_command(bring_interface_up_command)

    logging.info(f"Configured IP address {args.ip} on {args.interface}")

    logging.info("Inreasing socket buffer maximum size")

    increase_wmem_max = f"sysctl -w net.core.wmem_max={NEw_WMEM_MAX}"
    increase_rmem_max = f"sysctl -w net.core.rmem_max={NEw_RMEM_MAX}"
    increase_netdev_max_backlog = f"sysctl -w net.core.netdev_max_backlog={NEw_NETDEV_MAX_BACKLOG}"
    execute_command(increase_wmem_max)
    execute_command(increase_rmem_max)
    execute_command(increase_netdev_max_backlog)


if __name__ == '__main__':
    logging.info('Starting sysinfo script')
    main()
    logging.info('Script sysinfo finished')