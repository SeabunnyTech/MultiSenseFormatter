import sys
import os
from vars import WATER_LEVEL_CONFIG, ZERO_DATE
from processors import WaterLevelProcessor

def main():
    """
    Main entry point for running sensor data processors.
    """
    # Currently, we only have one processor.
    # In the future, you could add logic here to select different
    # processors based on command-line arguments or other settings.
    
    print("Initializing Water Level Processor...")
    processor = WaterLevelProcessor(config=WATER_LEVEL_CONFIG, zero_date_str=ZERO_DATE)
    
    processor.run()

if __name__ == "__main__":
    # Ensure the console can display Unicode characters correctly
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    main()
