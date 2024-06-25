import argparse
import logging
import shutil
import tarfile
import os

RESULTS_DIR = "./graphs"
FOLDER_NAME_IN_TAR = "nperf-results-test"

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

    os.makedirs(args.results_folder, exist_ok=True)
    with tarfile.open(args.path_to_tar, "r") as tar:
        tar.extractall()

    # Untar the file {args.client_name}-results.tar.gz inside temp_folder into client-results
    client_results_folder = os.path.join(temp_folder, "client-results")
    os.makedirs(client_results_folder, exist_ok=True)
    client_tar_file = os.path.join(temp_folder, f"{args.client_name}-results.tar.gz")
    with tarfile.open(client_tar_file, "r") as tar:
        tar.extractall(client_results_folder)

    # Untar the file {args.server_name}-results.tar.gz inside temp_folder into server-results
    server_results_folder = os.path.join(temp_folder, "server-results")
    os.makedirs(server_results_folder, exist_ok=True)
    server_tar_file = os.path.join(temp_folder, f"{args.server_name}-results.tar.gz")
    with tarfile.open(server_tar_file, "r") as tar:
        tar.extractall(server_results_folder)


    # Visualize the results

    # Remove the temporary folder
    shutil.rmtree(temp_folder)

if __name__ == '__main__':
    logging.info('Starting sysinfo script')
    main()
    logging.info('Script sysinfo finished')
