import os
import pandas as pd
import sys

class Colors:
    """ANSI color codes"""
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

def zero_water_level_data(input_root_dir, output_root_dir, zero_date_str):
    """
    Processes water level data from Excel files. It discards any data before
    the specified zero_date, zeros out the water level relative to the entry
    on that zero_date, and saves the output as CSV files.
    Skips files that have already been processed or don't contain the zero_date.

    Args:
        input_root_dir (str): The root directory containing the input data.
        output_root_dir (str): The root directory where processed data will be saved.
        zero_date_str (str): The specific date (YYYY-MM-DD) to use for zeroing.
    """
    # Expected column names in the input Excel files
    EXPECTED_INPUT_COLUMNS = ['儀器名稱', '系統時間', '水位高', '相對水位高']
    TARGET_SUBDIR_NAME = '水位觀測井'

    try:
        zero_date = pd.to_datetime(zero_date_str).date()
    except ValueError:
        print(f"{Colors.RED}ERROR: Invalid zero_date format '{zero_date_str}'. Please use YYYY-MM-DD.{Colors.ENDC}")
        sys.exit(1)

    # --- 1. Collect all files first for progress tracking ---
    files_to_process = []
    print("Collecting files to process...")
    for root, dirs, files in os.walk(input_root_dir):
        if TARGET_SUBDIR_NAME in root.split(os.sep):
            for file_name in files:
                if file_name.endswith('.xlsx') and not file_name.startswith('~$'):
                    files_to_process.append(os.path.join(root, file_name))

    total_files = len(files_to_process)
    if total_files == 0:
        print("No files found to process in '水位觀測井' subdirectories.")
        return

    print(f"Found {total_files} files. Starting processing.")
    print(f"Using '{zero_date_str}' as the zeroing date.")

    # Initialize counters
    processed_count = 0
    skipped_mismatch_count = 0
    skipped_existing_count = 0
    skipped_no_date_count = 0
    error_count = 0
    
    # --- 2. Process files with progress indicator ---
    for i, input_file_path in enumerate(files_to_process, start=1):
        file_name = os.path.basename(input_file_path)
        # Use a consistent width for the progress counter
        progress_prefix = f"[{i:>{len(str(total_files))}}/{total_files}]"
        print(f"{progress_prefix} Processing '{file_name}'... ")

        try:
            # Construct output path to check for existence
            relative_path = os.path.relpath(os.path.dirname(input_file_path), input_root_dir)
            current_output_dir = os.path.join(output_root_dir, relative_path)
            os.makedirs(current_output_dir, exist_ok=True)
            output_file_name = os.path.splitext(file_name)[0] + '.csv'
            output_file_path = os.path.join(current_output_dir, output_file_name)

            if os.path.exists(output_file_path):
                print(f"{Colors.YELLOW}  -> SKIPPED (Already exists){Colors.ENDC}")
                skipped_existing_count += 1
                continue

            # Header check
            df_header = pd.read_excel(input_file_path, nrows=0)
            df_header.columns = [col.strip() for col in df_header.columns]
            if list(df_header.columns) != EXPECTED_INPUT_COLUMNS:
                print(f"{Colors.YELLOW}  -> SKIPPED (Bad Header: Expected {EXPECTED_INPUT_COLUMNS}, Found {list(df_header.columns)}){Colors.ENDC}")
                skipped_mismatch_count += 1
                continue

            # Read full file
            df = pd.read_excel(input_file_path)
            df.columns = [col.strip() for col in df.columns]
            df['系統時間'] = pd.to_datetime(df['系統時間'].astype(str))
            df = df.sort_values(by='系統時間').reset_index(drop=True)
            df['date_only'] = df['系統時間'].dt.date
            df_last_per_day = df.drop_duplicates(subset=['date_only'], keep='last').copy()

            if df_last_per_day.empty:
                print(f"{Colors.YELLOW}  -> SKIPPED (No data){Colors.ENDC}")
                skipped_no_date_count += 1
                continue

            # --- NEW: Explicit check for zero date out of range ---
            max_date_in_file = df_last_per_day['date_only'].max()
            if zero_date > max_date_in_file:
                print(f"{Colors.YELLOW}  -> SKIPPED (Zero date {zero_date_str} is after last data date {max_date_in_file}){Colors.ENDC}")
                skipped_no_date_count += 1
                continue

            # Filter data to include only on and after the zero_date
            df_filtered = df_last_per_day[df_last_per_day['date_only'] >= zero_date].copy()

            # Find the row for the specific zero_date
            zero_row = df_filtered[df_filtered['date_only'] == zero_date]

            if zero_row.empty:
                print(f"{Colors.YELLOW}  -> SKIPPED (Zero date {zero_date_str} not found in available data range){Colors.ENDC}")
                skipped_no_date_count += 1
                continue
            
            # Get the water level value from that specific date
            zero_water_level = zero_row['水位高'].iloc[0]

            # Calculate the zeroed water level on the filtered data
            df_filtered['水位高歸零值'] = df_filtered['水位高'] - zero_water_level

            # Prepare the output DataFrame
            output_df = pd.DataFrame()
            output_df[0] = df_filtered['系統時間'].dt.strftime('%Y/%m/%d')
            output_df[1] = df_filtered['系統時間'].dt.strftime('%Y/%m/%d %H:%M')
            output_df[2] = df_filtered['水位高']
            output_df[3] = df_filtered['水位高歸零值']

            # Save to CSV
            output_df.to_csv(output_file_path, header=False, index=False, encoding='utf-8')
            print("  -> OK")
            processed_count += 1

        except Exception as e:
            print(f"{Colors.RED}  -> ERROR ({e}){Colors.ENDC}")
            error_count += 1
            continue

    print("\n--- Processing Summary ---")
    print(f"Total files processed: {processed_count}")
    print(f"Total files skipped (already exist): {skipped_existing_count}")
    print(f"Total files skipped (column mismatch): {skipped_mismatch_count}")
    print(f"Total files skipped (no zero-date data): {skipped_no_date_count}")
    print(f"Total files with errors: {error_count}")
    print("------------------------")

    if error_count > 0:
        print(f"\n{Colors.RED}Script finished with {error_count} errors.{Colors.ENDC}")
        sys.exit(1)


def cleanup_empty_dirs(path):
    """
    Walks from the bottom up and removes any empty directories.
    """
    print(f"\nCleaning up empty directories in '{path}'...")
    for root, dirs, files in os.walk(path, topdown=False):
        # Do not process the root path itself, only subdirectories
        if root == path:
            # On the first pass (deepest level), dirs will be subdirs of root
            # On the last pass, root will be the path itself, and we check its subdirs
            pass

        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                # Check if the directory is empty
                if not os.listdir(dir_path):
                    print(f"  - Removing empty directory: {dir_path}")
                    os.rmdir(dir_path)
            except OSError as e:
                print(f"  - Error removing directory {dir_path}: {e}")

if __name__ == '__main__':
    try:
        from vars import ZERO_DATE, ZERO_INPUT_PATH, ZERO_OUTPUT_PATH
    except ImportError:
        print("ERROR: Could not import settings from vars.py.")
        print("Please ensure vars.py exists and contains ZERO_DATE, ZERO_INPUT_PATH, and ZERO_OUTPUT_PATH.")
        sys.exit(1)
    
    # Call the main processing function
    zero_water_level_data(ZERO_INPUT_PATH, ZERO_OUTPUT_PATH, ZERO_DATE)
    
    # After processing, clean up any empty directories that might have been created
    cleanup_empty_dirs(ZERO_OUTPUT_PATH)