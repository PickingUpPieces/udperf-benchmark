import argparse
import logging
import os
import shutil
import subprocess
import datetime
import concurrent.futures 

TESTS = ['udperf', 'iperf2', 'iperf3']
udperf_BENCHMARK_REPO = "https://github.com/PickingUpPieces/udperf-benchmark.git"
udperf_BENCHMARK_REPO_BRANCH = 'develop'
udperf_BENCHMARK_DIRECTORY = "udperf-benchmark"
udperf_RESULTS_DIR = "results"
LOG_FILE = "results/run.log"
IP_RECEIVER = "192.168.128.1"
IP_SENDER = "192.168.128.2"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=LOG_FILE, filemode='a')

def main():
    logging.info('Starting main function')
    
    parser = argparse.ArgumentParser(description="Run tests on receiver and sender")

    parser.add_argument("receiver_hostname", type=str, help="The hostname of the receiver")
    parser.add_argument("receiver_interfacename", type=str, help="The interface name of the receiver")
    parser.add_argument("sender_hostname", type=str, help="The hostname of the sender")
    parser.add_argument("sender_interfacename", type=str, help="The interface name of the sender")
    parser.add_argument("-t", "--tests", type=str, nargs='*', help="List of tests to run in a string with space separated values. Possible values: udperf, sysinfo, iperf2, iperf3")

    args = parser.parse_args()

    logging.info(f"Receiver hostname: {args.receiver_hostname}")
    logging.info(f"Receiver interface name: {args.receiver_interfacename}")
    logging.info(f"Sender hostname: {args.sender_hostname}")
    logging.info(f"Sender interface name: {args.sender_interfacename}")

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
        tests = ["udperf"]
    
    # Create udperf_RESULTS_DIR if it doesn't exist
    if not os.path.exists(udperf_RESULTS_DIR):
        os.makedirs(udperf_RESULTS_DIR)

    logging.info('----------------------')

    # Test SSH connection to receiver
    for host in [args.receiver_hostname, args.sender_hostname]:
        if not test_ssh_connection(host):
            logging.error(f"SSH connection to {host} failed. Exiting.")
            return

    if args.receiver_hostname == args.sender_hostname:
        logging.warning("Receiver and sender hostnames are the same. Running local benchmark!")
        hosts = [args.receiver_hostname]
        ip_sender = "0.0.0.0"
        ip_receiver = "0.0.0.0"
    else:
        ip_sender = IP_SENDER
        ip_receiver = IP_RECEIVER
        hosts = [args.receiver_hostname, args.sender_hostname]

    logging.info('----------------------')
    setup_hosts(hosts)
    logging.info('----------------------')
    execute_tests(tests, [args.receiver_hostname, args.sender_hostname], [(args.receiver_hostname, args.receiver_interfacename, ip_receiver), (args.sender_hostname, args.sender_interfacename, ip_sender)])
    logging.info('----------------------')
    get_results(hosts)
    logging.info('----------------------')


def execute_tests(tests: list, hosts, interfaces) -> bool:
    logging.info('Executing tests')
    logging.info(f'Configuring all hosts')
    execute_on_hosts_in_parallel(interfaces, execute_script_on_host, 'configure.py')
    logging.info(f'Getting system information from all hosts')
    execute_on_hosts_in_parallel(interfaces, execute_script_on_host, 'sysinfo.py')

    logging.info(f'Executing following tests: {tests}')

    interface_names = [interface[1] for interface in interfaces]
    receiver_ip = interfaces[0][2]
    logging.info(f'Interface names: {interface_names}')

    for test in tests:
        logging.info(f"Executing test: {test}")
        # Assuming each test has a corresponding script with the same name
        script_name = f"{test}.py"
        execute_script_locally(script_name, hosts, interface_names, receiver_ip)
    return True

def execute_script_locally(script_name, hosts, interfaces, receiver_ip: str):
    logging.info(f"Executing {script_name} locally to trigger test on remote hosts")

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']
        
    with open(LOG_FILE, 'a+') as log_file:
        subprocess.run(["python3", 'scripts/' + script_name] + hosts + interfaces + [receiver_ip], stdout=log_file, stderr=log_file, env=env_vars)

def execute_script_on_host(host, interface, ip, script_name):
    logging.info(f"Executing {script_name} on {host}")
    try:
        result = execute_ssh_command(host, f'cd {udperf_BENCHMARK_DIRECTORY}/scripts && python3 {script_name} {interface} --ip {ip}', return_output=True)
        
        if result.returncode == 0:
            logging.info(f"Script {script_name} completed successfully on {host}")
        else:
            logging.error(f"Script {script_name} failed on {host}: {result.stderr}")
    except Exception as e:
        logging.error(f"Error executing setup on {host}: {str(e)}")

def execute_on_hosts_in_parallel(hosts, function_to_execute, script_name: str):
    logging.info(f'Executing {script_name} on all hosts in parallel')
    # Check for localhost mode
    if hosts[0][0] == hosts[1][0]:
        logging.info(f'Localhost mode detected ({hosts[0][0]}={hosts[1][0]}). Running on configure.py on single host.')
        hosts = [hosts[0]]

    # Execute the script in parallel on all hosts
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(hosts)) as executor:
        futures = [executor.submit(function_to_execute, host, interface, ip, script_name) for (host, interface, ip) in hosts]
        
        # Waiting for all futures to complete
        for future in futures:
            future.result()
            pass

def setup_hosts(hosts: list) -> bool:
    for host in hosts:
        logging.info(f"Setting up host: {host}")
        with open(LOG_FILE, 'a') as log_file:
            execute_ssh_command(host, f"git clone -b {udperf_BENCHMARK_REPO_BRANCH} {udperf_BENCHMARK_REPO}", log_file)
            execute_ssh_command(host, f"cd {udperf_BENCHMARK_DIRECTORY} && git pull", log_file)

    logging.info('Hosts repo setup completed')
    return True

def get_results(hosts) -> bool:
    for host in hosts:
        logging.info(f'Getting results from host: {host}')

        with open(LOG_FILE, 'a') as log_file:
            execute_ssh_command(host, f"cd {udperf_BENCHMARK_DIRECTORY} && tar -czvf {host}-results.tar.gz {udperf_RESULTS_DIR}", log_file)

            scp_command = f"scp -o LogLevel=quiet -o StrictHostKeyChecking=no {host}:{udperf_BENCHMARK_DIRECTORY}/{host}-results.tar.gz {udperf_RESULTS_DIR}/"
            subprocess.run(scp_command, shell=True, stdout=log_file, stderr=log_file)

            execute_ssh_command(host, f"rm -rf {udperf_BENCHMARK_DIRECTORY}/{udperf_RESULTS_DIR}/*", log_file)

    logging.info(f'Results copied to results directory {udperf_RESULTS_DIR}')
    logging.info('Zipping results')

    # Check for tar command 
    if shutil.which('tar'):
        logging.info('Tar command is available on this system.')
        tar_command = f'tar -czvf udperf-results.tar.gz -C {udperf_RESULTS_DIR} .'

        with open(LOG_FILE, 'a') as log_file:
            subprocess.run(tar_command, shell=True, stdout=log_file, stderr=log_file)

        logging.info('Results zipped using tar.')
    # Check for zip command if tar not found
    elif shutil.which('zip'):
        logging.info('Zip command is available on this system.')
        zip_command = f'zip -r udperf-results.zip {udperf_RESULTS_DIR}'

        with open(LOG_FILE, 'a') as log_file:
            subprocess.run(zip_command, shell=True, stdout=log_file, stderr=log_file)

        logging.info('Results zipped using zip.')
    else:
        logging.error('Neither tar nor zip command is available on this system.')

    return True

def test_ssh_connection(ssh_address: str) -> bool:
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

def execute_ssh_command(host: str, command: str, log_file=None, return_output=False) -> str:
    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']

    ssh_command = f"ssh -o LogLevel=quiet -o StrictHostKeyChecking=no {host} '{command}'"
    if log_file:
        subprocess.run(ssh_command, shell=True, stdout=log_file, stderr=log_file, env=env_vars)
    elif return_output:
        result = subprocess.run(ssh_command, capture_output=True, shell=True, text=True, env=env_vars)
        return result
    else:
        subprocess.run(ssh_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True, env=env_vars)

if __name__ == '__main__':
    logging.info('Starting script')
    print(f"Begin benchmark: {datetime.datetime.now()}")
    main()
    print(f"End benchmark: {datetime.datetime.now()}")
    logging.info('Script finished')
