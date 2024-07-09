from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
import signal
import subprocess
import argparse
import json
import time
import logging
import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
PATH_TO_RESULTS_FOLDER = './results/nperf'
PATH_TO_NPERF_REPO = '/root/nperf'
NPERF_REPO = 'https://github.com/PickingUpPieces/nperf'
NPERF_REPO_BRANCH = 'develop'
PATH_TO_NPERF_BIN = '/target/release/nperf'
MAX_FAILED_ATTEMPTS = 3

def parse_config_file(json_file_path: str):
    with open(os.path.abspath(json_file_path), 'r') as json_file:
        data = json.load(json_file)

    logging.debug('Read test config: %s', data)

    global_parameters = data.pop('parameters', data)
    logging.debug('Global parameters: %s', global_parameters)
    repetitions = global_parameters.pop('repetitions', 1)

    test_configs = []

    for test_name, test_runs in data.items():
        logging.debug('Processing test %s', test_name)
        test_parameters = test_runs.pop('parameters', {})
        logging.debug('Test specific parameters: %s', test_parameters)

        test_config = {
            'test_name': test_name,
            'runs': [],
        }

        for run_name, run_config in test_runs.items():
            logging.debug('Processing run "%s" with config: %s', run_name, run_config)

            # Add test parameters first
            run_config_sender = {**test_parameters, **run_config['sender']}
            run_config_receiver = {**test_parameters, **run_config['receiver']}

            # Add global parameters at last
            run_config_sender = {**global_parameters, **run_config_sender}
            run_config_receiver = {**global_parameters, **run_config_receiver}

            run = {
                'run_name': run_name,
                'repetitions': run_config.get('repetitions', repetitions),
                'sender': run_config_sender,
                'receiver': run_config_receiver 
            }
            logging.debug('Complete run config: %s', run)

            test_config["runs"].append(run)

        test_configs.append(test_config)

    return test_configs

def load_json(json_str):
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def run_test_sender(run_config, test_name: str, file_name: str, results_folder: str, ssh_sender=None) -> bool:
    logging.debug('Running sender test with config: %s', run_config)

    # Build sender command
    sender_command = [nperf_binary, 'sender', '--output-format=file', f'--output-file-path=\"{results_folder}sender-{file_name}\"', f'--label-test=\"{test_name}\"', f'--label-run=\"{run_config["run_name"]}\"']
    
    for k, v in run_config["sender"].items():
        if v is not False:
            if v is True:
                sender_command.append(f'--{k}')
            else:
                sender_command.append(f'--{k}')
                sender_command.append(f'{v}')
    
    command_str = ' '.join(sender_command)
    logging.debug('Starting sender with command: %s', command_str)

    env_vars = os.environ.copy()
    env_vars['RUST_LOG'] = 'error'
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    if ssh_sender:
        # Modify the command to be executed over SSH
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {ssh_sender} '{command_str}'"
        sender_process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_vars)
    else:
        # Execute command locally
        sender_process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'RUST_LOG': 'error'})

    # Wait for the sender to finish
    sender_output, sender_error = sender_process.communicate()
    if sender_output:
        logging.debug('Sender output: %s', sender_output.decode())
    if sender_error:
        logging.error('Sender error: %s', sender_error.decode())
        # Only write to log file if SSH is not used
        if ssh_sender is None:
            log_file_name = file_name.replace('.csv', '.log')
            log_file_path = f'{results_folder}sender-{log_file_name}'

            with open(log_file_path, 'a') as log_file:
                log_file.write("Test: " + test_name + " Run: " + run_config["run_name"] + '\n')
                log_file.write("Config: " + str(run_config) + '\n')
                log_file.write(sender_error.decode())

        return False

    return True

def run_test_receiver(run_config, test_name: str, file_name: str, results_folder: str, ssh_receiver=None) -> bool:
    logging.debug('Running receiver test with config: %s', run_config)
    # Replace with file name
    receiver_command = [nperf_binary, 'receiver', '--output-format=file', f'--output-file-path=\"{results_folder}receiver-{file_name}\"', f'--label-test=\"{test_name}\"', f'--label-run=\"{run_config["run_name"]}\"']
    
    for k, v in run_config['receiver'].items():
        if v is not False:
            if v is True:
                receiver_command.append(f'--{k}')
            else:
                receiver_command.append(f'--{k}')
                receiver_command.append(f'{v}')
    
    command_str = ' '.join(receiver_command)
    logging.debug('Starting receiver with command: %s', command_str)

    env_vars = os.environ.copy()
    env_vars['RUST_LOG'] = 'error'
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    if ssh_receiver:
        # Modify the command to be executed over SSH
        ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {ssh_receiver} '{command_str}'"
        receiver_process = subprocess.Popen(ssh_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env_vars)
    else:
        # Execute command locally
        receiver_process = subprocess.Popen(command_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={'RUST_LOG': 'error'})

    # Wait for the receiver to finish
    try:
        receiver_output, receiver_error = receiver_process.communicate(timeout=(run_config["sender"]["time"] + 10)) # Add 10 seconds as buffer to the sender time
    except subprocess.TimeoutExpired:
        logging.error('Receiver process timed out')
        return False

    # Check if the receiver finished 
    receiver_did_not_finish = False
    if receiver_process.poll() is None:
        logging.error('Receiver did not finish, retrying test')
        receiver_process.kill()
        receiver_did_not_finish = True
    
    if receiver_output:
        logging.debug('Receiver output: %s', receiver_output.decode())
    if receiver_error:
        logging.error('Receiver error: %s', receiver_error.decode())
        # Only write to log file if SSH is not used
        if ssh_receiver is None:
            log_file_name = file_name.replace('.csv', '.log')
            log_file_path = f'{results_folder}receiver-{log_file_name}'
        
            with open(log_file_path, 'a') as log_file:
                log_file.write("Test: " + test_name + " Run: " + run_config["run_name"] + '\n')
                log_file.write("Config: " + str(run_config) + '\n')
                log_file.write(receiver_error.decode())
        return False

    if receiver_did_not_finish:
        return False

    logging.debug('Returning results: %s', receiver_output)
    return True
 
def test_ssh_connection(ssh_address: str):
    try:
        result = subprocess.run(['ssh', '-o LogLevel=quiet', '-o StrictHostKeyChecking=no', ssh_address, 'echo ok'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if result.stdout.decode().strip() == 'ok':
            logging.info(f"SSH connection to {ssh_address} successful.")
            return True
        else:
            logging.error(f"SSH connection to {ssh_address} failed. Error: {result.stderr.decode()}")
            return False
    except subprocess.TimeoutExpired:
        logging.error(f"SSH connection to {ssh_address} timed out.")
        return False
    except Exception as e:
        logging.error(f"Error testing SSH connection to {ssh_address}: {e}")
        return False

def get_file_name(file_name: str) -> str:
    timestamp = int(time.time())
    dt_object = datetime.fromtimestamp(timestamp)
    formatted_datetime = dt_object.strftime("%m-%d-%H:%M")
    return f"{file_name}-{formatted_datetime}.csv"

def kill_receiver_process(port: str, ssh_receiver=None):
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

def main():
    logging.debug('Starting main function')

    parser = argparse.ArgumentParser(description='Benchmark nperf.')
    parser.add_argument('config_file', nargs='?', help='Path to the JSON configuration file')
    parser.add_argument('results_file', nargs='?', default='test_results.csv', help='Path to the CSV file to write the results')
    parser.add_argument('--results-folder', default=PATH_TO_RESULTS_FOLDER, help='Path to results folder')
    parser.add_argument('--nperf-bin', default=PATH_TO_NPERF_REPO + PATH_TO_NPERF_BIN, help='Path to the nperf binary')
    parser.add_argument('--nperf-repo', default=PATH_TO_NPERF_REPO, help='Path to the nperf repository')
    parser.add_argument('--yaml', help='Path to the YAML configuration file')  # Add YAML config file option
    parser.add_argument('--ssh-sender', default=None, help='SSH address of the sender machine')
    parser.add_argument('--ssh-receiver', default=None, help='SSH address of the receiver machine')

    args = parser.parse_args()

    global nperf_binary

    # If YAML config is provided, parse it and use its parameters
    if args.yaml:
        with open(args.yaml, 'r') as yaml_file:
            yaml_config = yaml.safe_load(yaml_file)
            # Use values from YAML config, potentially overriding other command-line arguments
            nperf_binary = yaml_config.get('nperf_bin', PATH_TO_NPERF_REPO + PATH_TO_NPERF_BIN)
            nperf_repo = yaml_config.get('nperf_repo', PATH_TO_NPERF_REPO)
            results_folder = yaml_config.get('results_folder', PATH_TO_RESULTS_FOLDER)
            csv_file_name = yaml_config.get('results_file', 'test_results.csv')
            config_file = yaml_config.get('config_file')
            ssh_sender = yaml_config.get('ssh_sender', None)
            ssh_receiver = yaml_config.get('ssh_receiver', None)

    else:
        nperf_binary = args.nperf_bin
        nperf_repo = args.nperf_repo 
        results_folder = args.results_folder
        config_file = args.config_file
        ssh_sender = args.ssh_sender
        ssh_receiver = args.ssh_receiver
        if config_file is None:
            logging.error("Config file must be supplied!")
            return
        csv_file_name = args.results_file

    nperf_binary = nperf_repo + PATH_TO_NPERF_BIN

    if csv_file_name == 'test_results.csv':
        csv_file_name = get_file_name(os.path.splitext(os.path.basename(config_file))[0])

    logging.debug('Parsed arguments: %s', args)
    logging.info('Using nPerf Repository: %s', nperf_repo)
    logging.info('Using nPerf Binary: %s', nperf_binary)
    logging.info('Reading config file: %s', config_file)
    logging.info('Results file name: %s', csv_file_name)
    logging.info('Results folder: %s', results_folder)

    test_configs = parse_config_file(config_file)
    logging.info('Read %d test configs', len(test_configs))

    # Check SSH connections if applicable
    if ssh_sender is not None:
        logging.debug("Testing SSH connection to sender...")
        if not test_ssh_connection(ssh_sender):
            logging.error("SSH connection to sender failed. Exiting.")
            exit(1)

    if ssh_receiver is not None:
        logging.debug("Testing SSH connection to receiver...")
        if not test_ssh_connection(ssh_receiver):
            logging.error("SSH connection to receiver failed. Exiting.")
            exit(1)

    if ssh_sender is None and ssh_receiver is not None or ssh_receiver is None and ssh_sender is not None:
        logging.error('SSH connection to sender AND receiver must be provided. Exiting.')
        exit(1)

    if ssh_sender is None and ssh_receiver is None:
        logging.info('Compiling binary in release mode. Assuming it is part of nperf repository.')
        subprocess.run(['cargo', 'build', '--release'], check=True, cwd=args.nperf_repo)

        # Create directory for test results
        os.makedirs(results_folder, exist_ok=True)
    elif ssh_sender == ssh_receiver:
        logging.info('Since ssh_sender and ssh_receiver are the same, assuming remote LOCALHOST.')
        setup_remote_repo_and_compile(ssh_sender, nperf_repo, NPERF_REPO)
    else:
        setup_remote_repo_and_compile(ssh_sender, nperf_repo, NPERF_REPO)
        setup_remote_repo_and_compile(ssh_receiver, nperf_repo, NPERF_REPO)


    for index, config in enumerate(test_configs):
        logging.info('-------------------')
        logging.info(f'Running test {config["test_name"]} ({index + 1}/{len(test_configs)}) from config {config_file}')
        logging.debug('Processing config: %s', config)
        logging.info('-------------------')

        test_name = config["test_name"]

        for run in config["runs"]:
            logging.info(f'Run {run["run_name"]} config: {run}')
            thread_timeout = run["sender"]["time"] + 15

            # FIXME: Currently interface is hardcoded to ens6f0np0
            if run["sender"]["ip"] == "127.0.0.1" or run["sender"]["ip"] == "0.0.0.0":
                logging.warning("Pacing is not possible on localhost/loopback.")
            elif run["sender"].get("bandwidth", 0) == 0:
                logging.info('Disabling pacing on hardcoded interface ens6f0np0')
                change_pacing(False, ssh_sender, "ens6f0np0")
            else:
                logging.info('Enabling pacing on hardcoded interface ens6f0np0')
                change_pacing(True, ssh_sender, "ens6f0np0")

            for i in range(run["repetitions"]):
                logging.info('Run repetition: %i/%i', i+1, run["repetitions"])
                failed_attempts = 0  # Initialize failed attempts counter
                for _ in range(0,MAX_FAILED_ATTEMPTS): # Retries, in case of an error
                    kill_receiver_process(run["receiver"]["port"], ssh_receiver)
                    logging.debug('Wait for some seconds so system under test can normalize...')
                    time.sleep(1)
                    logging.info('Starting test run %s', run['run_name'])
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        future_receiver = executor.submit(run_test_receiver, run, test_name, csv_file_name, results_folder, ssh_receiver)
                        time.sleep(1) # Wait for receiver to be ready
                        future_sender = executor.submit(run_test_sender, run, test_name, csv_file_name, results_folder, ssh_sender)

                        if future_receiver.result(timeout=thread_timeout) and future_sender.result(timeout=thread_timeout):
                            logging.info(f'Test run "{run["run_name"]}" finished successfully')
                            break
                        else:
                            logging.error(f'Test run {run["run_name"]} failed (test: {test_name}; config {config_file}), retrying')
                            kill_receiver_process(run["receiver"]["port"], ssh_receiver)
                            failed_attempts += 1

                if failed_attempts == MAX_FAILED_ATTEMPTS:
                    logging.error('Maximum number of failed attempts reached. Dont execute next repetition.')
                    break

    logging.info(f"Results stored in: {results_folder}receiver-{csv_file_name}")
    logging.info(f"Results stored in: {results_folder}sender-{csv_file_name}")


def setup_remote_repo_and_compile(ssh_target, path_to_repo, repo_url):
    logging.info(f"Setting up repository and compile code on {ssh_target}")
    repo_update_result = execute_command_on_host(ssh_target, f'cd {path_to_repo} && git checkout {NPERF_REPO_BRANCH} && git pull')
    
    if repo_update_result:
        logging.info(f"Repository at {path_to_repo} successfully updated.")
    else:
        logging.info(f"Repository does not exist or is not a Git repo at {path_to_repo}. Attempting to clone.")
        execute_command_on_host(ssh_target, f'mkdir -p {path_to_repo} && git clone {repo_url} {path_to_repo}')
        execute_command_on_host(ssh_target, f'cd {path_to_repo} && git checkout {NPERF_REPO_BRANCH}')

    execute_command_on_host(ssh_target, f'cd {path_to_repo} && source "$HOME/.cargo/env" && cargo build --release')


def change_pacing(enable: bool, host=None, interface=None) -> bool:
    pacing_state = "add" if enable else "del"
    command = f"tc qdisc {pacing_state} dev {interface} root fq"

    if host and interface:
        result = execute_command_on_host(host, command)
    else:
        result_code = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        result = result_code.returncode == 0

    if result:
        logging.info(f"Pacing {'enabled' if enable else 'disabled'}")
        return True
    else:
        logging.error(f"Failed to change pacing: {e}")
        return False


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


if __name__ == '__main__':
    logging.info('Starting benchmark script')
    main()
    logging.info('Finished benchmark script')
