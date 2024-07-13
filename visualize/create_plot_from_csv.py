import argparse
from collections import defaultdict
from math import floor
import os
import csv
import matplotlib.pyplot as plt
import logging
# Needed for heatmap
import pandas as pd
from scipy import stats
import seaborn as sns
import numpy as np
import ast

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
PATH_TO_RESULTS_FOLDER = 'results/'
BURN_IN_THRESHOLD = 10 # Percentage of data points (rows) to skip at the beginning of the test

MAPPINGS_COLUMNS = {
    "amount_threads": "Number of Threads",
    "packet_loss": "Packet Loss (%)",
    "data_rate_gbit": "Data Rate (Gbit/s)",
    "ring_size": "Ring Size",
}

def parse_results_file(results_file):
    results = []

    with open(results_file, 'r') as file:
        reader = csv.DictReader(file)
        current_test_name = ""
        test = []
        for row in reader:
            this_test_name = row.get('test_name')
            if this_test_name != current_test_name:
                logging.info("New test found %s (old test: %s), add the old test to the results list and start a new one", this_test_name, current_test_name)
                current_test_name = this_test_name
                if test != []:
                    results.append(test)
                test = []

            test.append(row)
        results.append(test)

    logging.info('Read %s test results', len(results))
    return results

def generate_area_chart(x: str, y: str, data, chart_title: str, results_file: str, results_folder: str, add_labels=False, rm_filename=False, no_errors=False, pdf=False, replace_plot=False):
    plt.figure()

    for test in data:
 
        # Organize data by x-value
        data_by_x = {}
        for row in test:
            try:
                x_val = float(row[x])
                y_val = float(row[y])
            except (ValueError, KeyError):
                continue 
            if x_val not in data_by_x:
                data_by_x[x_val] = []
            # This assumes that the last summeray row is at the end of the file
            if row['interval_id'] == '0' and data_by_x[x_val] is not None and len(data_by_x[x_val]) > 0:
                logging.debug("Leaving out final interval for %s=%s: %s", x, x_val, row)
                continue
            data_by_x[x_val].append(y_val)

        # Calculate mean and std for y-values of each x-value
        x_values = sorted(data_by_x.keys())

        # Remove burn-in values
        for run_name in data_by_x.keys():
            length_of_run = len(data_by_x.get(run_name))
            burn_in_rows_count = floor(length_of_run * BURN_IN_THRESHOLD / 100)
            data_by_x[run_name] = data_by_x[run_name][burn_in_rows_count:-2] # IMPORTANT: Remove last 2 rows, since one is the summary row and the other is the last interval which is buggy
            logging.debug("Leave out %s/%s rows for burn-in! New length %s", burn_in_rows_count, length_of_run, len(data_by_x.get(run_name)))

        # Calculate the burn_in_rows from the data_by_x array and directly remove the burn_in values
        y_means = [np.mean(data_by_x[x_val]) for x_val in x_values]
        y_stds = [np.std(data_by_x[x_val]) for x_val in x_values]

        try:
            label_name = test[0]['test_name']
        except KeyError:
            label_name = 'NOT FOUND'
            
        plt.plot(x_values, y_means, label=label_name, marker='o')

        if no_errors is False:
            # Plot error bars (filled area)
            plt.fill_between(x_values, np.subtract(y_means, y_stds), np.add(y_means, y_stds), alpha=0.2)

        if add_labels:
            for i, value in enumerate(y_means):
                plt.annotate(f"{value:.0f}", (x_values[i], value), textcoords="offset points", xytext=(0,10), ha='center')
 
    plt.xlabel(MAPPINGS_COLUMNS.get(x, x))
    plt.ylabel(MAPPINGS_COLUMNS.get(y, y))
    plt.ylim(bottom=0)  # Set the start of y-axis to 0
    if not rm_filename:
        plt.text(0.99, 0.5, "data: " + os.path.basename(results_file), ha='center', va='center', rotation=90, transform=plt.gcf().transFigure, fontsize=8)
    plt.title(chart_title)
    plt.legend()

    chart_title = chart_title.lower().replace(" - ", "_").replace(" ", "_").replace("/", "_").replace("-", "_")
    plot_file = results_folder + "/" + chart_title + '_area'
    save_plot(plot_file, pdf, replace_plot)

def generate_heatmap(x: str, y: str, test_name, data, chart_title, results_file, results_folder: str, rm_filename=False):
    logging.debug('Generating heatmap for %s', test_name)
    heatmap_data = []

    logging.debug('Data: %s', data)
    # data is a list of list, where each list is a test

    for test in data:
        for run in test:
            logging.debug('Test: %s', run)
            if run['test_name'] == test_name:
                y_values = ast.literal_eval(run[y])
                for key, val in y_values.items():
                    heatmap_data.append({
                        x: run[x],
                        'Utilization': key,
                        'Value': val
                    })

    # parse heatmap data
    logging.debug('Heatmap data: %s', heatmap_data)
    
    # Create a DataFrame from the heatmap_data list
    df = pd.DataFrame(heatmap_data)
    
    # Sort x and y keys
    df[x] = df[x].astype(int)
    df['Utilization'] = df['Utilization'].astype(int)
    df = df.sort_values(by=[x, 'Utilization'])

    logging.debug('DataFrame: %s', df)

    # Devide each value through the thread_amount to get the value per thread
    if x.startswith("amount_threads"):
        df['Value'] = df.apply(lambda row: row['Value'] / row[x], axis=1)

    logging.debug('DataFrame: %s', df)

    # use log, otherwise the values are too big
    df['Value'] = np.log(df['Value'])

    logging.debug('DataFrame: %s', df)

    # Pivot the DataFrame to get the heatmap data
    pivot_table = df.pivot(index='Utilization', columns=x, values='Value').fillna(0)
    logging.debug('Pivot Table: %s', pivot_table)

    # Generate heatmap
    plt.figure(figsize=(10, 8))
    sns.heatmap(pivot_table, cmap="YlGnBu", linewidths=.5, fmt='g')
    plt.xlabel(x)
    plt.ylabel(y)
    if not rm_filename:
        plt.text(0.99, 0.5, "data: " + os.path.basename(results_file), ha='center', va='center', rotation=90, transform=plt.gcf().transFigure, fontsize=8)
    plt.title(chart_title)

    chart_title = chart_title.lower().replace(" - ", "_").replace(" ", "_").replace("/", "_").replace("-", "_")
    plt.savefig(results_folder + "/" + chart_title + '_heatmap.png')
    logging.info('Saved plot to %s_heatmap.png', chart_title)
    plt.close()


def generate_bar_chart(y: str, data, chart_title: str, results_file, results_folder: str, rm_filename=False, no_errors=False, x_label=None, pdf=False, replace_plot=False):
    # Map every row in the data as a bar with the y value
    logging.debug("Generating bar chart for %s with data %s", y, data)

   # Group y_values by run_name
    grouped_data = defaultdict(list)
    for row in data:
        # This assumes that the last summary row is at the end of the file
        if row['interval_id'] == '0' and grouped_data[row['run_name']] is not None and len(grouped_data[row['run_name']]) > 0: 
            logging.debug("Leaving out final interval for x=%s", row[y])
            continue
        grouped_data[row['run_name']].append(float(row[y]))

    # Apply BURN_IN_THRESHOLD
    for run_name in list(grouped_data):
        burn_in_rows_count = floor(len(grouped_data[run_name]) * BURN_IN_THRESHOLD / 100)
        logging.debug("Leave out %s/%s rows for burn-in", burn_in_rows_count, len(grouped_data[run_name]))
        grouped_data[run_name] = grouped_data[run_name][burn_in_rows_count:-2]
    
    # Calculate mean and standard deviation for each group
    x_values = []
    mean_values = []
    std_dev_values = []
    for run_name, values in grouped_data.items():
        x_values.append(run_name)
        mean_values.append(np.mean(values))
        std_dev_values.append(np.std(values))

    if no_errors:
        plt.bar(x_values, mean_values)
    else:
        plt.bar(x_values, mean_values, yerr=std_dev_values, capsize=5, error_kw=dict(ecolor='darkred', lw=2, capsize=5, capthick=2))

    if x_label is not None:
        plt.xlabel(MAPPINGS_COLUMNS.get(x_label, x_label))
    plt.ylabel(MAPPINGS_COLUMNS.get(y, y))
    #plt.xticks(fontsize='x-small')  # rotation=20, ha="right",  Rotate labels for readability

    if not rm_filename:
        plt.text(0.99, 0.5, "data: " + os.path.basename(results_file), ha='center', va='center', rotation=90, transform=plt.gcf().transFigure, fontsize=8)
    plt.title(chart_title)

    chart_title = chart_title.lower().replace(" - ", "_").replace(" ", "_").replace("/", "_").replace("-", "_")
    plot_file = results_folder + "/" + chart_title + '_bar'
    save_plot(plot_file, pdf, replace_plot)

    
def save_plot(plot_file, pdf, replace_plot=False):
    if replace_plot is False:
        counter = 1
        plot_file_search = plot_file
        if pdf:
            plot_file_search += '.pdf'
        else:
            plot_file_search += '.png'
        logging.info('Saving plot to %s', plot_file)
        plot_file_new = plot_file

        while os.path.exists(plot_file_search):
            plot_file_new = f'{plot_file}-{counter}'
            counter += 1
            plot_file_search = plot_file_new
            if pdf:
                plot_file_search += '.pdf'
            else:
                plot_file_search += '.png'
    else:
        plot_file_new = plot_file
        
    if pdf:
        plot_file_new += '.pdf'
    else:
        plot_file_new += '.png'
    plt.savefig(plot_file_new, bbox_inches='tight', pad_inches=0.1)
    logging.info('Saved plot to %s', plot_file_new)
    plt.close()
    

def get_median_result(results):
    if len(results) == 1:
        return results[0]

    array = []
    for (receiver_result, sender_result) in results:
        array.append(receiver_result["data_rate_gbit"])

    logging.debug("Array of results: %s", array)

    # Calculate z-scores for each result in the array https://en.wikipedia.org/wiki/Standard_score
    zscore = (stats.zscore(array))
    logging.debug("Z-scores: %s", zscore)

    # Map each z-score in the array which is greater than 1.4/-1.4 to None
    array = [array[i] if zscore[i] < 1.4 and zscore[i] > -1.4 else None for i in range(len(array))]
    filtered_arr = [x for x in array if x is not None]
    logging.debug("Array with outliers removed: %s", filtered_arr)

    # Get the index of the median value in the original array
    median_index = find_closest_to_median_index(filtered_arr)
    logging.debug("Median index: %s", median_index)

    # Find the index of the median value in the original array
    median_index = array.index(filtered_arr[median_index])

    # Return median result
    logging.debug("Returning median result: %s", results[median_index])
    return results[median_index]

def find_closest_to_median_index(arr):
    # Check if array is empty; Otherwise argmin fails
    if not arr:
        return None
    # Calculate the median and find the index of the closest value
    closest_index = np.argmin(np.abs(np.array(arr) - np.median(arr)))
    return closest_index
    
def main():
    logging.debug('Starting main function')

    parser = argparse.ArgumentParser(description='Plot generation for nperf benchmarks.')
    parser.add_argument('results_file', help='Path to the CSV file to get the results.')
    parser.add_argument('--results-folder', default=PATH_TO_RESULTS_FOLDER, help='Folder to save the generated plots')
    parser.add_argument('chart_name', default="Benchmark", help='Name of the generated chart')
    parser.add_argument('x_axis_param', default="run_name", help='Name of the x-axis parameter')
    parser.add_argument('y_axis_param', help='Name of the y-axis parameter')
    parser.add_argument('--test_name', help='Name of the specific test to generate the heatmap for')
    parser.add_argument('type', default="area", help='Type of graph to generate (area, bar, heat)')
    parser.add_argument('-l', action="store_true", help='Add labels to data points')
    parser.add_argument('--rm-filename', action="store_true", help='Add the results file name to the graph')
    parser.add_argument('--no-errors', action="store_true", help='Dont display errors (standard deviation etc.) in the charts')
    parser.add_argument('--x-label', default=None, help='Label for the x-axis in the bar chart')
    parser.add_argument('--pdf', action="store_true", help='Save the plots as pdf')
    parser.add_argument('--replace', action="store_true", help='Replace the existing plot file')
    args = parser.parse_args()

    logging.info('Reading results file: %s', args.results_file)
    results = parse_results_file(args.results_file)
    logging.debug('Results: %s', results)

    if args.type == 'area':
        generate_area_chart(args.x_axis_param, args.y_axis_param, results, args.chart_name, args.results_file, args.results_folder, args.l, args.rm_filename, args.no_errors, args.pdf, args.replace)
    elif args.type == 'bar':
        for test in results:
            # If no chart name supplied, take the test name
            if args.chart_name == "Benchmark":
                args.chart_name = test[0]["test_name"] 
            generate_bar_chart(args.y_axis_param, test, args.chart_name, args.results_file, args.results_folder, args.rm_filename, args.no_errors, args.x_label, args.pdf, args.replace)
    elif args.type == 'heat':
        generate_heatmap(args.x_axis_param, args.y_axis_param, args.test_name, results, args.chart_name, args.results_file, args.results_folder, args.rm_filename)

if __name__ == '__main__':
    logging.info('Starting script')
    main()
    logging.info('Script finished')
