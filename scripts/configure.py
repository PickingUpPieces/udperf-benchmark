import logging
import subprocess

RESULTS_FILE = "../results/configure.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=RESULTS_FILE, filemode='a')

logging.info("Starting configure script")

# Turn off Hyperthreading
logging.info("Turning off Hyperthreading")
turn_off_HT = "echo off | sudo tee /sys/devices/system/cpu/smt/control"
with open(RESULTS_FILE, "a") as result_file:
    subprocess.run(turn_off_HT, shell=True, stdout=result_file, stderr=result_file)


logging.info("Configuring interfaces")
# Interfaces
# Get information about passed interfaces
# Set correct MTU 1500
# Set correct IP address 
# Set up passed interfaces

logging.info("Finished configure script")
