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


def build_insar_dates_map(insar_batch_dir):
    """
    從 InSAR 批次目錄建立 站號 → 完整影像日期清單 映射。

    歸零起始日不再固定，而是在處理各儀器時取「監測開始後第一個 InSAR 影像
    日期」，因此這裡回傳每站的完整影像日期清單（YYYY-MM-DD，已排序）。
    """
    import pandas as pd
    import shapefile as shp_module

    # 1. 載入各軌道 T*.xlsx 的完整影像日期清單（以影像日期數為鍵，供 shapefile 欄位數比對）
    track_dates = {}  # {date_count: [YYYY-MM-DD, ...]}
    for f in sorted(os.listdir(insar_batch_dir)):
        if not (f.startswith('T') and f.endswith('.xlsx')):
            continue
        df = pd.read_excel(os.path.join(insar_batch_dir, f), header=None)
        raw = [str(d).strip() for d in df[0] if len(str(d).strip()) == 8 and str(d).strip().isdigit()]
        date_strs = sorted(f"{d[:4]}-{d[4:6]}-{d[6:8]}" for d in raw)
        # 註冊精確數量和 -1（例：T54 有 55 個有效日期但 shapefile 只有 54 個欄位）
        track_dates[len(raw)] = date_strs
        track_dates[len(raw) - 1] = date_strs
        if date_strs:
            print(f"  {f}: {len(raw)} 個影像日期 ({date_strs[0]} ~ {date_strs[-1]})")

    # 2. 從 shapefile 欄位數判斷各站所屬軌道，取得該軌道完整影像日期清單
    dates_map = {}
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
            if fc in track_dates:
                dates_map[station] = track_dates[fc]
        except Exception:
            continue

    return dates_map


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
        help='InSAR 批次資料夾路徑；各儀器以「監測開始後第一個 InSAR 影像日期」為歸零起始日'
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

    # 建立各站 InSAR 影像日期映射（實際歸零起始日於處理各儀器時，依監測起始日決定）
    insar_dates_map = None
    if args.insar_batch:
        print(f"從 InSAR 批次建立影像日期映射: {args.insar_batch}")
        insar_dates_map = build_insar_dates_map(args.insar_batch)
        if insar_dates_map:
            for station, dates in sorted(insar_dates_map.items()):
                print(f"  站號 {station}: {len(dates)} 個影像日期 ({dates[0]} ~ {dates[-1]})")
        else:
            print("  警告: 無法建立影像日期映射，將使用預設歸零日期")

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
            processor = proc_cls(config=config, force_overwrite=args.force, insar_dates_map=insar_dates_map)
        else:
            processor = proc_cls(config=config, zero_date_str=ZERO_DATE, force_overwrite=args.force, insar_dates_map=insar_dates_map)

        processor.run()


if __name__ == "__main__":
    # 確保 Windows 終端正確顯示 Unicode
    if sys.platform == "win32":
        os.system("chcp 65001 > nul")

    main()
