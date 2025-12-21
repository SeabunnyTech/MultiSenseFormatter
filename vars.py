# 儀器編號檔案路徑
INSTRUMENT_FILE = r"data\20251031_25處MT潛勢區儀器編號.xlsx"

# 數據資料檔所在資料夾
INPUT_DIR = r"data\input"

# 輸出資料夾
SEPERATED_DIR = r"data\seperated"

# --- General Settings for Processors ---
# The specific date to use for zeroing the water level data.
# Format must be YYYY-MM-DD
ZERO_DATE = "2023-06-15"

# --- Sensor-Specific Configurations ---

# 1. Water Level Sensor
WATER_LEVEL_FORMAT_V1 = {
    "id": "Standard",
    "expected_columns": ['儀器名稱', '系統時間', '水位高', '相對水位高'],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "水位高", "output_name": "水位高歸零值"}
    ]
}

WATER_LEVEL_FORMAT_V2 = {
    "id": "Standard",
    "expected_columns": ['儀器名稱', '系統時間', '水位高', '相對水位高', 'Unnamed: 4'],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "水位高", "output_name": "水位高歸零值"}
    ]
}

WATER_LEVEL_CONFIG = {
    "sensor_name": "Water Level",
    "target_subdir": "水位觀測井",
    "input_path": SEPERATED_DIR,
    "output_path": r"data\zeroed",
    "formats": [
        WATER_LEVEL_FORMAT_V1,
        WATER_LEVEL_FORMAT_V2
    ]
}

# 2. Dual Value Sensor (Example)

# DUAL_VALUE_FORMAT_V1 = {
    # "id": "Standard Dual-Value",
    # "expected_columns": ['Date', 'Time', 'Value_A', 'Value_B'],
    # "time_column": "Date", # Assuming date/time might be in one or two columns
    # "value_columns": [ # A list for multiple value columns
        # {"name": "Value_A", "output_name": "Value_A_zeroed"},
        # {"name": "Value_B", "output_name": "Value_B_zeroed"}
    # ]
# }

# DUAL_VALUE_CONFIG = {
    # "sensor_name": "Dual Value Sensor",
    # "target_subdir": "雙值感測器", # Example name for the sub-directory
    # "input_path": SEPERATED_DIR,
    # "output_path": r"data\zeroed",
    # "formats": [
        # DUAL_VALUE_FORMAT_V1,
    # ]
# }



# 3. Surface Extensometer

EXTENSOMETER_FORMAT_V1 = {
    "id": "Standard Extensometer",
    "expected_columns": ['儀器名稱', '系統時間', '伸張量', '累積變位量', '1日變位量'],
    "time_column": "系統時間",
    "value_columns": [
        {"name": "伸張量", "output_name": "伸張量歸零值"}
    ]
}

EXTENSOMETER_CONFIG = {
    "sensor_name": "Surface Extensometer",
    "target_subdir": "地表伸縮計",
    "input_path": SEPERATED_DIR,
    "output_path": r"data\zeroed",
    "formats": [
        EXTENSOMETER_FORMAT_V1,
    ]
}
