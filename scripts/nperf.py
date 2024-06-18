
import argparse
import json
import logging
import os
import subprocess

BENCHMARK_CONFIGS = [
    "syscalls_client_normal.json" 
#    "send_methods_vs_uring_both.json",
#    "sendmmsg_mmsg-vec_with_threads_detailed.json"
]
RESULTS_FILE = "./results/"
CONFIGS_FOLDER = "configs2/"
MTU_MAX = 65536
MTU_DEFAULT = 1500

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info('Starting main function')

    parser = argparse.ArgumentParser(description="Wrapper script for benchmark.py to benchmark nperf")

    parser.add_argument("server_hostname", type=str, help="The hostname of the server")
    parser.add_argument("client_hostname", type=str, help="The hostname of the client")
    parser.add_argument("server_interface", type=str, help="The interface of the server")
    parser.add_argument("client_interface", type=str, help="The interface of the client")
    parser.add_argument("server_ip", type=str, help="The ip address of the server")

    # Parse the arguments
    args = parser.parse_args()

    logging.info(f"Server hostname/interface: {args.server_hostname}/{args.server_interface}")
    logging.info(f"Client hostname/interface: {args.client_hostname}/{args.client_interface}")
    logging.info(f"Server IP: {args.server_ip}")
    path_to_nperf_repo = "./nperf"

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    mtu_changed = False

    for config in BENCHMARK_CONFIGS:
        logging.info(f"Running nperf with config: {config}")
        if mtu_changed:
            logging.warn(f"Changing MTU back to {MTU_DEFAULT}")
            change_mtu(MTU_DEFAULT, args.server_hostname, args.server_interface)
            change_mtu(MTU_DEFAULT, args.client_hostname, args.client_interface)
            mtu_changed = False

        if "max_mtu" in config:
            logging.warn(f"Changing MTU to {MTU_MAX}")
            change_mtu(MTU_MAX, args.server_hostname, args.server_interface)
            change_mtu(MTU_MAX, args.client_hostname, args.client_interface)
            mtu_changed = True
        
        replace_ip_in_config(CONFIGS_FOLDER + config, args.server_ip)

        parameters = [CONFIGS_FOLDER + config, '--nperf-repo', path_to_nperf_repo, '--results-folder', RESULTS_FILE, '--ssh-client', args.client_hostname, '--ssh-server', args.server_hostname]
        try:
            subprocess.run(["python3", 'scripts/benchmark.py'] + parameters, check=True, env=env_vars)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to execute {config}: {e}")

def change_mtu(mtu: int, host: str, interface: str) -> bool:
    try:
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {host} 'ifconfig {interface} mtu {mtu} up'"
        subprocess.run(ssh_command, check=True)
        logging.info("MTU changed to 65536 for loopback interface")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to change MTU: {e}")
        return False

def replace_ip_in_config(config_file: str, ip: str) -> bool:
    logging.info(f"Replacing IP {ip} in config file: {config_file}")
    # Open and read the JSON config file
    with open(config_file, 'r') as file:
        config_data = json.load(file)

    if 'ip' in config_data:
        config_data['ip'] = ip
        # Write updated dictionary back to file
        with open(config_file, 'w') as file:
            json.dump(config_data, file, indent=4)
        logging.info(f"Replaced IP in {config_file}")
        return True
    else:
        logging.error(f"Failed to replace IP in {config_file}")
        return False


if __name__ == '__main__':
    logging.info('Starting nperf script')
    main()
    logging.info('Script nperf finished')
