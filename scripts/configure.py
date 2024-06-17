# Interfaces
# Get information about passed interfaces
# Set correct MTU 1500
# Set correct IP address 
# Set up passed interfaces
print("Configuring interfaces")

import logging
RESULTS_FILE = "../results/configure.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=RESULTS_FILE, filemode='a')

