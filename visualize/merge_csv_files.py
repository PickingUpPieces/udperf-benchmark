import pandas as pd
import sys

def merge_csv_files(master_file, csv_file1, csv_file2):
    master_df = pd.read_csv(master_file)
    df1 = pd.read_csv(csv_file1)
    df2 = pd.read_csv(csv_file2)
    
    # Check for run_name in df1 and use amount_threads if necessary
    if 'run_name' not in df1.columns and 'amount_threads' in df1.columns:
        df1['run_name'] = df1['amount_threads']

    # Add missing columns with empty entries to df1
    for column in master_df.columns:
        if column not in df1.columns:
            df1[column] = pd.NA

    # Check for run_name in df2 and use amount_threads if necessary
    if 'run_name' not in df2.columns and 'amount_threads' in df2.columns:
        df2['run_name'] = df2['amount_threads']
    
    # Add missing columns with empty entries to df2
    for column in master_df.columns:
        if column not in df2.columns:
            df2[column] = pd.NA

    # Ensure both dfs have the same column order as master_df
    df1 = df1[master_df.columns]
    df2 = df2[master_df.columns]
    
    # Merge df1 with master_df
    merged_df = pd.concat([master_df, df1], ignore_index=True)
    
    # Merge df2 with the merged_df
    merged_df = pd.concat([merged_df, df2], ignore_index=True)

    # Drop duplicate rows if any
    merged_df = merged_df.drop_duplicates()
    
    return merged_df

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python merge_csv.py <master_file> <csv_file1> <csv_file2>")
        sys.exit(1)
    
    master_file = sys.argv[1]
    csv_file1 = sys.argv[2]
    csv_file2 = sys.argv[3]
    
    merged_df = merge_csv_files(master_file, csv_file1, csv_file2)
    
    # Save the merged dataframe back to the master file
    merged_df.to_csv(master_file, index=False)
    
    print(f"Merged CSV files have been saved to {master_file}")
