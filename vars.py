        # 儀器編號檔案路徑
    INSTRUMENT_FILE = r"data\20251031_25處MT潛勢區儀器編號.xlsx"
    
    # 數據資料檔所在資料夾
    INPUT_DIR = r"data\input"
    
    # 輸出資料夾
    SEPERATED_DIR = r"data\seperated"
    
    # --- General Settings for Processors ---
    # The specific date to use for zeroing the water level data.
    # Format must be YYYY-MM-DD
    ZERO_DATE = "2025-01-15"
    
    # --- Sensor-Specific Configurations ---
    
    # Define individual format specifications first for clarity.
    WATER_LEVEL_FORMAT_V1 = {
        "id": "Standard",
        "expected_columns": ['儀器名稱', '系統時間', '水位高', '相對水位高'],
        "value_column": "水位高",
        "output_zeroed_column_name": "水位高歸零值"
    }
    
    # Example of another possible format for the same sensor.
    # You can add more formats here as needed.
    WATER_LEVEL_FORMAT_V2 = {
        "id": "Simplified",
        "expected_columns": ['時間', '水位'],
        "value_column": "水位",
        "output_zeroed_column_name": "水位歸零值"
    }
    
    
    # The main configuration object now contains a list of possible formats.
    WATER_LEVEL_CONFIG = {
        "sensor_name": "Water Level",
        "target_subdir": "水位觀測井",
        "input_path": SEPERATED_DIR,
        "output_path": r"data\zeroed",
        "formats": [
            WATER_LEVEL_FORMAT_V1,
            # WATER_LEVEL_FORMAT_V2, # Currently commented out, uncomment to enable.
        ]
    }
    
    # In the future, you can add other sensor configs here, e.g.:
    # INCLINOMETER_CONFIG = { ... }
    