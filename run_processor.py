import sys
import os
import argparse
from vars import (
    WATER_LEVEL_CONFIG, EXTENSOMETER_CONFIG, INCLINOMETER_CONFIG,
    RAIN_GAUGE_CONFIG, GNSS_CONFIG, ZERO_DATE
)
from processors import ZeroingProcessor, SeasonalRainfallProcessor, GNSSProcessor


def parse_args():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(
        description="感測器資料歸零處理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python run_processor.py              # 互動模式，遇到已存在檔案會詢問
  python run_processor.py --force      # 強制覆蓋所有已存在的檔案
        """
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='強制覆蓋已存在的輸出檔案（不詢問）'
    )
    return parser.parse_args()


def main():
    """主程式進入點"""
    args = parse_args()

    # --- 1. Run the processor for Water Level data ---
    # print("初始化水位計處理器...")
    # water_processor = ZeroingProcessor(
    #     config=WATER_LEVEL_CONFIG,
    #     zero_date_str=ZERO_DATE,
    #     force_overwrite=args.force
    # )
    # water_processor.run()

    # --- 2. Run the processor for Surface Extensometer data ---
    # print("初始化地表伸縮計處理器...")
    # extensometer_processor = ZeroingProcessor(
        # config=EXTENSOMETER_CONFIG,
        # zero_date_str=ZERO_DATE,
        # force_overwrite=args.force
    # )
    # extensometer_processor.run()

    # --- 3. Run the processor for Inclinometer data ---
    print("\n初始化傾斜計處理器...")
    inclinometer_processor = ZeroingProcessor(
        config=INCLINOMETER_CONFIG,
        zero_date_str=ZERO_DATE,
        force_overwrite=args.force
    )
    inclinometer_processor.run()

    # --- 4. Run the processor for Rain Gauge data ---
    # print("\n初始化雨量計處理器...")
    # rain_gauge_processor = SeasonalRainfallProcessor(
        # config=RAIN_GAUGE_CONFIG,
        # force_overwrite=args.force
    # )
    # rain_gauge_processor.run()

    # --- 5. Run the processor for GNSS data ---
    # print("\n初始化 GNSS 處理器...")
    # gnss_processor = GNSSProcessor(
        # config=GNSS_CONFIG,
        # zero_date_str=ZERO_DATE,
        # force_overwrite=args.force
    # )
    # gnss_processor.run()


if __name__ == "__main__":
    # 確保 Windows 終端正確顯示 Unicode
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    main()
