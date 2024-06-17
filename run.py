import argparse
import logging
import os
import shutil
import subprocess

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
        passed_tests = args.tests.split()
        tests = []
        for test in passed_tests:
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
    setup_hosts([args.server_hostname, args.client_hostname])
    logging.info('----------------------')
    execute_tests(tests, [args.server_hostname, args.client_hostname])
    logging.info('----------------------')
    get_results([args.server_hostname, args.client_hostname])
    logging.info('----------------------')


def execute_tests(tests: list, hosts: list) -> bool:
    logging.info('Executing tests')
    # Always call setup.py on both hosts
    # Always call sysinfo.py on both hosts

    # Iterate over the tests
    # Execute the scripts on the local host
    # The scripts will then execute the tests on the remote hosts
    return True


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

if __name__ == '__main__':
    logging.info('Starting script')
    main()
    logging.info('Script finished')
