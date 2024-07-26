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
# Adjust the logging level for matplotlib to suppress debug messages
matplotlib_logger = logging.getLogger('matplotlib')
matplotlib_logger.setLevel(logging.WARNING)

PATH_TO_RESULTS_FOLDER = 'results'
BURN_IN_THRESHOLD = 25 # Percentage of data points (rows) to skip at the beginning of the test

MAPPINGS_COLUMNS = {
    "amount_threads": "Number of Threads",
    "packet_loss": "Packet Loss (%)",
    "data_rate_gbit": "Data Rate (Gibit/s)",
    "ring_size": "Ring Size",
}

def pre_process_data(results_file: str) -> pd.DataFrame:
    # A run is identified by same test_name, run_name and repetition_id
    # If there are multiple rows/values in a single run, we assume they are interval measurements. 
    # Therefore they can be ordered by column interval_id
    df = pd.read_csv(results_file)

    # Backwards compatibility to old result files: Check if 'repetition_id' column exists, if not add it with default value 1
    if 'repetition_id' not in df.columns:
        df['repetition_id'] = 1
     
    grouped = df.groupby(['test_name', 'run_name', 'repetition_id'])
    processed_groups = []
    
    for _, group in grouped:
        group = group.sort_values(by='interval_id')

        # If more values in the group than 1, we assume they are interval measurements
        # Remove first the rows, before we remove the burn-in threshold
        if len(group) > 1:
            # Remove rows where interval_id is 0 -> Summary row of measurement
            group = group[group['interval_id'] != 0]
            # Remove the row with the maximum interval_id -> This is the last interval measurement and is currently buggy
            max_interval_id = group['interval_id'].max()
            group = group[group['interval_id'] != max_interval_id]
        
        # Calculate the number of burn-in rows to leave out
        burn_in_rows_count = floor(len(group) * BURN_IN_THRESHOLD / 100)
        
        if burn_in_rows_count > 0:
            group = group.iloc[burn_in_rows_count:]
        
        processed_groups.append(group)
    
    processed_df = pd.concat(processed_groups)

    # Ensure run_name is always a string
    processed_df['run_name'] = processed_df['run_name'].astype(str)

    logging.debug('Processed data: %s', processed_df)
    return processed_df


def get_names_ordered(results_file: str, name: str) -> np.ndarray:
    data = pd.read_csv(results_file)
    # Get the unique names in the order they appear in the csv file -> This order should be the order in the plot
    return data[name].unique()


def generate_area_chart(x: str, y: str, data: pd.DataFrame, chart_title: str, results_file: str, results_folder: str, add_labels=False, rm_filename=False, no_errors=False, pdf=False, replace_plot=False, plot_per_repetition=False):
    plt.figure()
 
    # Ensure data is ordered but iterate in the same order as the test names appear in the results file
    grouped = data.groupby('test_name')
    test_names_ordered = get_names_ordered(results_file, 'test_name')

    for test_name in test_names_ordered.tolist():
        group = grouped.get_group(test_name)
        grouped_by_x = group.groupby(x)
        logging.info('Grouped by %s with number of tests %s', x, len(grouped_by_x))

        # Calculate mean and standard deviation 
        mean_y = grouped_by_x[y].mean()
        std_error_y = grouped_by_x[y].std()

        # Combine the results into a DataFrame
        data_by_x = pd.DataFrame({
            x: mean_y.index,
            'mean_y': mean_y.values,
            'std_error_y': std_error_y.values
        }).reset_index(drop=True)
        
        plt.plot(data_by_x[x], data_by_x['mean_y'], label=test_name, marker='o')
        
        if not no_errors:
            plt.fill_between(data_by_x[x], 
                             data_by_x['mean_y'] - data_by_x['std_error_y'], 
                             data_by_x['mean_y'] + data_by_x['std_error_y'], 
                             alpha=0.2)
 
 
    plt.xlabel(MAPPINGS_COLUMNS.get(x, x))
    plt.ylabel(MAPPINGS_COLUMNS.get(y, y))
    plt.ylim(bottom=0)  # Set the start of y-axis to 0
    if not rm_filename:
        plt.text(0.99, 0.5, 'data: ' + os.path.basename(results_file), ha='center', va='center', rotation=90, transform=plt.gcf().transFigure, fontsize=8)
    plt.title(chart_title)
    plt.legend()

    chart_title = chart_title.lower().replace(' - ', '_').replace(' ', '_').replace('/', '_').replace('-', '_')
    plot_file = results_folder + '/' + chart_title + '_area'
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
    if x.startswith('amount_threads'):
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
    sns.heatmap(pivot_table, cmap='YlGnBu', linewidths=.5, fmt='g')
    plt.xlabel(x)
    plt.ylabel(y)
    if not rm_filename:
        plt.text(0.99, 0.5, 'data: ' + os.path.basename(results_file), ha='center', va='center', rotation=90, transform=plt.gcf().transFigure, fontsize=8)
    plt.title(chart_title)

    chart_title = chart_title.lower().replace(' - ', '_').replace(' ', '_').replace('/', '_').replace('-', '_')
    plt.savefig(results_folder + '/' + chart_title + '_heatmap.png')
    logging.info('Saved plot to %s_heatmap.png', chart_title)
    plt.close()


# test_data: List of tests of repetitions: List[List[Dict]]
def generate_bar_chart(y: str, data: pd.DataFrame, chart_title: str, results_file, results_folder: str, rm_filename=False, no_errors=False, x_label=None, pdf=False, replace_plot=False, plot_per_repetition=False):
    # In the case of the bar chart, we expect run_name is the unique value differentiating the runs 
    # We assume that test_name is the same for all runs
    data['run_name'] = pd.Categorical(data['run_name'], categories=get_names_ordered(results_file, 'run_name'), ordered=True)

    grouped = data.groupby('run_name')[y]

    mean_std = grouped.agg(['mean', 'std'])
    grouped_data = mean_std.reset_index()

    # Replacing spaces in x-axis labels for better readability
    plot_x_values = grouped_data['run_name'].str.replace(' ', '\n', 1) 

    # Calculate mean and standard dev for each run
    means = grouped_data['mean']
    std_devs = grouped_data['std']

    if no_errors:
        plt.bar(plot_x_values, means)
    else:
        plt.bar(plot_x_values, means, yerr=std_devs, capsize=5, error_kw=dict(ecolor='darkred', lw=2, capsize=5, capthick=2))

    if x_label is not None:
        plt.xlabel(MAPPINGS_COLUMNS.get(x_label, x_label))
    plt.ylabel(MAPPINGS_COLUMNS.get(y, y))

    if len(plot_x_values) > 4:
        logging.info('Rotating x-axis labels')
        plt.xticks(fontsize='small', rotation=25)

    if not rm_filename:
        plt.text(0.99, 0.5, 'data: ' + os.path.basename(results_file), ha='center', va='center', rotation=90, transform=plt.gcf().transFigure, fontsize=8)
    plt.title(chart_title)

    chart_title = chart_title.lower().replace(' - ', '_').replace(' ', '_').replace('/', '_').replace('-', '_')
    plot_file = results_folder + '/' + chart_title + '_bar'
    save_plot(plot_file, pdf, replace_plot)

    
def save_plot(plot_file, pdf, replace_plot=False):
    if replace_plot is False:
        counter = 1
        plot_file_search = plot_file
        if pdf:
            plot_file_search += '.pdf'
        else:
            plot_file_search += '.png'
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
    

def main():
    logging.debug('Starting main function')

    parser = argparse.ArgumentParser(description='Plot generation for nperf benchmarks.')
    parser.add_argument('results_file', default='nperf-output.csv', help='Path to the CSV file to get the results.')
    parser.add_argument('--results-folder', default=PATH_TO_RESULTS_FOLDER, help='Folder to save the generated plots')
    parser.add_argument('chart_name', default='Benchmark', help='Name of the generated chart')
    parser.add_argument('x_axis_param', default='run_name', help='Name of the x-axis parameter')
    parser.add_argument('y_axis_param', default='data_rate_gbit', help='Name of the y-axis parameter')
    parser.add_argument('--test_name', help='Name of the specific test to generate the heatmap for')
    parser.add_argument('type', default='area', help='Type of graph to generate (area, bar, heat)')
    parser.add_argument('-l', action='store_true', help='Add labels to data points')
    parser.add_argument('--rm-filename', action='store_true', help='Add the results file name to the graph')
    parser.add_argument('--no-errors', action='store_true', help='Dont display errors (standard deviation etc.) in the charts')
    parser.add_argument('--x-label', default=None, help='Label for the x-axis in the bar chart')
    parser.add_argument('--pdf', action='store_true', help='Save the plots as pdf')
    parser.add_argument('--replace', action='store_true', help='Replace the existing plot file')

    args = parser.parse_args()

    logging.info('Reading results data file: %s', args.results_file)
    data_frame = pre_process_data(args.results_file)

    if args.type == 'area':
        generate_area_chart(args.x_axis_param, args.y_axis_param, data_frame, args.chart_name, args.results_file, args.results_folder, args.l, args.rm_filename, args.no_errors, args.pdf, args.replace)
    elif args.type == 'bar':
        if args.chart_name == 'Benchmark':
            args.chart_name = data_frame['test_name'].iloc[0]
        generate_bar_chart(args.y_axis_param, data_frame, args.chart_name, args.results_file, args.results_folder, args.rm_filename, args.no_errors, args.x_label, args.pdf, args.replace)
    elif args.type == 'heat':
        pass
        # Needs to be moved to using pandas
        #generate_heatmap(args.x_axis_param, args.y_axis_param, args.test_name, results, args.chart_name, args.results_file, args.results_folder, args.rm_filename)

if __name__ == '__main__':
    logging.info('Starting script')
    main()
    logging.info('Script finished')
