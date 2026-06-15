import sys
import os
import argparse
from vars import (
    WATER_LEVEL_CONFIG, EXTENSOMETER_CONFIG, INCLINOMETER_CONFIG,
    RAIN_GAUGE_CONFIG, GNSS_CONFIG, ZERO_DATE
)
from processors import ZeroingProcessor, SeasonalRainfallProcessor, GNSSProcessor

# 感測器註冊表：key 為 CLI 使用的短名稱
SENSOR_REGISTRY = {
    "water":         ("水位觀測井",       ZeroingProcessor,           WATER_LEVEL_CONFIG),
    "extensometer":  ("地表伸縮計",       ZeroingProcessor,           EXTENSOMETER_CONFIG),
    "inclinometer":  ("地表傾斜計(雙軸)", ZeroingProcessor,           INCLINOMETER_CONFIG),
    "rain":          ("雨量計",           SeasonalRainfallProcessor,  RAIN_GAUGE_CONFIG),
    "gnss":          ("GNSS地表變位",     GNSSProcessor,              GNSS_CONFIG),
}


def parse_args():
    """解析命令列參數"""
    sensor_keys = list(SENSOR_REGISTRY.keys())
    sensor_help = ", ".join(f"{k} ({v[0]})" for k, v in SENSOR_REGISTRY.items())

    parser = argparse.ArgumentParser(
        description="感測器資料歸零處理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
可用的感測器: {sensor_help}

範例:
  python run_processor.py                       # 執行所有感測器
  python run_processor.py --sensor gnss         # 只執行 GNSS
  python run_processor.py --sensor gnss rain    # 執行 GNSS 和雨量計
  python run_processor.py --force --sensor water # 強制覆蓋 + 只跑水位
  python run_processor.py --list                # 列出所有可用的感測器
        """
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='強制覆蓋已存在的輸出檔案（不詢問）'
    )
    parser.add_argument(
        '--sensor', '-s',
        nargs='+',
        choices=sensor_keys,
        metavar='SENSOR',
        help=f'指定要執行的感測器（可多個）。可選: {", ".join(sensor_keys)}'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='列出所有可用的感測器並退出'
    )
    return parser.parse_args()


def main():
    """主程式進入點"""
    args = parse_args()

    if args.list:
        print("可用的感測器:")
        for key, (name, proc_cls, _) in SENSOR_REGISTRY.items():
            print(f"  {key:<15} {name} ({proc_cls.__name__})")
        return

    # 決定要執行哪些感測器
    selected = args.sensor if args.sensor else list(SENSOR_REGISTRY.keys())

    for key in selected:
        name, proc_cls, config = SENSOR_REGISTRY[key]
        print(f"\n初始化{name}處理器...")

        # SeasonalRainfallProcessor 不需要 zero_date_str
        if proc_cls is SeasonalRainfallProcessor:
            processor = proc_cls(config=config, force_overwrite=args.force)
        else:
            processor = proc_cls(config=config, zero_date_str=ZERO_DATE, force_overwrite=args.force)

        processor.run()


if __name__ == "__main__":
    # 確保 Windows 終端正確顯示 Unicode
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    main()
