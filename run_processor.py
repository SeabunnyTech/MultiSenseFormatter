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


def build_zero_date_map(insar_batch_dir):
    """從 InSAR 批次目錄建立 站號→歸零日期 映射（各站以其 2018 年第一個 InSAR 影像日期歸零）"""
    import pandas as pd
    import shapefile as shp_module

    # 1. 載入 T*.xlsx，找各軌道 2018 年第一個影像日期
    track_zero_dates = {}  # {date_count: zero_date_str}
    for f in sorted(os.listdir(insar_batch_dir)):
        if not (f.startswith('T') and f.endswith('.xlsx')):
            continue
        df = pd.read_excel(os.path.join(insar_batch_dir, f), header=None)
        dates = [str(d).strip() for d in df[0] if len(str(d).strip()) == 8 and str(d).strip().isdigit()]
        dates_2018 = [d for d in dates if d.startswith('2018')]
        if not dates_2018:
            continue
        first_2018 = dates_2018[0]
        zero_str = f"{first_2018[:4]}-{first_2018[4:6]}-{first_2018[6:8]}"
        # 註冊精確數量和 -1（T54 有 55 個有效日期但只有 54 個欄位）
        track_zero_dates[len(dates)] = zero_str
        track_zero_dates[len(dates) - 1] = zero_str
        print(f"  {f}: 2018 第一張影像 {zero_str} ({len(dates)} 個日期)")

    # 2. 從 shapefile 欄位數判斷各站所屬軌道
    zero_map = {}
    for f in sorted(os.listdir(insar_batch_dir)):
        if not f.endswith('.shp'):
            continue
        station = f.split('_')[0]
        dbf_path = os.path.join(insar_batch_dir, f.replace('.shp', '.dbf'))
        if not os.path.exists(dbf_path):
            continue
        try:
            sf = shp_module.Reader(os.path.join(insar_batch_dir, f))
            fc = len([fd[0] for fd in sf.fields[1:] if fd[0].strip().startswith('Field')])
            zero_date = track_zero_dates.get(fc)
            if zero_date:
                zero_map[station] = zero_date
        except Exception:
            continue

    return zero_map


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
  python run_processor.py --batch data/batches/08_監測數據           # 批次模式
  python run_processor.py --batch data/batches/08_監測數據 -s gnss   # 批次模式 + 只跑 GNSS
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
    parser.add_argument(
        '--batch', '-b',
        type=str,
        metavar='PATH',
        help='批次資料夾路徑 (使用 {batch}-seperated 為輸入，{batch}-zeroed 為輸出)'
    )
    parser.add_argument(
        '--insar-batch',
        type=str,
        metavar='PATH',
        help='InSAR 批次資料夾路徑，各站以其 2018 年第一個 InSAR 影像日期歸零'
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

    # 批次模式路徑設定
    if args.batch:
        batch_path = args.batch.rstrip('/\\')
        batch_input = batch_path + '-seperated'
        batch_output = batch_path + '-zeroed'
        if not os.path.isdir(batch_input):
            print(f"錯誤: 找不到分類後的資料夾 '{batch_input}'")
            print(f"請先執行: python split_excel_by_location.py --batch {batch_path}")
            sys.exit(1)

    # 建立各站歸零日期映射
    zero_date_map = None
    if args.insar_batch:
        print(f"從 InSAR 批次建立歸零日期映射: {args.insar_batch}")
        zero_date_map = build_zero_date_map(args.insar_batch)
        if zero_date_map:
            for station, zd in sorted(zero_date_map.items()):
                print(f"  站號 {station}: 歸零日期 {zd}")
        else:
            print("  警告: 無法建立歸零日期映射，將使用預設日期")

    # 決定要執行哪些感測器
    selected = args.sensor if args.sensor else list(SENSOR_REGISTRY.keys())

    for key in selected:
        name, proc_cls, config = SENSOR_REGISTRY[key]

        # 批次模式覆蓋輸入/輸出路徑
        if args.batch:
            config = {**config, "input_path": batch_input, "output_path": batch_output}

        print(f"\n初始化{name}處理器...")

        # SeasonalRainfallProcessor 不需要 zero_date_str
        if proc_cls is SeasonalRainfallProcessor:
            processor = proc_cls(config=config, force_overwrite=args.force, zero_date_map=zero_date_map)
        else:
            processor = proc_cls(config=config, zero_date_str=ZERO_DATE, force_overwrite=args.force, zero_date_map=zero_date_map)

        processor.run()


if __name__ == "__main__":
    # 確保 Windows 終端正確顯示 Unicode
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    main()
