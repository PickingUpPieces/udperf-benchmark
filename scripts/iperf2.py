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

#DEFAULT_SOCKET_BUFFER_SIZE = 212992
DEFAULT_SOCKET_BUFFER_SIZE = 2129920
DEFAULT_MEASUREMENT_TIME = 15

BENCHMARK_CONFIGS = [
    {"test_name": "iperf2", 
     "amount_threads": 12,
     "jumboframes": False,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--len": 1472,
         "--udp": ""
         }
    },
    {"test_name": "iperf2 TCP", 
     "amount_threads": 12,
     "jumboframes": False,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--len": 1472
         }
    },
    {"test_name": "iperf2 Jumboframes", 
     "amount_threads": 12,
     "jumboframes": True,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--len": 8948,
         "--udp": ""
         }
    },
    {"test_name": "iperf2 Jumboframes TCP", 
     "amount_threads": 12,
     "jumboframes": True,
     "parameter": {
         "--window": DEFAULT_SOCKET_BUFFER_SIZE,
         "--time": DEFAULT_MEASUREMENT_TIME,
         "--len": 8948
         }
    },
#   {"test_name": "iperf2 Jumboframes", 
#    "amount_threads": 12,
#    "jumboframes": True,
#    "parameter": {
#        "--window": DEFAULT_SOCKET_BUFFER_SIZE,
#        "--time": DEFAULT_MEASUREMENT_TIME,
#        "--len": 65507,
#        "--udp": ""
#        }
#   },
#   {"test_name": "iiperf2 Jumboframes TCP", 
#    "amount_threads": 12,
#    "jumboframes": True,
#    "parameter": {
#        "--window": DEFAULT_SOCKET_BUFFER_SIZE,
#        "--time": DEFAULT_MEASUREMENT_TIME,
#        "--len": 65507
#        }
#   },
]

# For every test run, the following parameter are used everytime additionally
DEFAULT_PARAMETER = "-i0 --enhanced --reportstyle=C --sum-only"
DEFAULT_BANDWIDTH = "100G"
#MTU_MAX = 65536 # 64KB on localhost loopback interface possible
MTU_MAX = 9000
MTU_DEFAULT = 1500
SERVER_PORT = 5001
MAX_FAILED_ATTEMPTS = 3

RESULTS_FOLDER = "./results/iperf2/"
IPERF2_REPO = "https://git.code.sf.net/p/iperf2/code"
IPERF2_VERSION = "2-2-0"
PATH_TO_REPO = "./iperf2"
PATH_TO_BINARY = PATH_TO_REPO + "/src/iperf"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_test_server(config: dict, test_name: str, file_name: str, ssh_server: str, results_folder: str, env_vars: dict) -> bool:
    logging.info(f"{test_name}: Running iperf2 server on {ssh_server}")

    command_str = f"{PATH_TO_BINARY} -s {DEFAULT_PARAMETER} -w {config['parameter']['--window']} -t {int(config['parameter']['--time']) + 3}"

    if config['parameter'].get('--udp', 'False') != 'False':
        logging.info(f"Running server in UDP mode")
        command_str += " --udp"

    logging.info(f"Executing command: {command_str}")

    if ssh_server:
        # Modify the command to be executed over SSH
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {ssh_server} '{command_str}'"
        server_process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_vars)
    else:
        # Execute command locally
        server_process = subprocess.Popen(command_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for the server to finish
    try:
        server_output, server_error = server_process.communicate(timeout=(config["parameter"]["--time"] + 10)) # Add 10 seconds as buffer to the client time
    except subprocess.TimeoutExpired:
        logging.error('Server process timed out')
        return False

    if server_output:
        logging.debug('Server output: %s', server_output.decode())
        results_file_path = f'{results_folder}server-{file_name}'.lower().replace(" ", "_").replace("/", "_")
        handle_output(config, server_output.decode(), results_file_path, "server")

        log_file_name = file_name.replace('.csv', '.raw')
        log_file_path = f'{results_folder}server-{log_file_name}'.lower().replace(" ", "_").replace("/", "_")
        handle_output(config, server_output.decode(), log_file_path, "server")

    if server_error:
        logging.error('Server error: %s', server_error.decode())

        log_file_name = file_name.replace('.csv', '.log')
        log_file_path = f'{results_folder}server-{log_file_name}'.lower().replace(" ", "_").replace("/", "_")
        additional_info = f"Test: {test_name} \nConfig: {str(config)}\n"
        handle_output(config, additional_info + server_error.decode(), log_file_path, "server")
        
        return False

    return True

def run_test_client(config: dict, test_name: str, file_name: str, ssh_client: str, results_folder: str, env_vars: dict) -> bool:
    logging.info(f"{test_name}: Running iperf2 client on {ssh_client}")

    client_command = [PATH_TO_BINARY, DEFAULT_PARAMETER, "--bandwidth", DEFAULT_BANDWIDTH]
    for k, v in config['parameter'].items():
        client_command.append(k)
        client_command.append(f"{v}")
    
    command_str = ' '.join(client_command)
    logging.info(f"Executing command: {command_str}")

    if ssh_client:
        # Modify the command to be executed over SSH
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {ssh_client} '{command_str}'"
        client_process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_vars)
    else:
        # Execute command locally
        client_process = subprocess.Popen(command_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        client_output, client_error = client_process.communicate() 
    except subprocess.TimeoutExpired:
        logging.error('Server process timed out')
        return False

    if client_output:
        logging.debug('Client output: %s', client_output.decode())
        results_file_path = f'{results_folder}client-{file_name}'.lower().replace(" ", "_").replace("/", "_")
        handle_output(config, client_output.decode(), results_file_path, "client")

        log_file_name = file_name.replace('.csv', '.raw')
        log_file_path = f'{results_folder}client-{log_file_name}'.lower().replace(" ", "_").replace("/", "_")
        handle_output(config, client_output.decode(), log_file_path, "client")
    if client_error:
        logging.error('Client error: %s', client_error.decode())

        log_file_name = file_name.replace('.csv', '.log')
        log_file_path = f'{results_folder}client-{log_file_name}'.lower().replace(" ", "_").replace("/", "_")
        additional_info = f"Test: {test_name} \nConfig: {str(config)}\n"
        handle_output(config, additional_info + client_error.decode(), log_file_path, "client")
    
        return False

    return True

def main():
    logging.info('Starting main function')

    parser = argparse.ArgumentParser(description="Wrapper script to benchmark iperf2")

    parser.add_argument("server_hostname", type=str, help="The hostname of the server")
    parser.add_argument("client_hostname", type=str, help="The hostname of the client")
    parser.add_argument("server_interface", type=str, help="The interface of the server")
    parser.add_argument("client_interface", type=str, help="The interface of the client")
    parser.add_argument("server_ip", type=str, help="The ip address of the server")

    args = parser.parse_args()

    logging.info(f"Server hostname/interface: {args.server_hostname}/{args.server_interface}")
    logging.info(f"Client hostname/interface: {args.client_hostname}/{args.client_interface}")
    logging.info(f"Server IP: {args.server_ip}")

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    if args.server_hostname == args.client_hostname:
        # Localhost mode
        setup_remote_repo_and_compile(args.server_hostname, PATH_TO_REPO)
    else:
        setup_remote_repo_and_compile(args.server_hostname, PATH_TO_REPO)
        setup_remote_repo_and_compile(args.client_hostname, PATH_TO_REPO)

    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    mtu_changed = False

    logging.warning(f"Changing MTU to {MTU_DEFAULT}")
    change_mtu(MTU_DEFAULT, args.server_hostname, args.server_interface, env_vars)
    change_mtu(MTU_DEFAULT, args.client_hostname, args.client_interface, env_vars)

    for config in BENCHMARK_CONFIGS:
        file_name = get_file_name(config["test_name"])
        config["parameter"]["-c"] = args.server_ip

        logging.info(f"Running iperf2 with config: {config}")

        if config["jumboframes"]:
            logging.warning(f"Changing MTU to {MTU_MAX}")
            change_mtu(MTU_MAX, args.server_hostname, args.server_interface, env_vars)
            change_mtu(MTU_MAX, args.client_hostname, args.client_interface, env_vars)
            mtu_changed = True

        for i in range(1, (config["amount_threads"] + 1)):
            logging.info(f"Executing iperf2 test {config['test_name']} with {i} threads")
            thread_timeout = config["parameter"]["--time"] + 10
            config["parameter"]["--parallel"] = i

            failed_attempts = 0
            for _ in range(0,MAX_FAILED_ATTEMPTS): # Retries, in case of an error
                kill_server_process(SERVER_PORT, args.server_hostname)
                logging.info('Wait for some seconds so system under test can normalize...')
                time.sleep(3)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_server = executor.submit(run_test_server, config, config['test_name'], file_name, args.server_hostname, RESULTS_FOLDER, env_vars)
                    time.sleep(1) # Wait for server to be ready
                    future_client = executor.submit(run_test_client, config, config['test_name'], file_name, args.client_hostname, RESULTS_FOLDER, env_vars)

                    if future_server.result(timeout=thread_timeout) and future_client.result(timeout=thread_timeout):
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
            change_mtu(MTU_DEFAULT, args.server_hostname, args.server_interface, env_vars)
            change_mtu(MTU_DEFAULT, args.client_hostname, args.client_interface, env_vars)
            mtu_changed = False


    logging.info(f"Results stored in: {RESULTS_FOLDER}server-{file_name}")
    logging.info(f"Results stored in: {RESULTS_FOLDER}client-{file_name}")


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

    repo_update_result = execute_command_on_host(ssh_target, f'cd {path_to_repo} && git checkout {IPERF2_VERSION} && git pull')

    if repo_update_result:
        logging.info(f"Repository at {path_to_repo} successfully updated.")
    else:
        logging.info(f"Repository does not exist or is not a Git repo at {path_to_repo}. Attempting to clone.")
        execute_command_on_host(ssh_target, f'mkdir -p {path_to_repo}')
        execute_command_on_host(ssh_target, f'git clone {IPERF2_REPO} {path_to_repo}')
        execute_command_on_host(ssh_target, f'cd {path_to_repo} && git checkout {IPERF2_VERSION}')

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

def kill_server_process(port: str, ssh_server: str):
    logging.info(f'Killing server process on port {port}, if still running')
    try:
        if ssh_server is None:
            # Use lsof and grep to find processes listening on UDP ports in the range 45000 to 45019
            command = "lsof -iUDP | grep ':450[0-1][0-9]' | awk '{print $2}'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
        else:
            # Execute the command remotely if an SSH server is specified
            command = "lsof -iUDP | grep ':450[0-1][0-9]' | awk '{print $2}'"
            result = subprocess.run(['ssh', '-o LogLevel=quiet', '-o StrictHostKeyChecking=no', ssh_server, command], capture_output=True, text=True)
  
        if result.stdout.strip() != '':
            logging.info(f'Found processes: {result.stdout.strip()}')
        pids: list[str] = result.stdout.strip().split('\n')

        for pid in pids:
            if pid:
                logging.warning(f'Killing process {pid} on port {port}')
                if ssh_server is None:
                    os.kill(int(pid), signal.SIGTERM)
                else:
                    subprocess.run(['ssh', '-o LogLevel=quiet', '-o StrictHostKeyChecking=no', ssh_server, f'kill -9 {pid}'], capture_output=True, text=True)
    except Exception as e:
        logging.error(f'Failed to kill process on port {port}: {e}')

def handle_output(config: dict, output: str, file_path: str, mode: str):
    logging.debug(f"Writing output to file: {file_path}")

    if file_path.endswith('.csv'):

        output_lines = output.strip().split('\n')
        header = output_lines[0].split(',')
        row = output_lines[1].split(',')
        output_dict = dict(zip(header, row))
        # Speed is in bytes, convert to Gbit
        speed_gbit = float(output_dict.get('speed', '0')) / float( 1024 * 1024 * 1024 )
        total_data_gbyte = float(output_dict.get('bytes', '0')) / float( 1024 * 1024 * 1024 )

        # Example output of iperf2
        # time,srcaddress,srcport,dstaddr,dstport,transferid,istart,iend,bytes,speed,jitter,errors,datagrams,errpercent,outoforder,writecnt,writeerr,pps
        # +0200:20240622141050.655,192.168.64.2,0,0.0.0.0,5001,-1,0.0,10.0,7844390400,6275636577,0.000,179685,5516005,3.258,0,5336321,0,533642.566123
        logging.debug(f"Parsed output dict: {output_dict}")

        header = ['test_name', 'mode', 'ip', 'amount_threads', 'mss', 'recv_buffer_size', 'send_buffer_size', 'test_runtime_length', 'amount_datagrams', 'amount_data_bytes', 'amount_reordered_datagrams', 'amount_omitted_datagrams', 'total_data_gbyte', 'data_rate_gbit', 'packet_loss']
        row_data = {
            'test_name': config.get('test_name', ''),
            'mode': mode,
            'ip': config.get('parameter', {}).get('-c', ''),
            'amount_threads': config.get('parameter', {}).get('--parallel', '0'),
            'mss': config.get('parameter', {}).get('--len', '0'),
            'recv_buffer_size': config.get('parameter', {}).get('--window', '0'),
            'send_buffer_size': config.get('parameter', {}).get('--window', '0'),
            'test_runtime_length': config.get('parameter', {}).get('--time', '0'),
            'amount_datagrams': output_dict.get('datagrams', '0'),
            'amount_data_bytes': output_dict.get('bytes', '0'),
            'amount_reordered_datagrams': output_dict.get('outoforder', '0'),
            'amount_omitted_datagrams': output_dict.get('errors', '0'),
            'total_data_gbyte': total_data_gbyte,
            'data_rate_gbit': speed_gbit,
            'packet_loss': output_dict.get('errpercent', '0'),
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
    logging.info('Starting iperf2 script')
    main()
    logging.info('Script iperf2 finished')
