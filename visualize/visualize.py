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

logging.basicConfig(level=logging.INFO , format='%(asctime)s - %(levelname)s - %(message)s')

def create_plots(results_folder: str, csv_folder: str, configs_mapping: dict[str, dict[str, str]]):
    logging.info(f"Create plots for the results in {results_folder}")
    os.makedirs(results_folder, exist_ok=True)
    for config_name, plot_config in configs_mapping.items():
        logging.info(f"Create plot for {config_name}")
        logging.debug(f"Plot config for {config_name}: {plot_config}")

        graph_type = plot_config.get("graph_type", "area")
        title = plot_config.get("title")
        x_label = plot_config.get("x_label", "amount_threads") 
        y_label = plot_config.get("y_label", "data_rate_gbit")

        base_name = config_name.replace('.json', '')
        csv_file = None
        for file in os.listdir(csv_folder):
            if base_name in file and file.endswith('.csv'):
                csv_file = file
                break
        if csv_file is None:
            logging.error(f"No CSV file found for {config_name} in {csv_folder}")
            # TODO: Add a check list entry in the markdown file
            continue 
        csv_file_path = os.path.join(csv_folder, csv_file)

        command = ["python3", "visualize/create_plot_from_csv.py", csv_file_path, title, x_label, y_label, graph_type, "--results-folder", results_folder]
        logging.debug(f"Running command: {command}")
        subprocess.run(command, check=True)


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
        tar.extractall(temp_folder)

    logging.info(f"Untar the file {args.client_name}-results.tar.gz inside {temp_folder} into folder nperf-client")
    client_tar_file = os.path.join(temp_folder, f"{args.client_name}-results.tar.gz")
    try:
        with tarfile.open(client_tar_file, "r") as tar:
            tar.extractall(temp_folder)
        client_results_folder = os.path.join(temp_folder, "nperf-client")
        # TODO: Change this to the variable FOLDER_NAME_IN_TAR
        os.rename(os.path.join(temp_folder, "results"), client_results_folder)
    except tarfile.TarError as e:
        logging.error(f"Error extracting tar file: {e}")
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")

    logging.info(f"Untar the file {args.server_name}-results.tar.gz inside {temp_folder} into folder nperf-server")
    server_tar_file = os.path.join(temp_folder, f"{args.server_name}-results.tar.gz")
    try:
        with tarfile.open(server_tar_file, "r") as tar:
            tar.extractall(temp_folder)
        server_results_folder = os.path.join(temp_folder, "nperf-server")
        # TODO: Change this to the variable FOLDER_NAME_IN_TAR
        os.rename(os.path.join(temp_folder, "results"), server_results_folder)
    except tarfile.TarError as e:
        logging.error(f"Error extracting tar file: {e}")
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        
    mappings = {
        "special": "configs_mapping_special.json",
        "syscalls": "configs_mapping_syscalls.json",
        "uring": "configs_mapping_uring.json"
    }

    csv_folder_server = os.path.join(temp_folder, f"nperf-server")
    csv_folder_client = os.path.join(temp_folder, f"nperf-client")

    for key, filename in mappings.items():
        file_path = os.path.join(MAPPINGS_FOLDER_PATH, filename)
        results_folder_path = os.path.join(args.results_folder, key)

        try:
            os.makedirs(results_folder_path, exist_ok=True) 
            with open(file_path, 'r') as file:
                config_mapping = json.load(file)
                create_plots(results_folder_path, csv_folder_server, config_mapping["server"])
                create_plots(results_folder_path, csv_folder_client, config_mapping["client"])
                logging.info(f"Plots created for {key}")
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {filename}: {e}")

    # Remove the temporary folder
    shutil.rmtree(temp_folder)

if __name__ == '__main__':
    logging.info('Starting visualize script')
    main()
    logging.info('Script visualize finished')
