import argparse
import logging
import os
import shutil
import subprocess
import concurrent.futures 

TESTS = ['nperf', 'iperf2', 'iperf3', 'netperf']
NPERF_BENCHMARK_REPO = "https://github.com/PickingUpPieces/nperf-benchmark.git"
NPERF_DIRECTORY = "nperf-benchmark"
NPERF_RESULTS_DIR = "results"
LOG_FILE = "results/run.log"

# Set up logging to write into LOG_FILE
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=LOG_FILE, filemode='a')

def main():
    logging.info('Starting main function')

    # Create the parser
    parser = argparse.ArgumentParser(description="Run tests on server and client")

    # Add the arguments
    parser.add_argument("server_hostname", type=str, help="The hostname of the server")
    parser.add_argument("server_interfacename", type=str, help="The interface name of the server")
    parser.add_argument("client_hostname", type=str, help="The hostname of the client")
    parser.add_argument("client_interfacename", type=str, help="The interface name of the client")

    # Add optional arguments
    parser.add_argument("-t", "--tests", type=str, nargs='*', help="List of tests to run in a string with space separated values. Possible values: nperf, sysinfo, iperf2, iperf3, netperf")

    # Parse the arguments
    args = parser.parse_args()

    # Use the arguments
    logging.info(f"Server hostname: {args.server_hostname}")
    logging.info(f"Server interface name: {args.server_interfacename}")
    logging.info(f"Client hostname: {args.client_hostname}")
    logging.info(f"Client interface name: {args.client_interfacename}")

    if args.tests:
        tests = []
        for test in args.tests:
            if test not in TESTS:
                logging.warning(f"Invalid test: {test}")
            else:
                logging.info(f"Running test: {test}")
                # Add the test to the tests list
                tests.append(test)
    else:
        logging.info("All tests are run")
        tests = TESTS

    logging.info('----------------------')

    # Test SSH connection to server
    for host in [args.server_hostname, args.client_hostname]:
        if not test_ssh_connection(host):
            logging.error(f"SSH connection to {host} failed. Exiting.")
            return

    logging.info('----------------------')
    setup_hosts([args.server_hostname, args.client_hostname])
    logging.info('----------------------')
    execute_tests(tests, [args.server_hostname, args.client_hostname], [(args.server_hostname, args.server_interfacename), (args.client_hostname, args.client_interfacename)])
    logging.info('----------------------')
    get_results([args.server_hostname, args.client_hostname])
    logging.info('----------------------')


def execute_tests(tests: list, hosts: list[str], interfaces: list[tuple[str, str]]) -> bool:
    logging.info('Executing tests')
    logging.info(f'Configuring all hosts')
    execute_on_hosts_in_parallel(interfaces, execute_script_on_host, 'configure.py')
    logging.info(f'Getting system information from all hosts')
    execute_on_hosts_in_parallel(interfaces, execute_script_on_host, 'sysinfo.py')

    logging.info(f'Executing following tests: {tests}')

    interface_names = [interface[1] for interface in interfaces]
    logging.info(f'Interface names: {interface_names}')

    for test in tests:
        logging.info(f"Executing test: {test}")
        # Assuming each test has a corresponding script with the same name
        script_name = f"{test}.py"
        execute_script_locally(script_name, hosts, interface_names)
    return True

def execute_script_locally(script_name, hosts, interfaces: list[str]):
    logging.info(f"Executing {script_name} locally to trigger test on remote hosts")

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    try:
        with open(LOG_FILE, 'a') as log_file:
            subprocess.run(["python3", 'scripts/' + script_name] + hosts + interfaces, stdout=log_file, stderr=log_file, check=True, env=env_vars)
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to execute {script_name}: {e}")

def execute_script_on_host(host, interface, script_name):
    logging.info(f"Executing {script_name} on {host}")
    try:
        env_vars = os.environ.copy()
        # Ensure SSH_AUTH_SOCK is forwarded if available
        if 'SSH_AUTH_SOCK' in os.environ:
            env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

        # Command to execute setup.py on the remote host
        ssh_command = f"ssh {host} 'cd {NPERF_DIRECTORY}/scripts && python3 {script_name} {interface}'"
        result = subprocess.run(ssh_command, shell=True, capture_output=True, env=env_vars)
        
        if result.returncode == 0:
            logging.info(f"Script {script_name} completed successfully on {host}")
        else:
            logging.error(f"Script {script_name} failed on {host}: {result.stderr}")
    except Exception as e:
        logging.error(f"Error executing setup on {host}: {str(e)}")

def execute_on_hosts_in_parallel(hosts: list[tuple[str, str]], function_to_execute, script_name):
    logging.info(f'Executing {script_name} on all hosts in parallel')

    # Execute the script in parallel on all hosts
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        futures = [executor.submit(function_to_execute, host, interface, script_name) for (host, interface) in hosts]
        
        # Waiting for all futures to complete
        for future in futures:
            future.result()
            pass

def setup_hosts(hosts: list) -> bool:
    for host in hosts:
        logging.info(f"Setting up host: {host}")

        env_vars = os.environ.copy()
        # Ensure SSH_AUTH_SOCK is forwarded if available
        if 'SSH_AUTH_SOCK' in os.environ:
            env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

        # Open LOG_FILE in append mode
        with open(LOG_FILE, 'a') as log_file:
            # Modify the command to be executed over SSH
            ssh_command = f"ssh {host} 'rm -rf {NPERF_DIRECTORY} && git clone {NPERF_BENCHMARK_REPO}'"
            subprocess.run(ssh_command, shell=True, stdout=log_file, stderr=log_file, env=env_vars, text=True)

    logging.info('Hosts repo setup completed')
    return True

def get_results(hosts: list) -> bool:
    for host in hosts:
        logging.info(f'Getting results from host: {host}')

        env_vars = os.environ.copy()
        # Ensure SSH_AUTH_SOCK is forwarded if available
        if 'SSH_AUTH_SOCK' in os.environ:
            env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

        # Open LOG_FILE in append mode
        with open(LOG_FILE, 'a') as log_file:
            # Modify the command to be executed over SSH
            ssh_command = f"ssh {host} 'tar -czvf {NPERF_DIRECTORY}/{host}-results.tar.gz {NPERF_DIRECTORY}/{NPERF_RESULTS_DIR}'"
            subprocess.run(ssh_command, shell=True, stdout=log_file, stderr=log_file, env=env_vars, text=True)
            scp_command = f"scp {host}:{NPERF_DIRECTORY}/{host}-results.tar.gz {NPERF_RESULTS_DIR}/"
            subprocess.run(scp_command, shell=True, stdout=log_file, stderr=log_file, env=env_vars, text=True)

    logging.info('Results copied to results directory')
    logging.info('Zipping results')

    # Check for tar command 
    if shutil.which('tar'):
        logging.info('Tar command is available on this system.')
        tar_command = f'tar -czvf nperf-results.tar.gz -C {NPERF_RESULTS_DIR} .'

        with open(LOG_FILE, 'a') as log_file:
            subprocess.run(tar_command, shell=True, stdout=log_file, stderr=log_file)

        logging.info('Results zipped using tar.')
    # Check for zip command if tar not found
    elif shutil.which('zip'):
        logging.info('Zip command is available on this system.')
        zip_command = f'zip -r nperf-results.zip {NPERF_RESULTS_DIR}'

        with open(LOG_FILE, 'a') as log_file:
            subprocess.run(zip_command, shell=True, stdout=log_file, stderr=log_file)

        logging.info('Results zipped using zip.')
    else:
        logging.error('Neither tar nor zip command is available on this system.')

    return True

def test_ssh_connection(ssh_address):
    try:
        result = subprocess.run(['ssh', ssh_address, 'echo ok'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
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

if __name__ == '__main__':
    logging.info('Starting script')
    main()
    logging.info('Script finished')
