import logging
import subprocess

RESULTS_FILE = "../results/configure.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=RESULTS_FILE, filemode='a')

def execute_command(command: str):
    with open(RESULTS_FILE, 'a') as results_file:
        subprocess.run(command, shell=True, stdout=results_file, stderr=results_file)
    logging.info('----------------------')

logging.info("Starting configure script")

logging.info("Install cargo ")
install_cargo = "curl https://sh.rustup.rs -sSf | sh -s -- -y"
execute_command(install_cargo)

# Turn off Hyperthreading
logging.info("Turning off Hyperthreading")
turn_off_HT = "echo off | tee /sys/devices/system/cpu/smt/control"
execute_command(turn_off_HT)


logging.info("Configuring interfaces")
# Interfaces
# Get information about passed interfaces
# Set correct MTU 1500
# Set correct IP address 
# Set up passed interfaces

logging.info("Finished configure script")
