import os
import pandas as pd

def zero_water_level_data(input_root_dir, output_root_dir):
    """
    Processes water level data from Excel files, zeros out the water level
    relative to the first entry, and saves the output as CSV files.
    Skips files that have already been processed.

    Args:
        input_root_dir (str): The root directory containing the input data
                              (e.g., 'data/separated').
        output_root_dir (str): The root directory where processed data
                               will be saved (e.g., 'data/zeroed').
    """
    # Expected column names in the input Excel files, as provided by the user.
    EXPECTED_INPUT_COLUMNS = ['儀器名稱', '系統時間', '水位高', '相對水位高']

    TARGET_SUBDIR_NAME = '水位觀測井'

    # Ensure output root directory exists
    os.makedirs(output_root_dir, exist_ok=True)

    print(f"Starting data processing from '{input_root_dir}' to '{output_root_dir}'")

    processed_count = 0
    skipped_mismatch_count = 0
    skipped_existing_count = 0
    error_count = 0

    for root, dirs, files in os.walk(input_root_dir):
        # Check if the current directory is a '水位觀測井' directory or a subdirectory of it
        # We want to process files directly inside '水位觀測井'
        if TARGET_SUBDIR_NAME in root.split(os.sep):
            # Determine the relative path from the input_root_dir to maintain structure
            relative_path = os.path.relpath(root, input_root_dir)
            current_output_dir = os.path.join(output_root_dir, relative_path)
            os.makedirs(current_output_dir, exist_ok=True)

            for file_name in files:
                if file_name.endswith('.xlsx') and not file_name.startswith('~$'): # Ignore temporary Excel files
                    input_file_path = os.path.join(root, file_name)
                    output_file_name = os.path.splitext(file_name)[0] + '.csv'
                    output_file_path = os.path.join(current_output_dir, output_file_name)

                    # Check if the output file already exists
                    if os.path.exists(output_file_path):
                        print(f"Skipping '{input_file_path}' as output already exists.")
                        skipped_existing_count += 1
                        continue

                    print(f"Processing '{input_file_path}'...")

                    try:
                        # Read the Excel file
                        df = pd.read_excel(input_file_path)
                        # Strip whitespace from column names
                        df.columns = [col.strip() for col in df.columns]

                        # Validate column names
                        if list(df.columns) != EXPECTED_INPUT_COLUMNS:
                            print(f"WARNING: Column names in '{file_name}' do not match expected. Skipping.")
                            print(f"  Expected: {EXPECTED_INPUT_COLUMNS}")
                            print(f"  Found:    {list(df.columns)}")
                            skipped_mismatch_count += 1
                            continue

                        # Convert '系統時間' to datetime objects
                        # Ensure '系統時間' is treated as a string before converting to datetime
                        df['系統時間'] = pd.to_datetime(df['系統時間'].astype(str))

                        # Sort by '系統時間' to ensure correct ordering
                        df = df.sort_values(by='系統時間').reset_index(drop=True)

                        # Filter to get the last entry for each unique date
                        df['date_only'] = df['系統時間'].dt.date
                        # Use .copy() to avoid SettingWithCopyWarning
                        df_last_per_day = df.drop_duplicates(subset=['date_only'], keep='last').copy() 

                        # Get the water level of the very first data entry in the *processed* data for zeroing
                        if not df_last_per_day.empty:
                            first_water_level = df_last_per_day['水位高'].iloc[0]
                        else:
                            print(f"WARNING: Processed data for '{file_name}' is empty. Skipping.")
                            skipped_mismatch_count += 1
                            continue

                        # Calculate the zeroed water level
                        df_last_per_day['水位高歸零值'] = df_last_per_day['水位高'] - first_water_level

                        # Prepare the output DataFrame with the specified format
                        output_df = pd.DataFrame()
                        output_df[0] = df_last_per_day['系統時間'].dt.strftime('%Y/%m/%d')
                        output_df[1] = df_last_per_day['系統時間'].dt.strftime('%Y/%m/%d %H:%M')
                        output_df[2] = df_last_per_day['水位高']
                        output_df[3] = df_last_per_day['水位高歸零值']

                        # Save to CSV without header and index
                        output_df.to_csv(output_file_path, header=False, index=False, encoding='utf-8')
                        processed_count += 1
                        print(f"Successfully processed and saved to '{output_file_path}'")

                    except Exception as e:
                        print(f"ERROR: Failed to process '{input_file_path}'. Reason: {e}")
                        error_count += 1
                        continue
    
    print("\n--- Processing Summary ---")
    print(f"Total files processed: {processed_count}")
    print(f"Total files skipped (already exist): {skipped_existing_count}")
    print(f"Total files skipped (column mismatch or empty): {skipped_mismatch_count}")
    print(f"Total files with errors: {error_count}")
    print("------------------------")


if __name__ == '__main__':
    # Define input and output root directories relative to the script's location
    # The script expects 'data/separated' to exist and contain the hierarchical structure.
    # The output will be created in 'data/zeroed'.
    
    # Assuming script is run from project root, or zero_water_level.py is in 'zero' folder
    # and main script is called from root, then paths should be relative to root.
    
    input_base_path = 'data/seperated'
    output_base_path = 'data/zeroed'

    # Call the processing function
    zero_water_level_data(input_base_path, output_base_path)
