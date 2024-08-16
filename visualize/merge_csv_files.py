import pandas as pd
import sys

def merge_csv_files(master_file, csv_files):
    master_df = pd.read_csv(master_file)
    
    # Create a list to hold all dataframes including the master_df
    dataframes = [master_df]
    
    for file_path in csv_files:
        df = pd.read_csv(file_path)
        
        # Check for run_name in df and use amount_threads if necessary
        if 'run_name' not in df.columns and 'amount_threads' in df.columns:
            df['run_name'] = df['amount_threads']
        
        # Add missing columns with empty entries to df
        for column in master_df.columns:
            if column not in df.columns:
                df[column] = pd.NA
        
        # Ensure df has the same column order as master_df
        df = df[master_df.columns]
        
        dataframes.append(df)
    
    # Concatenate all dataframes and drop duplicates
    merged_df = pd.concat(dataframes, ignore_index=True)
    merged_df = merged_df.drop_duplicates()
    
    return merged_df

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python merge_csv.py <master_file> <csv_file1> <csv_file2> <csv_file3>")
        sys.exit(1)
    
    master_file = sys.argv[1]
    csv_files = sys.argv[2:]
    
    merged_df = merge_csv_files(master_file, csv_files)
    
    # Save the merged dataframe back to the master file
    merged_df.to_csv(master_file, index=False)
    
    print(f"Merged CSV files have been saved to {master_file}")
