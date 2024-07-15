
import argparse
import json
import logging
import os
import subprocess

#BENCHMARK_CONFIGS = [
#    "nperf_jumboframes_max.json",
#    "nperf_jumboframes.json",
#    "nperf_normal.json",
#]

BENCHMARK_CONFIGS = [
#    "nperf_sender-receiver_ratio.json",
##   "nperf_jumboframes.json",
##   "nperf_normal.json",
#    "nperf_multiplex_port_comparison.json",
     "special_sender_same_bytes.json",
     "special_sender_same_bytes.json",
     "special_receiver_same_bytes.json",
     "special_receiver_same_bytes.json",
##   "special_receiver_uneven_gso.json",
##   "special_receiver_burn_in.json",
#    "syscalls_sender_multi_thread.json",
#    "syscalls_sender_multi_thread_gsro.json",
#    "syscalls_sender_multi_thread_mmsgvec.json",
#    "syscalls_sender_multi_thread_mmsgvec_gsro.json",
#    "syscalls_sender_single_thread.json",
#    "syscalls_sender_single_thread_gsro.json",
#    "syscalls_sender_single_thread_mmsgvec.json",
#    "syscalls_receiver_multi_thread.json",
#    "syscalls_receiver_multi_thread_gsro.json",
#    "syscalls_receiver_multi_thread_mmsgvec.json",
#    "syscalls_receiver_multi_thread_mmsgvec_gsro.json",
#    "syscalls_receiver_single_thread.json",
#    "syscalls_receiver_single_thread_gsro.json",
#    "syscalls_receiver_single_thread_mmsgvec.json",
     "uring_sender_multi_thread.json",
     "uring_sender_multi_thread.json",
     "uring_sender_multi_thread_gsro.json",
     "uring_sender_multi_thread_gsro.json",
#    "uring_sender_multi_thread_ring_size.json",
#    "uring_sender_multi_thread_ring_size_gsro.json",
     "uring_sender_single_thread.json",
     "uring_sender_single_thread.json",
     "uring_sender_single_thread.json",
     "uring_sender_single_thread_gsro.json",
     "uring_sender_single_thread_gsro.json",
     "uring_sender_single_thread_gsro.json",
#    "uring_sender_single_thread_ring_size.json",
#    "uring_sender_single_thread_fill_modes.json",
#    "uring_sender_single_thread_sq_poll.json",
     "uring_sender_single_thread_task_work.json",
     "uring_sender_single_thread_task_work.json",
     "uring_sender_single_thread_task_work.json",
     "uring_sender_single_thread_zerocopy.json",
     "uring_sender_single_thread_zerocopy.json",
     "uring_sender_single_thread_zerocopy.json",
     "uring_sender_single_thread_zerocopy_jumboframes.json",
     "uring_sender_single_thread_zerocopy_jumboframes.json",
     "uring_sender_single_thread_zerocopy_jumboframes.json",
     "uring_receiver_multi_thread.json",
     "uring_receiver_multi_thread.json",
     "uring_receiver_multi_thread_gsro.json",
     "uring_receiver_multi_thread_gsro.json",
#    "uring_receiver_multi_thread_ring_size.json",
#    "uring_receiver_multi_thread_ring_size_gsro.json",
#    "uring_receiver_multi_thread_fill_modes.json",
     "uring_receiver_single_thread.json",
     "uring_receiver_single_thread.json",
     "uring_receiver_single_thread.json",
     "uring_receiver_single_thread_gsro.json",
     "uring_receiver_single_thread_gsro.json",
     "uring_receiver_single_thread_gsro.json",
#    "uring_receiver_single_thread_ring_size_multishot.json",
#    "uring_receiver_single_thread_fill_modes.json",
#    "uring_receiver_single_thread_sq_poll.json",
     "uring_receiver_single_thread_task_work.json"
     "uring_receiver_single_thread_task_work.json"
     "uring_receiver_single_thread_task_work.json"
]


RESULTS_FOLDER = "./nperf-benchmark/results/"
CONFIGS_FOLDER = "configs/"
PATH_TO_NPERF_REPO = "./nperf"
MTU_MAX = 9000
#MTU_MAX = 65536 # 64KB on localhost loopback interface possible
MTU_DEFAULT = 1500

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info('Starting main function')
    parser = argparse.ArgumentParser(description="Wrapper script for benchmark.py to benchmark nperf")

    parser.add_argument("receiver_hostname", nargs='?', type=str, help="The hostname of the receiver")
    parser.add_argument("sender_hostname", nargs='?', type=str, help="The hostname of the sender")
    parser.add_argument("receiver_interface", nargs='?', type=str, help="The interface of the receiver")
    parser.add_argument("sender_interface", nargs='?', type=str, help="The interface of the sender")
    parser.add_argument("receiver_ip", nargs='?', default="0.0.0.0", type=str, help="The ip address of the receiver")
    parser.add_argument('--nperf-repo', default=PATH_TO_NPERF_REPO, help='Path to the nperf repository')
    parser.add_argument('--results-folder', default=RESULTS_FOLDER, help='Path to results folder')

    args = parser.parse_args()

    logging.info(f"Receiver hostname/interface: {args.receiver_hostname}/{args.receiver_interface}")
    logging.info(f"Sender hostname/interface: {args.sender_hostname}/{args.sender_interface}")
    logging.info(f"Receiver IP: {args.receiver_ip}")
    path_to_nperf_repo = args.nperf_repo
    results_folder = args.results_folder

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    mtu_changed = False

    for index, config in enumerate(BENCHMARK_CONFIGS):
        logging.info('-------------------')
        logging.info(f"Running nperf with config: {config} ({index + 1}/{len(BENCHMARK_CONFIGS)}")
        logging.info('-------------------')

        if "jumboframes" in config:
            logging.warning(f"Changing MTU to {MTU_MAX}")
            change_mtu(MTU_MAX, args.receiver_hostname, args.receiver_interface, env_vars)
            change_mtu(MTU_MAX, args.sender_hostname, args.sender_interface, env_vars)
            mtu_changed = True
        
        if replace_ip_in_config(CONFIGS_FOLDER + config, args.receiver_ip) is False:
            continue

        if args.receiver_hostname and args.sender_hostname:
            parameters = [CONFIGS_FOLDER + config, '--nperf-repo', path_to_nperf_repo, '--results-folder', results_folder, '--ssh-sender', args.sender_hostname, '--ssh-receiver', args.receiver_hostname]
        else:
            parameters = [CONFIGS_FOLDER + config, '--nperf-repo', path_to_nperf_repo, '--results-folder', results_folder]
            
        try:
            subprocess.run(["python3", 'scripts/benchmark.py'] + parameters, check=True, env=env_vars)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to execute {config}: {e}")

        if mtu_changed:
            logging.warning(f"Changing MTU back to {MTU_DEFAULT}")
            change_mtu(MTU_DEFAULT, args.receiver_hostname, args.receiver_interface, env_vars)
            change_mtu(MTU_DEFAULT, args.sender_hostname, args.sender_interface, env_vars)
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
