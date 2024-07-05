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
#MAPPINGS = {
#    "special": "configs_mapping_special-old.json",
#    "syscalls": "configs_mapping_syscalls-old.json",
#    "uring": "configs_mapping_uring-old.json"
#}

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
        x_label = plot_config.get("x", "amount_threads") 
        x_bar_label = plot_config.get("x_label")
        y_label = plot_config.get("y", "data_rate_gbit")

        base_name = config_name.replace('.json', '-')
        csv_file = None
        for file in os.listdir(csv_folder):
            if base_name in file and file.endswith('.csv'):
                csv_file = file
                csv_file_path = os.path.join(csv_folder, csv_file)

                command = ["python3", "visualize/create_plot_from_csv.py", csv_file_path, title, x_label, y_label, graph_type, "--results-folder", results_folder]

                if x_bar_label is not None:
                    command.append("--x-label")
                    command.append(x_bar_label)

                if no_errors:
                    command.append("--no-errors")

                logging.debug(f"Running command: {command}")
                subprocess.run(command, check=True)
        if csv_file is None:
            logging.error(f"No CSV file found for {config_name} in {csv_folder}")
            result += f"- {config_name} : No CSV file found\n"
            continue 
    return result

def visualize(folder_name: str, results_folder: str, no_errors=False):
    csv_folder_receiver = os.path.join(folder_name, f"nperf-receiver")
    csv_folder_sender = os.path.join(folder_name, f"nperf-sender")
    result = "FAILED PLOTS\n"

    for key, filename in MAPPINGS.items():
        file_path = os.path.join(MAPPINGS_FOLDER_PATH, filename)
        results_folder_path = os.path.join(results_folder, key)

        try:
            os.makedirs(results_folder_path, exist_ok=True) 
            with open(file_path, 'r') as file:
                config_mapping = json.load(file)
                result += create_plots(results_folder_path, csv_folder_receiver, config_mapping["receiver"], no_errors=no_errors)
                result += create_plots(results_folder_path, csv_folder_sender, config_mapping["sender"], no_errors=no_errors)
                logging.info(f"Plots created for {key}")
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON from {filename}: {e}")

    if result != "FAILED PLOTS\n":
        logging.warning(result)


def unpack_tar(tar_path: str, folder_name: str, receiver_name: str, sender_name=None):
    # Untar the results tar in the current directory
    with tarfile.open(tar_path, "r") as tar:
        tar.extractall(folder_name)

    logging.info(f"Untar the file {receiver_name}-results.tar.gz inside {folder_name} into folder nperf-receiver")
    receiver_tar_file = os.path.join(folder_name, f"{receiver_name}-results.tar.gz")

    try:
        with tarfile.open(receiver_tar_file, "r") as tar:
            tar.extractall(folder_name)
        receiver_results_folder = os.path.join(folder_name, "nperf-receiver")
        # TODO: Change this to the variable FOLDER_NAME_IN_TAR
        os.rename(os.path.join(folder_name, "results"), receiver_results_folder)
    except tarfile.TarError as e:
        logging.error(f"Error extracting tar file: {e}")
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")


    if sender_name:
        logging.info(f"Untar the file {sender_name}-results.tar.gz inside {folder_name} into folder nperf-sender")
        sender_tar_file = os.path.join(folder_name, f"{sender_name}-results.tar.gz")

        try:
            with tarfile.open(sender_tar_file, "r") as tar:
                tar.extractall(folder_name)
            sender_results_folder = os.path.join(folder_name, "nperf-sender")
            # TODO: Change this to the variable FOLDER_NAME_IN_TAR
            os.rename(os.path.join(folder_name, "results"), sender_results_folder)
        except tarfile.TarError as e:
            logging.error(f"Error extracting tar file: {e}")
        except FileNotFoundError as e:
            logging.error(f"File not found: {e}")

def fix_folder_structure(folder_name: str):
    nperf_receiver_folder = os.path.join(folder_name, "nperf-receiver")
    nperf_sender_folder = os.path.join(folder_name, "nperf-sender")

    if not os.path.exists(nperf_sender_folder):
        os.makedirs(nperf_sender_folder)

    # Move all files starting with "sender-" from nperf-receiver to nperf-sender
    for file in os.listdir(nperf_receiver_folder):
        if file.startswith("sender-"):
            shutil.move(os.path.join(nperf_receiver_folder, file), nperf_sender_folder)

def main():
    logging.info('Starting main function')
    parser = argparse.ArgumentParser(description="Visualize the results of run.py")

    parser.add_argument("path_to_tar", type=str, help="The relative path to the tar file")
    parser.add_argument("receiver_name", type=str, help="The ssh name of the receiver")
    parser.add_argument("sender_name", nargs='?', type=str, help="The ssh name of the sender")
    parser.add_argument("--results-folder", type=str, default=RESULTS_DIR, help="The folder where the results are stored")
    parser.add_argument("--folder-name-in-tar", type=str, default=FOLDER_NAME_IN_TAR, help="The folder name in the tar file")
    parser.add_argument("--use-existing", action="store_true", help="Use existing temp folder data instead of extracting the tar file.")
    parser.add_argument("--unpack-only", action="store_true", help="Only unpack the tar file and exit")
    parser.add_argument('--no-errors', action="store_true", help='Dont display errors (standard deviation etc.) in the charts')

    args = parser.parse_args()

    logging.info(f"Path to tar file: {args.path_to_tar}")
    logging.info(f"Sender name: {args.sender_name}")
    logging.info(f"Receiver name: {args.receiver_name}")
    temp_folder = args.folder_name_in_tar

    # Create the results folder
    os.makedirs(args.results_folder, exist_ok=True)

    if os.path.exists(temp_folder) and not args.use_existing:
        logging.warning(f"Removing existing folder {temp_folder}")
        shutil.rmtree(temp_folder)

    if not args.use_existing:
        unpack_tar(args.path_to_tar, temp_folder, args.receiver_name, args.sender_name)

    if args.sender_name is None:
        fix_folder_structure(temp_folder)

    if not args.unpack_only:
        visualize(temp_folder, args.results_folder, args.no_errors)


if __name__ == '__main__':
    logging.info('Starting visualize script')
    main()
    logging.info('Script visualize finished')
