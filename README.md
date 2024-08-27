# Benchmarking Framework for nPerf
This project is a benchmarking framework for nPerf, a network performance testing tool. The framework is designed to automate the process of setting up the systems, running nPerf tests and collecting the results. 
It also supports performing limited benchmarks with iperf2 and iperf3.
There are a lot of hardcoded features in this framework, which will potentially be removed in the future.


## Benchmark scripts
In general all scripts can be run standalone and have a `--help` option to show the needed arguments and options.

The `run.py` script is the main script orchestrating the benchmarking process. 
It is designed to be run on a central node, which has SSH access to the nodes that are to be benchmarked. 
The script will copy the necessary files to the nodes, run the benchmarking scripts on the nodes and collect the results.

Two scripts are used to collect system information and configure the host:
- `sysinfo.py`: This script collects system information on the node it is run on. 
- `configure.py`: This script configures the host on which it is run. Currently, it performs quite specific tasks for our used benchmark setups and configurations e.g. sets IP addresses on interfaces, installs dependencies, disables hyperthreading etc. This script can be extended or modified to fit the needs of the user.


### nPerf
Since we want to evaluate multiple configurations of nPerf, we have divided the benchmarking into two scripts:
- `nperf.py`: Manages the benchmarking of multiple configurations of nPerf.
- `benchmark.py`: Executes a single declarative benchmark configuration with nPerf.

In the `nperf.py` script, all configuration files which should be benchmarked are stored in the `BENCHMARK_CONFIGS` dictionary.
The script replaces the ip addresses in the configuration files with the ip addresses of the nodes.
Additionally, it sets a different MTU on the network interfaces of the nodes if the configuration file name includes the string `jumboframes`.
Then it calls the `benchmark.py` script on the same server or on different nodes to run the actual benchmark.

The `benchmark.py` script is the script which runs the nPerf benchmark on the nodes.
It clones and builds a specific version of the nPerf repository, which can be specified in the script.
Then it parses the configuration file and starts the nPerf receiver and sender with the given configuration.
If no sender configuration is given (`sender: {}`), the script uses a default configuration specified in the `DEFAULT_CONFIG_SENDER` dictionary.

```python
DEFAULT_CONFIG_SENDER = {
#   "parallel": {amount of threads which the receiver is using}, 
    "io-model": "select",
    "exchange-function": "msg",
    "with-gsro": True,
    "bandwidth": 100000
}
```

When the `bandwidth` parameter is specified, the script sets qdisc on the network interfaces.



### iperf2 and iperf3
For automating the benchmarks of iperf2 and iperf3, the `iperf2.py` and `iperf3.py` scripts are used.
These scripts are quite similar in their structure. 
They clone and build a specific version of the iperf2 or iperf3 repository, which can be specified in both scripts.
The benchmark configs are stored in the `BENCHMARK_CONFIGS` dictionary, which can be extended easily. 
The scripts can be executed on the host directly, measuring against localhost or on two hosts measuring between them.
The output is stored in a CSV file, which can be used for further processing by the visualization scripts.


## Visualization
After automated benchmarking, the collected data can be visualized in an automated way too.
Similar to the benchmarking scripts, there exists a main script `visualize.py` which creates plots for the different configuration files.
As input, it either needs the tar file created by the `run.py` script or an already extracted folder with the benchmark results.
The script uses multiple mapping JSON files to create the plots for the result files e.g. `configs_mapping_syscalls.json` and `configs_mapping_special.json`.
An example mapping in these files is:
```json
    "syscalls_sender_multi_thread.json": {
      "title": "Sender - Multi Thread",
      "type": "area",
      "x": "amount_threads",
      "y": "data_rate_gbit"
    }
```
Since the result files are named as their configuration files, the mapping needs the configuration file name as key.
The `title` is the title of the plot, `type` is the type of the plot and `x` and `y` are the columns of the CSV file that should be used for the x and y axis.
To create the plots, the script uses the `create_plot_from_csv.py` script, which is a general script to create plots from CSV files.


### Scripts for creating plots
There are several scripts for different types of data.
The `create_plot_from_csv.py` creates an area or bar plot from a given CSV file.
It supports multiple configurations which can be seen with the `--help` option.
By default the script leaves out the first percentage of data specified in `BURN_IN_THRESHOLD`.

The scripts `create_cache_plot.py` and `create_mem_plot.py` create plots from the output of the [pcm-memory](https://github.com/intel/pcm) tool.
The command which should be used to create a csv file is `sudo ./pcm-memory 0.1 -silent -nc -csv=test.log`.
- `create_mem_plot.py` creates a plot for the memory usage of the system.
- `create_cache_plot.py` creates a plot for the L2 and L3 cache hits or misses of the system.