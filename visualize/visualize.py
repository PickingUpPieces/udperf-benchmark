import argparse
import json
import logging
import shutil
import subprocess
import tarfile
import os

RESULTS_DIR = "./graphs"
FOLDER_NAME_IN_TAR = "nperf-results-test" # Normally: "results"
LOG_FILE = "plots_checklist.md"
MAPPINGS_FOLDER_PATH = "visualize"

MAPPINGS = {
    "special": "configs_mapping_special.json",
    "syscalls": "configs_mapping_syscalls.json",
    "uring": "configs_mapping_uring.json"
}

logging.basicConfig(level=logging.INFO , format='%(asctime)s - %(levelname)s - %(message)s')

def create_plots(results_folder: str, csv_folder: str, configs_mapping: dict[str, dict[str, str]], no_errors=False) -> str:
    logging.info(f"Create plots for the results in {results_folder}")
    os.makedirs(results_folder, exist_ok=True)
    result = ""
    for config_name, plot_config in configs_mapping.items():
        logging.info(f"Create plot for {config_name}")
        logging.debug(f"Plot config for {config_name}: {plot_config}")

        graph_type = plot_config.get("type", "area")
        title = plot_config.get("title")
        x_label = plot_config.get("x_label", "amount_threads") 
        y_label = plot_config.get("y_label", "data_rate_gbit")

        base_name = config_name.replace('.json', '-')
        csv_file = None
        for file in os.listdir(csv_folder):
            if base_name in file and file.endswith('.csv'):
                csv_file = file
                break
        if csv_file is None:
            logging.error(f"No CSV file found for {config_name} in {csv_folder}")
            result += f"- {config_name} : No CSV file found\n"
            continue 
        csv_file_path = os.path.join(csv_folder, csv_file)

        command = ["python3", "visualize/create_plot_from_csv.py", csv_file_path, title, x_label, y_label, graph_type, "--results-folder", results_folder]

        if no_errors:
            command.append("--no-errors")

        logging.debug(f"Running command: {command}")
        subprocess.run(command, check=True)
    return result

def visualize(folder_name: str, results_folder: str, no_errors=False):
    csv_folder_server = os.path.join(folder_name, f"nperf-server")
    csv_folder_client = os.path.join(folder_name, f"nperf-client")
    result = "FAILED PLOTS\n"

    for key, filename in MAPPINGS.items():
        file_path = os.path.join(MAPPINGS_FOLDER_PATH, filename)
        results_folder_path = os.path.join(results_folder, key)

        try:
            os.makedirs(results_folder_path, exist_ok=True) 
            with open(file_path, 'r') as file:
                config_mapping = json.load(file)
                result += create_plots(results_folder_path, csv_folder_server, config_mapping["server"], no_errors=no_errors)
                result += create_plots(results_folder_path, csv_folder_client, config_mapping["client"], no_errors=no_errors)
                logging.info(f"Plots created for {key}")
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {filename}: {e}")

    if result != "FAILED PLOTS\n":
        logging.warning(result)


def unpack_tar(tar_path: str, folder_name: str, server_name: str, client_name=None):
    # Untar the results tar in the current directory
    with tarfile.open(tar_path, "r") as tar:
        tar.extractall(folder_name)

    logging.info(f"Untar the file {server_name}-results.tar.gz inside {folder_name} into folder nperf-server")
    server_tar_file = os.path.join(folder_name, f"{server_name}-results.tar.gz")

    try:
        with tarfile.open(server_tar_file, "r") as tar:
            tar.extractall(folder_name)
        server_results_folder = os.path.join(folder_name, "nperf-server")
        # TODO: Change this to the variable FOLDER_NAME_IN_TAR
        os.rename(os.path.join(folder_name, "results"), server_results_folder)
    except tarfile.TarError as e:
        logging.error(f"Error extracting tar file: {e}")
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")


    if client_name:
        logging.info(f"Untar the file {client_name}-results.tar.gz inside {folder_name} into folder nperf-client")
        client_tar_file = os.path.join(folder_name, f"{client_name}-results.tar.gz")

        try:
            with tarfile.open(client_tar_file, "r") as tar:
                tar.extractall(folder_name)
            client_results_folder = os.path.join(folder_name, "nperf-client")
            # TODO: Change this to the variable FOLDER_NAME_IN_TAR
            os.rename(os.path.join(folder_name, "results"), client_results_folder)
        except tarfile.TarError as e:
            logging.error(f"Error extracting tar file: {e}")
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")

def fix_folder_structure(folder_name: str):
    nperf_server_folder = os.path.join(folder_name, "nperf-server")
    nperf_client_folder = os.path.join(folder_name, "nperf-client")

    if not os.path.exists(nperf_client_folder):
        os.makedirs(nperf_client_folder)

    # Move all files starting with "client-" from nperf-server to nperf-client
    for file in os.listdir(nperf_server_folder):
        if file.startswith("client-"):
            shutil.move(os.path.join(nperf_server_folder, file), nperf_client_folder)

def main():
    logging.info('Starting main function')
    parser = argparse.ArgumentParser(description="Visualize the results of run.py")

    parser.add_argument("path_to_tar", type=str, help="The relative path to the tar file")
    parser.add_argument("server_name", type=str, help="The ssh name of the server")
    parser.add_argument("client_name", nargs='?', type=str, help="The ssh name of the client")
    parser.add_argument("--results-folder", type=str, default=RESULTS_DIR, help="The folder where the results are stored")
    parser.add_argument("--folder-name-in-tar", type=str, default=FOLDER_NAME_IN_TAR, help="The folder name in the tar file")
    parser.add_argument("--use-existing", action="store_true", help="Use existing temp folder data instead of extracting the tar file.")
    parser.add_argument("--unpack-only", action="store_true", help="Only unpack the tar file and exit")
    parser.add_argument('--no-errors', action="store_true", help='Dont display errors (standard deviation etc.) in the charts')

    args = parser.parse_args()

    logging.info(f"Path to tar file: {args.path_to_tar}")
    logging.info(f"Client name: {args.client_name}")
    logging.info(f"Server name: {args.server_name}")
    temp_folder = args.folder_name_in_tar

    # Create the results folder
    os.makedirs(args.results_folder, exist_ok=True)

    if os.path.exists(temp_folder) and not args.use_existing:
        logging.warning(f"Removing existing folder {temp_folder}")
        shutil.rmtree(temp_folder)

    if not args.use_existing:
        unpack_tar(args.path_to_tar, temp_folder, args.server_name, args.client_name)

    if args.client_name is None:
        fix_folder_structure(temp_folder)

    if not args.unpack_only:
        visualize(temp_folder, args.results_folder, args.no_errors)


if __name__ == '__main__':
    logging.info('Starting visualize script')
    main()
    logging.info('Script visualize finished')
