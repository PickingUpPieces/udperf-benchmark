import argparse
import logging
import shutil
import tarfile
import os

RESULTS_DIR = "./graphs"
FOLDER_NAME_IN_TAR = "nperf-results-test" # Normally: "results"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_plots(results_folder: str, configs_mapping: dict[str, dict[str, str]]):
    logging.info(f"Create plots for the results in {results_folder}")
    os.makedirs(results_folder, exist_ok=True)
    for config_name, plot_config in configs_mapping.items():
        logging.info(f"Create plot for {config_name}")
        logging.debug(f"Plot config for {config_name}: {plot_config}")
        # TODO: Implement the visualization of the results
        

def main():
    logging.info('Starting main function')
    parser = argparse.ArgumentParser(description="Visualize the results of run.py")

    parser.add_argument("path_to_tar", type=str, help="The relative path to the tar file")
    parser.add_argument("client_name", type=str, help="The ssh name of the client")
    parser.add_argument("server_name", type=str, help="The ssh name of the server")
    parser.add_argument("--results-folder", type=str, default=RESULTS_DIR, help="The folder where the results are stored")
    parser.add_argument("--folder-name-in-tar", type=str, default=FOLDER_NAME_IN_TAR, help="The folder name in the tar file")
    args = parser.parse_args()

    logging.info(f"Path to tar file: {args.path_to_tar}")
    logging.info(f"Client name: {args.client_name}")
    logging.info(f"Server name: {args.server_name}")
    temp_folder = args.folder_name_in_tar

    # Create the results folder
    os.makedirs(args.results_folder, exist_ok=True)

    # Untar the results tar in the current directory
    with tarfile.open(args.path_to_tar, "r") as tar:
        tar.extractall()

    logging.info(f"Untar the file {args.client_name}-results.tar.gz inside temp_folder into folder nperf-client")
    client_tar_file = os.path.join(temp_folder, f"{args.client_name}-results.tar.gz")
    with tarfile.open(client_tar_file, "r") as tar:
        tar.extractall(temp_folder)
    client_results_folder = os.path.join(temp_folder, "nperf-client")
    # TODO: Change this to the variable FOLDER_NAME_IN_TAR
    os.rename(os.path.join(temp_folder, "results"), client_results_folder)

    logging.info(f"Untar the file {args.server_name}-results.tar.gz inside temp_folder into folder nperf-server")
    server_tar_file = os.path.join(temp_folder, f"{args.server_name}-results.tar.gz")
    with tarfile.open(server_tar_file, "r") as tar:
        tar.extractall(temp_folder)
    server_results_folder = os.path.join(temp_folder, "nperf-server")
    # TODO: Change this to the variable FOLDER_NAME_IN_TAR
    os.rename(os.path.join(temp_folder, "results"), server_results_folder)

    # Visualize the results
    # For every benchmark one graph is created
    # Bar graph: python3 visualize/create_plot_from_csv.py results/server-uring_client_single_thread-06-19-15:24.csv "uring client single thread" data_rate_gbit data_rate_gbit bar
    # Area graph:  python3 visualize/create_plot_from_csv.py results/interval-measurement.csv "interval-measurement" interval_id data_rate_gbit area
    # Heatmap: python3 create_plot_from_csv.py  "server-topup" amount_threads_client uring_sq_utilization heat --test_name 'default'
    CONFIGS_MAPPING_CLIENT = {
    }

    CONFIGS_MAPPING_SERVER = {
        "nperf_client-server_ratio.json": {
            "title": "client server ratio",
            "type": "area",
            "x": "amount_threads",
            "y": "data_rate_gbit",
        },
        "nperf_multiplex_port_comparison.json": {
            "title": "multiplex port comparison",
            "type": "area",
            "x": "amount_threads",
            "y": "data_rate_gbit"
        },
    }

    "special_client_same_bytes.json",
    "special_server_same_bytes.json",
    "special_server_uneven_gso.json",
    "syscalls_client_multi_thread.json",
    "syscalls_client_multi_thread_gsro.json",
    "syscalls_client_multi_thread_mmsgvec.json",
    "syscalls_client_single_thread.json",
    "syscalls_client_single_thread_gsro.json",
    "syscalls_client_single_thread_mmsgvec.json",
    "syscalls_server_multi_thread.json",
    "syscalls_server_multi_thread_gsro.json",
    "syscalls_server_multi_thread_mmsgvec.json",
    "syscalls_server_single_thread.json",
    "syscalls_server_single_thread_gsro.json",
    "syscalls_server_single_thread_mmsgvec.json",
    "uring_client_multi_thread.json",
    "uring_client_multi_thread_ring_size.json",
    "uring_client_multi_thread_ring_size_gsro.json",
    "uring_client_single_thread.json",
    "uring_client_single_thread_fill_modes.json",
    "uring_client_single_thread_gsro.json",
    "uring_client_single_thread_ring_size.json",
    "uring_client_single_thread_sq_poll.json",
    "uring_client_single_thread_task_work.json",
    "uring_client_single_thread_zerocopy.json",
    "uring_server_multi_thread.json",
    "uring_server_multi_thread_gsro.json",
    "uring_server_multi_thread_ring_size.json",
    "uring_server_multi_thread_ring_size_gsro.json",
    "uring_server_single_thread.json",
    "uring_server_single_thread_fill_modes.json",
    "uring_server_single_thread_gsro.json",
    "uring_server_single_thread_sq_poll.json",
    "uring_server_single_thread_task_work.json"

    # Remove the temporary folder
    shutil.rmtree(temp_folder)

if __name__ == '__main__':
    logging.info('Starting visualize script')
    main()
    logging.info('Script visualize finished')
