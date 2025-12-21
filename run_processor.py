import sys
import os
from vars import WATER_LEVEL_CONFIG, EXTENSOMETER_CONFIG, ZERO_DATE, INCLINOMETER_CONFIG
from processors import ZeroingProcessor

def main():
    """
    Main entry point for running sensor data processors.
    """
    # --- 1. Run the processor for Water Level data ---
    # print("Initializing Processor for Water Level...")
    # water_processor = ZeroingProcessor(config=WATER_LEVEL_CONFIG, zero_date_str=ZERO_DATE)
    # water_processor.run()

    # --- 3. Run the processor for Surface Extensometer data ---
    # print("\nInitializing Processor for Surface Extensometer...")
    # extensometer_processor = ZeroingProcessor(config=EXTENSOMETER_CONFIG, zero_date_str=ZERO_DATE)
    # extensometer_processor.run()

    print("\nInitializing Processor for Inclinometer...")
    inclinometer_processor = ZeroingProcessor(config=INCLINOMETER_CONFIG, zero_date_str=ZERO_DATE)
    inclinometer_processor.run()

if __name__ == "__main__":
    # Ensure the console can display Unicode characters correctly
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    main()
