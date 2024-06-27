
import argparse
import json
import logging
import os
import subprocess

BENCHMARK_CONFIGS = [
#   "nperf_client-server_ratio.json",
#   "nperf_jumboframes.json",
#   "nperf_multiplex_port_comparison.json",
#   "special_client_same_bytes.json",
#   "special_server_same_bytes.json",
#   "special_server_uneven_gso.json",
#   "syscalls_client_multi_thread.json",
#   "syscalls_client_multi_thread_gsro.json",
#   "syscalls_client_multi_thread_mmsgvec.json",
#   "syscalls_client_single_thread.json",
#   "syscalls_client_single_thread_gsro.json",
#   "syscalls_client_single_thread_mmsgvec.json",
#   "syscalls_server_multi_thread.json",
#   "syscalls_server_multi_thread_gsro.json",
#   "syscalls_server_multi_thread_mmsgvec.json",
#   "syscalls_server_single_thread.json",
#   "syscalls_server_single_thread_gsro.json",
#   "syscalls_server_single_thread_mmsgvec.json",
#   "uring_client_multi_thread.json",
#   "uring_client_multi_thread_ring_size.json",
#   "uring_client_multi_thread_ring_size_gsro.json",
#   "uring_client_single_thread.json",
#   "uring_client_single_thread_fill_modes.json",
#   "uring_client_single_thread_gsro.json",
#   "uring_client_single_thread_ring_size.json",
#   "uring_client_single_thread_sq_poll.json",
#   "uring_client_single_thread_task_work.json",
#   "uring_client_single_thread_zerocopy.json",
#   "uring_server_multi_thread.json",
#   "uring_server_multi_thread_gsro.json",
#   "uring_server_multi_thread_ring_size.json",
#   #"uring_server_multi_thread_ring_size_gsro.json",
    "uring_server_single_thread.json",
#   "uring_server_single_thread_fill_modes.json",
#   "uring_server_single_thread_gsro.json",
#   "uring_server_single_thread_sq_poll.json",
#   "uring_server_single_thread_task_work.json"
]

RESULTS_FOLDER = "./nperf-benchmark/results/"
CONFIGS_FOLDER = "configs/"
PATH_TO_NPERF_REPO = "./nperf"
MTU_MAX = 9000
MTU_DEFAULT = 1500

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info('Starting main function')
    parser = argparse.ArgumentParser(description="Wrapper script for benchmark.py to benchmark nperf")

    parser.add_argument("server_hostname", nargs='?', type=str, help="The hostname of the server")
    parser.add_argument("client_hostname", nargs='?', type=str, help="The hostname of the client")
    parser.add_argument("server_interface", nargs='?', type=str, help="The interface of the server")
    parser.add_argument("client_interface", nargs='?', type=str, help="The interface of the client")
    parser.add_argument("server_ip", nargs='?', default="0.0.0.0", type=str, help="The ip address of the server")
    parser.add_argument('--nperf-repo', default=PATH_TO_NPERF_REPO, help='Path to the nperf repository')
    parser.add_argument('--results-folder', default=RESULTS_FOLDER, help='Path to results folder')

    args = parser.parse_args()

    logging.info(f"Server hostname/interface: {args.server_hostname}/{args.server_interface}")
    logging.info(f"Client hostname/interface: {args.client_hostname}/{args.client_interface}")
    logging.info(f"Server IP: {args.server_ip}")
    path_to_nperf_repo = args.nperf_repo

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    mtu_changed = False

    for index, config in enumerate(BENCHMARK_CONFIGS):
        logging.info('-------------------')
        logging.info(f"Running nperf with config: {config} ({index + 1}/{len(BENCHMARK_CONFIGS)}")
        print(f"Running nperf with config: {config} ({index + 1}/{len(BENCHMARK_CONFIGS)}")
        logging.info('-------------------')

        if "jumboframes" in config:
            logging.warning(f"Changing MTU to {MTU_MAX}")
            change_mtu(MTU_MAX, args.server_hostname, args.server_interface, env_vars)
            change_mtu(MTU_MAX, args.client_hostname, args.client_interface, env_vars)
            mtu_changed = True
        
        if replace_ip_in_config(CONFIGS_FOLDER + config, args.server_ip) is False:
            continue

        if args.server_hostname and args.client_hostname:
            parameters = [CONFIGS_FOLDER + config, '--nperf-repo', path_to_nperf_repo, '--results-folder', RESULTS_FOLDER, '--ssh-client', args.client_hostname, '--ssh-server', args.server_hostname]
        else:
            parameters = [CONFIGS_FOLDER + config, '--nperf-repo', path_to_nperf_repo, '--results-folder', RESULTS_FOLDER]
            
        try:
            subprocess.run(["python3", 'scripts/benchmark.py'] + parameters, check=True, env=env_vars)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to execute {config}: {e}")

        if mtu_changed:
            logging.warning(f"Changing MTU back to {MTU_DEFAULT}")
            change_mtu(MTU_DEFAULT, args.server_hostname, args.server_interface, env_vars)
            change_mtu(MTU_DEFAULT, args.client_hostname, args.client_interface, env_vars)
            mtu_changed = False


def change_mtu(mtu: int, host=None, interface=None, env_vars=None) -> bool:
    if host and interface and env_vars:
        command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {host} 'ifconfig {interface} mtu {mtu} up'"
    else:
        command = f"ifconfig {interface} mtu {mtu} up"

    try:
        subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, env=env_vars)
        logging.info(f"MTU changed to {mtu}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to change MTU: {e}")
        return False

def replace_ip_in_config(config_file: str, ip: str) -> bool:
    logging.info(f"Replacing IP {ip} in config file: {config_file}")

    try:
        with open(config_file, 'r') as file:
            config_data = json.load(file)
    except FileNotFoundError as e:
        logging.error(f"Failed to open config file: {e}")
        return False

    if 'ip' in config_data['parameters']:
        logging.info(f"Replacing IP {config_data['parameters']['ip']} with {ip}")
        config_data['parameters']['ip'] = ip

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
