
import argparse
import logging
import os
import subprocess

BENCHMARK_CONFIGS = [
    "benchmark_test_config.json"
#    "send_methods_vs_uring_both.json",
#    "sendmmsg_mmsg-vec_with_threads_detailed.json"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info('Starting main function')

    parser = argparse.ArgumentParser(description="Wrapper script for benchmark.py to benchmark nperf")

    parser.add_argument("server_hostname", type=str, help="The hostname of the server")
    parser.add_argument("client_hostname", type=str, help="The hostname of the client")

    # Parse the arguments
    args = parser.parse_args()

    logging.info(f"Server hostname: {args.server_hostname}")
    logging.info(f"Client hostname: {args.client_hostname}")
    path_to_nperf_repo = "./nperf"

    env_vars = os.environ.copy()
    # Ensure SSH_AUTH_SOCK is forwarded if available
    if 'SSH_AUTH_SOCK' in os.environ:
        env_vars['SSH_AUTH_SOCK'] = os.environ['SSH_AUTH_SOCK']


    for config in BENCHMARK_CONFIGS:
        logging.info(f"Running nperf with config: {config}")
        parameters = ["configs/" + config, '--nperf-repo', path_to_nperf_repo, '--results-folder', './nperf-benchmark/results/', '--ssh-client', args.client_hostname, '--ssh-server', args.server_hostname]
        try:
            subprocess.run(["python3", 'scripts/benchmark.py'] + parameters, check=True, env=env_vars)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to execute {config}: {e}")

if __name__ == '__main__':
    logging.info('Starting nperf script')
    main()
    logging.info('Script nperf finished')
