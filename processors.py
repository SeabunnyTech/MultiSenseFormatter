import os
import pandas as pd
import sys
from abc import ABC, abstractmethod

class Colors:
    """ANSI color codes"""
    YELLOW = '\033[93m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'

class BaseProcessor(ABC):
    """
    A base class for processing sensor data files.
    It handles file discovery, iteration, progress display, and common checks.
    It can handle multiple data formats for a single sensor type.
    """
    def __init__(self, config, zero_date_str):
        self.config = config
        self.sensor_name = config["sensor_name"]
        self.target_subdir = config["target_subdir"]
        self.input_root_dir = config["input_path"]
        self.output_root_dir = config["output_path"]
        
        try:
            self.zero_date = pd.to_datetime(zero_date_str).date()
        except ValueError:
            print(f"{Colors.RED}ERROR: Invalid zero_date format '{zero_date_str}'. Please use YYYY-MM-DD.{Colors.ENDC}")
            sys.exit(1)

    def run(self):
        """Main method to execute the processing pipeline."""
        files_to_process = self._collect_files()
        
        total_files = len(files_to_process)
        if total_files == 0:
            print(f"No files found to process in '{self.target_subdir}' subdirectories.")
            return

        print(f"\nProcessing sensor: {self.sensor_name}")
        print(f"Found {total_files} files. Starting processing.")
        print(f"Using '{self.zero_date}' as the zeroing date.")

        counters = {
            "processed": 0, "skipped_exist": 0, "skipped_header": 0,
            "skipped_date": 0, "skipped_nodata": 0, "error": 0
        }

        for i, input_file_path in enumerate(files_to_process, start=1):
            self._process_file(i, total_files, input_file_path, counters)

        self._print_summary(counters)
        self._cleanup_empty_dirs()

        if counters["error"] > 0:
            print(f"\n{Colors.RED}Script finished with {counters['error']} errors.{Colors.ENDC}")
            sys.exit(1)

    def _collect_files(self):
        """Collects all relevant files for processing."""
        files_to_process = []
        print(f"Collecting files from '{self.input_root_dir}' in subdir '{self.target_subdir}'...")
        for root, _, files in os.walk(self.input_root_dir):
            if self.target_subdir in root.split(os.sep):
                for file_name in files:
                    if file_name.endswith('.xlsx') and not file_name.startswith('~$'):
                        files_to_process.append(os.path.join(root, file_name))
        return files_to_process

    def _find_matching_format(self, actual_columns):
        """Finds a matching format from the config's format list."""
        for fmt in self.config["formats"]:
            if actual_columns == fmt["expected_columns"]:
                return fmt
        return None

    def _process_file(self, i, total_files, input_file_path, counters):
        """Processes a single file with all checks and logic."""
        file_name = os.path.basename(input_file_path)

        # Extract location name from path for clearer progress display
        try:
            relative_dir = os.path.relpath(os.path.dirname(input_file_path), self.input_root_dir)
            location_name = relative_dir.split(os.sep)[0]
        except (ValueError, IndexError):
            location_name = "Unknown"

        progress_prefix = f"[{i:>{len(str(total_files))}}/{total_files}]"
        print(f"{progress_prefix} Processing [{location_name}] '{file_name}'... ")

        try:
            relative_path = os.path.relpath(os.path.dirname(input_file_path), self.input_root_dir)
            current_output_dir = os.path.join(self.output_root_dir, relative_path)
            os.makedirs(current_output_dir, exist_ok=True)
            output_file_name = os.path.splitext(file_name)[0] + '.csv'
            output_file_path = os.path.join(current_output_dir, output_file_name)

            if os.path.exists(output_file_path):
                print(f"{Colors.YELLOW}  -> SKIPPED (Already exists){Colors.ENDC}")
                counters["skipped_exist"] += 1
                return

            df_header = pd.read_excel(input_file_path, nrows=0)
            df_header.columns = [col.strip() for col in df_header.columns]
            
            matched_format = self._find_matching_format(list(df_header.columns))
            
            if not matched_format:
                print(f"{Colors.YELLOW}  -> SKIPPED (Unrecognized Header: {list(df_header.columns)}){Colors.ENDC}")
                counters["skipped_header"] += 1
                return

            df = pd.read_excel(input_file_path)
            df.columns = [col.strip() for col in df.columns]
            
            output_df = self._process_data(df, matched_format)

            if output_df is None:
                # _process_data returns None if skipping is needed. The reason is printed inside.
                counters["skipped_date"] += 1
                return
            
            output_df.to_csv(output_file_path, header=False, index=False, encoding='utf-8')
            print(f"{Colors.GREEN}  -> OK (Format: '{matched_format['id']}') {Colors.ENDC}")
            counters["processed"] += 1

        except Exception as e:
            print(f"{Colors.RED}  -> ERROR ({e}){Colors.ENDC}")
            counters["error"] += 1

    @abstractmethod
    def _process_data(self, df, matched_format):
        """
        Sensor-specific data processing logic.
        This method MUST be implemented by subclasses.
        It should return a processed DataFrame or None if the file should be skipped.
        """
        pass

    def _print_summary(self, counters):
        print("\n--- Processing Summary ---")
        print(f"Total files processed: {counters['processed']}")
        print(f"Total files skipped (already exist): {counters['skipped_exist']}")
        print(f"Total files skipped (unrecognized header): {counters['skipped_header']}")
        print(f"Total files skipped (no zero-date data): {counters['skipped_date']}")
        print(f"Total files with errors: {counters['error']}")
        print("------------------------")

    def _cleanup_empty_dirs(self):
        """Walks from the bottom up and removes any empty directories."""
        print(f"\nCleaning up empty directories in '{self.output_root_dir}'...")
        # List of directories that we tried to create. Only remove subdirs of these.
        for root, dirs, _ in os.walk(self.output_root_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if not os.listdir(dir_path):
                        print(f"  - Removing empty directory: {dir_path}")
                        os.rmdir(dir_path)
                except OSError as e:
                    print(f"  - Error removing directory {dir_path}: {e}")



class ZeroingProcessor(BaseProcessor):
    """
    Specific processor for sensors that require zeroing on multiple value columns.
    """

    def _process_data(self, df, matched_format):
        """
        Implements data processing for multi-value sensors. It iterates through
        a list of value columns defined in the config.
        """
        # Get the list of value column configurations
        value_configs = matched_format["value_columns"]
        
        # Determine the time column, supporting single or multiple time-related columns
        time_col = matched_format.get("time_column", "系統時間")
        if time_col not in df.columns and 'Time' in df.columns:
             time_col = 'Time' # Fallback for flexibility

        df[time_col] = pd.to_datetime(df[time_col].astype(str))
        df = df.sort_values(by=time_col).reset_index(drop=True)
        df['date_only'] = df[time_col].dt.date
        df_last_per_day = df.drop_duplicates(subset=['date_only'], keep='last').copy()

        if df_last_per_day.empty:
            print(f"{Colors.YELLOW}  -> SKIPPED (No data after initial parsing){Colors.ENDC}")
            return None

        max_date_in_file = df_last_per_day['date_only'].max()
        if self.zero_date > max_date_in_file:
            print(f"{Colors.YELLOW}  -> SKIPPED (Zero date {self.zero_date} is after last data date {max_date_in_file}){Colors.ENDC}")
            return None

        df_filtered = df_last_per_day[df_last_per_day['date_only'] >= self.zero_date].copy()
        
        zero_row = df_filtered[df_filtered['date_only'] == self.zero_date]
        if zero_row.empty:
            print(f"{Colors.YELLOW}  -> SKIPPED (Zero date {self.zero_date} not found in available data range){Colors.ENDC}")
            return None
        
        # Find zero values for all specified columns
        zero_values = {}
        for v_conf in value_configs:
            col_name = v_conf["name"]
            zero_values[col_name] = zero_row[col_name].iloc[0]

        # Calculate zeroed values for all specified columns
        for v_conf in value_configs:
            col_name = v_conf["name"]
            output_name = v_conf["output_name"]
            df_filtered[output_name] = df_filtered[col_name] - zero_values[col_name]

        # Prepare the output DataFrame dynamically
        output_df = pd.DataFrame()
        output_df[time_col] = df_filtered[time_col].dt.strftime('%Y/%m/%d %H:%M')
        
        for v_conf in value_configs:
            output_df[v_conf["name"]] = df_filtered[v_conf["name"]]
            output_df[v_conf["output_name"]] = df_filtered[v_conf["output_name"]]
        
        return output_df
