    # 儀器編號檔案路徑
INSTRUMENT_FILE = r"C:\Users\User\Documents\GitHub\MultiSenseFormatter\data\20251031_25處MT潛勢區儀器編號.xlsx"

# 數據資料檔所在資料夾
INPUT_DIR = r"C:\Users\User\Documents\GitHub\MultiSenseFormatter\data\input"

# 輸出資料夾
SEPERATED_DIR = r"C:\Users\User\Documents\GitHub\MultiSenseFormatter\data\seperated"

# --- Settings for zero_water_level.py ---

# The specific date to use for zeroing the water level data.
# Format must be YYYY-MM-DD
ZERO_DATE = "2023-06-15"

# Input path for the zeroing script (typically the output of the separation script)
ZERO_INPUT_PATH = SEPERATED_DIR

# Output path for the zeroing script
ZERO_OUTPUT_PATH = r"C:\Users\User\Documents\GitHub\MultiSenseFormatter\data\zeroed"