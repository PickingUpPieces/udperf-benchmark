import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime
import json
import logging
import os
import signal
import subprocess
import time

DEFAULT_SOCKET_BUFFER_SIZE = 212992
DEFAULT_MEASUREMENT_TIME = 10
DEFAULT_BANDWIDTH = "100G"

BENCHMARK_CONFIGS = [
    {"test_name": "multi_thread", 
     "amount_threads": 12,
     "jumboframes": False,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--length": 1472,
         "--udp": ""
         }
    },
    {"test_name": "multi_thread_jumboframes", 
     "amount_threads": 12,
     "jumboframes": True,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--length": 8948,
         "--udp": ""
         }
    },
    {"test_name": "multi_thread_tcp", 
     "amount_threads": 12,
     "jumboframes": False,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--length": 1472
         }
    },
    {"test_name": "multi_thread_jumboframes_tcp", 
     "amount_threads": 12,
     "jumboframes": True,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--length": 8948
         }
    }
]

DEFAULT_PARAMETER_SENDER = f"-i0 --dont-fragment --repeating-payload --json --bandwidth {DEFAULT_BANDWIDTH}"
DEFAULT_PARAMETER_RECEIVER = "--receiver -i0 --one-off --json"
MTU_MAX = 9000
MTU_DEFAULT = 1500
RECEIVER_PORT = 5001
MAX_FAILED_ATTEMPTS = 3

RESULTS_FOLDER = "./results/iperf3/"
IPERF3_REPO = "https://github.com/esnet/iperf.git" 
IPERF3_VERSION = "3.17.1"
PATH_TO_REPO = "./iperf3"
PATH_TO_BINARY = PATH_TO_REPO + "/src/iperf3"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_test_receiver(config: dict, test_name: str, file_name: str, ssh_receiver: str, results_folder: str, env_vars: dict) -> bool:
    logging.info(f"{test_name}: Running iperf3 receiver on {ssh_receiver}")

    command_str = f"{PATH_TO_BINARY} {DEFAULT_PARAMETER_RECEIVER}"
    logging.info(f"Executing command: {command_str}")

    if ssh_receiver:
        # Modify the command to be executed over SSH
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {ssh_receiver} '{command_str}'"
        receiver_process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_vars)
    else:
        # Execute command locally
        receiver_process = subprocess.Popen(command_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for the receiver to finish
    try:
        receiver_output, receiver_error = receiver_process.communicate(timeout=(config["parameter"]["--time"] + 10)) # Add 10 seconds as buffer to the sender time
    except subprocess.TimeoutExpired:
        logging.error('Receiver process timed out')
        return False

    if receiver_output:
        logging.debug('Receiver output: %s', receiver_output.decode())
        results_file_path = f'{results_folder}iperf3-receiver-{file_name}'
        handle_output(config, receiver_output.decode(), results_file_path, "receiver")

        log_file_name = file_name.replace('.csv', '.raw')
        log_file_path = f'{results_folder}iperf3-receiver-{log_file_name}'
        handle_output(config, receiver_output.decode(), log_file_path, "receiver")

    if receiver_error:
        logging.error('Receiver error: %s', receiver_error.decode())

        log_file_name = file_name.replace('.csv', '.log')
        log_file_path = f'{results_folder}iperf3-receiver-{log_file_name}'
        additional_info = f"Test: {test_name} \nConfig: {str(config)}\n"
        handle_output(config, additional_info + receiver_error.decode(), log_file_path, "receiver")
        
        return False    

    return True


def run_test_sender(config: dict, test_name: str, file_name: str, ssh_sender: str, results_folder: str, env_vars: dict) -> bool:
    logging.info(f"{test_name}: Running iperf3 sender on {ssh_sender}")

    sender_command = [PATH_TO_BINARY, DEFAULT_PARAMETER_SENDER]
    for k, v in config['parameter'].items():
        sender_command.append(k)
        sender_command.append(f"{v}")
    
    command_str = ' '.join(sender_command)
    logging.info(f"Executing command: {command_str}")

    if ssh_sender:
        # Modify the command to be executed over SSH
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {ssh_sender} '{command_str}'"
        sender_process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_vars)
    else:
        # Execute command locally
        sender_process = subprocess.Popen(command_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        sender_output, sender_error = sender_process.communicate() 
    except subprocess.TimeoutExpired:
        logging.error('Receiver process timed out')
        return False

    if sender_output:
        logging.debug('Sender output: %s', sender_output.decode())
        results_file_path = f'{results_folder}iperf3-sender-{file_name}'
        handle_output(config, sender_output.decode(), results_file_path, "sender")

        log_file_name = file_name.replace('.csv', '.raw')
        log_file_path = f'{results_folder}iperf3-sender-{log_file_name}'
        handle_output(config, sender_output.decode(), log_file_path, "sender")
    if sender_error:
        logging.error('Sender error: %s', sender_error.decode())
        log_file_name = file_name.replace('.csv', '.log')
        log_file_path = f'{results_folder}iperf2-receiver-{log_file_name}'
        additional_info = f"Test: {test_name} \nConfig: {str(config)}\n"
        handle_output(config, additional_info + sender_error.decode(), log_file_path, "sender")
    
        if "warning" in sender_error.decode() and "error" not in sender_error.decode():
            logging.info('Assuming sender error is a warning, continuing')
            return True
        else:
            return False

    return True


def main():
    logging.info('Starting main function')
    parser = argparse.ArgumentParser(description="Wrapper script to benchmark iperf3")

    parser.add_argument("receiver_hostname", type=str, help="The hostname of the receiver")
    parser.add_argument("sender_hostname", type=str, help="The hostname of the sender")
    parser.add_argument("receiver_interface", type=str, help="The interface of the receiver")
    parser.add_argument("sender_interface", type=str, help="The interface of the sender")
    parser.add_argument("receiver_ip", type=str, help="The ip address of the receiver")

    args = parser.parse_args()

    logging.info(f"Receiver hostname/interface: {args.receiver_hostname}/{args.receiver_interface}")
    logging.info(f"Sender hostname/interface: {args.sender_hostname}/{args.sender_interface}")
    logging.info(f"Receiver IP: {args.receiver_ip}")

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    if args.receiver_hostname == args.sender_hostname:
        # Localhost mode
        setup_remote_repo_and_compile(args.receiver_hostname, PATH_TO_REPO)
    else:
        setup_remote_repo_and_compile(args.receiver_hostname, PATH_TO_REPO)
        setup_remote_repo_and_compile(args.sender_hostname, PATH_TO_REPO)

    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    mtu_changed = False
    logging.warning(f"Changing MTU to {MTU_DEFAULT}")
    change_mtu(MTU_DEFAULT, args.receiver_hostname, args.receiver_interface, env_vars)
    change_mtu(MTU_DEFAULT, args.sender_hostname, args.sender_interface, env_vars)

    for config in BENCHMARK_CONFIGS:
        file_name = get_file_name(config["test_name"])
        config["parameter"]["-c"] = args.receiver_ip

        logging.info(f"Running iperf3 with config: {config}")

        if config["jumboframes"]:
            logging.warning(f"Changing MTU to {MTU_MAX}")
            change_mtu(MTU_MAX, args.receiver_hostname, args.receiver_interface, env_vars)
            change_mtu(MTU_MAX, args.sender_hostname, args.sender_interface, env_vars)
            mtu_changed = True

        for i in range(1, (config["amount_threads"] + 1)):
            logging.info(f"Executing iperf3 test {config['test_name']} with {i} threads")
            thread_timeout = config["parameter"]["--time"] + 10
            config["parameter"]["--parallel"] = i

            failed_attempts = 0
            for _ in range(0,MAX_FAILED_ATTEMPTS): # Retries, in case of an error
                kill_receiver_process(RECEIVER_PORT, args.receiver_hostname)
                logging.info('Wait for some seconds so system under test can normalize...')
                time.sleep(3)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_receiver = executor.submit(run_test_receiver, config, config['test_name'], file_name, args.receiver_hostname, RESULTS_FOLDER, env_vars)
                    time.sleep(1) # Wait for receiver to be ready
                    future_sender = executor.submit(run_test_sender, config, config['test_name'], file_name, args.sender_hostname, RESULTS_FOLDER, env_vars)

                    if future_receiver.result(timeout=thread_timeout) and future_sender.result(timeout=thread_timeout):
                        logging.info(f'Test run "{config["test_name"]}" finished successfully')
                        break
                    else:
                        logging.error(f'Test run {config["test_name"]} failed, retrying')
                        failed_attempts += 1

            if failed_attempts == MAX_FAILED_ATTEMPTS:
                logging.error('Maximum number of failed attempts reached. Dont execute next repetition.')
                break

        if mtu_changed:
            logging.warning(f"Changing MTU back to {MTU_DEFAULT}")
            change_mtu(MTU_DEFAULT, args.receiver_hostname, args.receiver_interface, env_vars)
            change_mtu(MTU_DEFAULT, args.sender_hostname, args.sender_interface, env_vars)
            mtu_changed = False


    logging.info(f"Results stored in: {RESULTS_FOLDER}receiver-{file_name}")
    logging.info(f"Results stored in: {RESULTS_FOLDER}sender-{file_name}")


##################################
# Helper functions
##################################

def get_file_name(file_name: str) -> str:
    timestamp = int(time.time())
    dt_object = datetime.datetime.fromtimestamp(timestamp)
    formatted_datetime = dt_object.strftime("%m-%d-%H:%M")
    return f"{file_name}-{formatted_datetime}.csv"

def setup_remote_repo_and_compile(ssh_target, path_to_repo):
    logging.info(f"Setting up repository and compile code on {ssh_target}")
    repo_update_result = execute_command_on_host(ssh_target, f'cd {path_to_repo} && git checkout {IPERF3_VERSION} && git pull')

    if repo_update_result:
        logging.info(f"Repository at {path_to_repo} successfully updated.")
    else:
        logging.info(f"Repository does not exist or is not a Git repo at {path_to_repo}. Attempting to clone.")
        execute_command_on_host(ssh_target, f'mkdir -p {path_to_repo}')
        execute_command_on_host(ssh_target, f'git clone {IPERF3_REPO} {path_to_repo}')
        execute_command_on_host(ssh_target, f'cd {path_to_repo} && git checkout {IPERF3_VERSION}')

    execute_command_on_host(ssh_target, f'cd {path_to_repo} && ./configure')
    execute_command_on_host(ssh_target, f'cd {path_to_repo} && make')


def execute_command_on_host(host: str, command: str) -> bool:
    logging.info(f"Executing {command} on {host}")
    try:
        env_vars = os.environ.copy()
        # Ensure SSH_AUTH_SOCK is forwarded if available
        if 'SSH_AUTH_SOCK' in os.environ:
            env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {host} '{command}'"
        result = subprocess.run(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, env=env_vars)
        
        if result.returncode == 0:
            logging.info(f"Command {command} completed successfully on {host}: {result.stdout}")
            return True
        else:
            logging.error(f"Command {command} failed on {host}: {result.stderr}")
            return False
    except Exception as e:
        logging.error(f"Error executing setup on {host}: {str(e)}")
        return False


def change_mtu(mtu: int, host: str, interface: str, env_vars: dict) -> bool:
    try:
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {host} 'ifconfig {interface} mtu {mtu} up'"
        subprocess.run(ssh_command, stdout=subprocess.PIPE, shell=True, stderr=subprocess.PIPE, check=True, env=env_vars)
        logging.info(f"MTU changed to {mtu} for {interface} interface")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to change MTU: {e}")
        return False


def kill_receiver_process(port: str, ssh_receiver: str):
    logging.info(f'Killing receiver process on port {port}, if still running')
    try:
        if ssh_receiver is None:
            # Use lsof and grep to find processes listening on UDP ports in the range 45000 to 45019
            command = "lsof -iUDP | grep ':450[0-1][0-9]' | awk '{print $2}'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
        else:
            # Execute the command remotely if an SSH receiver is specified
            command = "lsof -iUDP | grep ':450[0-1][0-9]' | awk '{print $2}'"
            result = subprocess.run(['ssh', '-o LogLevel=quiet', '-o StrictHostKeyChecking=no', ssh_receiver, command], capture_output=True, text=True)
  
        if result.stdout.strip() != '':
            logging.info(f'Found processes: {result.stdout.strip()}')
        pids: list[str] = result.stdout.strip().split('\n')

        for pid in pids:
            if pid:
                logging.warning(f'Killing process {pid} on port {port}')
                if ssh_receiver is None:
                    os.kill(int(pid), signal.SIGTERM)
                else:
                    subprocess.run(['ssh', '-o LogLevel=quiet', '-o StrictHostKeyChecking=no', ssh_receiver, f'kill -9 {pid}'], capture_output=True, text=True)
    except Exception as e:
        logging.error(f'Failed to kill process on port {port}: {e}')


def handle_output(config: dict, output: str, file_path: str, mode: str):
    logging.debug(f"Writing output to file: {file_path}")

    if file_path.endswith('.csv'):

        # The output is in JSON format, parse it
        output_dict = json.loads(output)
        logging.debug(f"Parsed output dict: {output_dict}")
        
        if mode == "sender":
            stats_dict: dict = output_dict.get('end', {}).get('sum_sent', {})
        else:
            stats_dict: dict = output_dict.get('end', {}).get('sum_received', {})

        # Speed is in bytes, convert to Gbit
        speed_gbit = float(stats_dict.get('bits_per_second', '')) / float( 1024 * 1024 * 1024 )
        total_data_gbyte = float(stats_dict.get('bytes', '')) / float( 1024 * 1024 * 1024 )

        header = ['test_name', 'mode', 'ip', 'amount_threads', 'mss', 'recv_buffer_size', 'send_buffer_size', 'test_runtime_length', 'amount_datagrams', 'amount_data_bytes', 'amount_omitted_datagrams', 'total_data_gbyte', 'data_rate_gbit', 'packet_loss', 'cpu_utilization_percent']
        row_data = {
            'test_name': config.get('test_name', ''),
            'mode': mode,
            'ip': config.get('parameter', {}).get('-c', ''),
            'amount_threads': config.get('parameter', {}).get('--parallel', '0'),
            'mss': config.get('parameter', {}).get('--length', ''),
            'recv_buffer_size': config.get('parameter', {}).get('--window', ''),
            'send_buffer_size': config.get('parameter', {}).get('--window', ''),
            'test_runtime_length': config.get('parameter', {}).get('--time', ''),
            'amount_datagrams': stats_dict.get('packets', ''),
            'amount_data_bytes': stats_dict.get('bytes', ''),
            'amount_omitted_datagrams': stats_dict.get('lost_packets', ''),
            'total_data_gbyte': total_data_gbyte,
            'data_rate_gbit': speed_gbit,
            'packet_loss': stats_dict.get('lost_percent', ''),
            'cpu_utilization_percent': output_dict['end']['cpu_utilization_percent']['host_total']
        }

        file_exists = os.path.isfile(file_path) and os.path.getsize(file_path) > 0

        with open(file_path, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=header)

            if not file_exists:
                writer.writeheader()

            writer.writerow(row_data)
    
    elif file_path.endswith('.log'):
        with open(file_path, 'a') as file:
            file.write("Test: " + config["test_name"] + '\n')
            file.write("Used Config: " + str(config) + '\n')
            file.write(output)
    elif file_path.endswith('.raw'):
        with open(file_path, 'a') as file:
            file.write(str(config))
            file.write(output)
    else:
        logging.error(f"Unknown file extension for file: {file_path}")
    

if __name__ == '__main__':
    logging.info('Starting iperf3 script')
    main()
    logging.info('Script iperf3 finished')
