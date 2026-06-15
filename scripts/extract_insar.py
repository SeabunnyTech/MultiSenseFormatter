"""
InSAR 時間序列提取工具

從 defo_conv shapefile 中，根據指定座標提取 InSAR 累積變形量時間序列。
支援兩種提取模式：
  1. nearest  — 取離指定座標最近的單一點
  2. average  — 取指定座標半徑內所有點的平均值

用法:
  python extract_insar.py <shp_path> <lat> <lon> [--mode nearest|average] [--radius 50]
  python extract_insar.py <shp_path> --batch <csv_with_coords>

輸出: CSV 時間序列 (日期, 累積變形量mm)
"""

import argparse
import csv
import math
import os
import struct
import sys
from datetime import datetime

import shapefile
from pyproj import Transformer


# ==============================================================================
# 日期對應表（從 PNG 圖提取，待 shortbaseline 檔案取代）
#
# Field5 = 基線 (值=0)，Field6~Field15 = 10 個時間步的累積變形量
# 目前 policy066 與 policy260 共用相同日期序列
# ==============================================================================

FIELD_DATE_MAP = {
    "Field5":  "2022/01/23",  # 基線
    "Field6":  "2022/03/20",
    "Field7":  "2022/04/03",
    "Field8":  "2022/09/18",
    "Field9":  "2022/10/16",
    "Field10": "2023/03/19",
    "Field11": "2023/04/02",
    "Field12": "2023/07/23",
    "Field13": "2023/09/17",
    "Field14": "2023/10/01",
    "Field15": "2024/03/31",
}

# WGS84 -> TWD97/TM2
_transformer = Transformer.from_crs("EPSG:4326", "EPSG:3826", always_xy=True)


def wgs84_to_twd97(lon, lat):
    """將 WGS84 經緯度轉為 TWD97/TM2 投影座標 (公尺)"""
    return _transformer.transform(lon, lat)


def read_shapefile(shp_path):
    """
    讀取 defo_conv shapefile，回傳 (points, records)

    points: list of (x, y) in TWD97/TM2
    records: list of dict {field_name: value}

    因 pyshp 對部分 DBF 有相容性問題，使用手動解析 DBF 記錄。
    """
    sf = shapefile.Reader(shp_path)

    # 讀取所有點座標
    points = [shape.points[0] for shape in sf.shapes()]

    # 取得欄位定義（跳過 DeletionFlag）
    field_defs = sf.fields[1:]
    field_names = [f[0].strip() for f in field_defs]
    field_sizes = [f[1] for f in field_defs]  # not used, all are 20

    # 手動解析 DBF（pyshp record() 在這些檔案回傳 None）
    dbf_path = shp_path.replace('.shp', '.dbf') if shp_path.endswith('.shp') else shp_path + '.dbf'
    records = _parse_dbf_records(dbf_path, field_names)

    return points, records


def _parse_dbf_records(dbf_path, field_names):
    """手動解析 DBF 檔案記錄"""
    records = []
    with open(dbf_path, 'rb') as f:
        # 讀取 header
        f.read(4)  # version + date
        num_records = struct.unpack('<I', f.read(4))[0]
        header_size = struct.unpack('<H', f.read(2))[0]
        record_size = struct.unpack('<H', f.read(2))[0]

        # 跳到資料區
        f.seek(header_size)

        field_width = 20  # 每個欄位 20 bytes

        for _ in range(num_records):
            raw = f.read(record_size)
            if len(raw) < record_size:
                break

            rec = {}
            offset = 1  # 跳過 deletion flag
            for name in field_names:
                val_str = raw[offset:offset + field_width].decode('ascii', errors='replace').strip()
                try:
                    val = float(val_str) if '.' in val_str else int(val_str)
                except (ValueError, TypeError):
                    val = val_str
                rec[name] = val
                offset += field_width

            records.append(rec)

    return records


def find_nearest(points, target_x, target_y):
    """找到離目標座標最近的點，回傳 (index, distance)"""
    min_dist = float('inf')
    min_idx = 0
    for i, (px, py) in enumerate(points):
        dist = math.hypot(px - target_x, py - target_y)
        if dist < min_dist:
            min_dist = dist
            min_idx = i
    return min_idx, min_dist


def find_within_radius(points, target_x, target_y, radius_m):
    """找到半徑內的所有點，回傳 [(index, distance), ...]"""
    results = []
    for i, (px, py) in enumerate(points):
        dist = math.hypot(px - target_x, py - target_y)
        if dist <= radius_m:
            results.append((i, dist))
    return results


def extract_timeseries(records, indices, field_date_map=None):
    """
    從指定的記錄索引提取時間序列

    若 indices 只有一個，取該點的值；
    若有多個，取平均值。

    回傳: [(date_str, value), ...]
    """
    if field_date_map is None:
        field_date_map = FIELD_DATE_MAP

    # 取出要用的欄位（Field5~Field15 等有日期對應的）
    value_fields = sorted(field_date_map.keys(), key=lambda k: int(k.replace("Field", "")))

    timeseries = []
    for field in value_fields:
        date_str = field_date_map[field]

        if len(indices) == 1:
            val = records[indices[0]].get(field, None)
        else:
            vals = [records[idx].get(field, None) for idx in indices]
            vals = [v for v in vals if v is not None and isinstance(v, (int, float))]
            val = sum(vals) / len(vals) if vals else None

        if val is not None:
            timeseries.append((date_str, val))

    return timeseries


def _extract_from_loaded(points, records, target_x, target_y, mode, radius, field_date_map):
    """對已載入的 shapefile 資料執行提取（內部共用邏輯）"""
    result = {
        "target_twd97": (target_x, target_y),
        "mode": mode,
    }

    if mode == "nearest":
        idx, dist = find_nearest(points, target_x, target_y)
        result["matched_count"] = 1
        result["nearest_distance"] = dist
        result["timeseries"] = extract_timeseries(records, [idx], field_date_map)

    elif mode == "average":
        matches = find_within_radius(points, target_x, target_y, radius)
        if not matches:
            idx, dist = find_nearest(points, target_x, target_y)
            print(f"  警告: 半徑 {radius}m 內無點，改用最近點 (距離 {dist:.1f}m)")
            matches = [(idx, dist)]

        indices = [m[0] for m in matches]
        distances = [m[1] for m in matches]
        result["matched_count"] = len(matches)
        result["nearest_distance"] = min(distances)
        result["timeseries"] = extract_timeseries(records, indices, field_date_map)

    return result


def extract_single(shp_path, lat, lon, mode="nearest", radius=50, field_date_map=None):
    """
    對單一 WGS84 座標進行 InSAR 時間序列提取

    Args:
        shp_path: defo_conv shapefile 路徑
        lat: WGS84 緯度
        lon: WGS84 經度
        mode: "nearest" 或 "average"
        radius: average 模式的搜尋半徑（公尺）
        field_date_map: 欄位-日期對照表，None 時使用預設值
    """
    points, records = read_shapefile(shp_path)
    target_x, target_y = wgs84_to_twd97(lon, lat)
    return _extract_from_loaded(points, records, target_x, target_y, mode, radius, field_date_map)


def extract_single_twd97(shp_path, e, n, mode="nearest", radius=50, field_date_map=None,
                         _preloaded=None):
    """
    對單一 TWD97/TM2 座標進行 InSAR 時間序列提取

    Args:
        shp_path: defo_conv shapefile 路徑
        e: TWD97 東距 (公尺)
        n: TWD97 北距 (公尺)
        _preloaded: (points, records) 預載入資料，避免重複讀檔
    """
    if _preloaded:
        points, records = _preloaded
    else:
        points, records = read_shapefile(shp_path)
    return _extract_from_loaded(points, records, e, n, mode, radius, field_date_map)


def extract_batch(shp_path, instruments, mode="nearest", radius=50, field_date_map=None):
    """
    批次提取多個儀器的 InSAR 時間序列（只讀一次 shapefile）

    Args:
        shp_path: defo_conv shapefile 路徑
        instruments: list of dict, 每個 dict 需有 "name", "e", "n" 鍵
        mode: "nearest" 或 "average"
        radius: average 模式的搜尋半徑（公尺）

    Returns:
        list of (instrument_dict, result_dict)
    """
    print(f"讀取 shapefile: {shp_path}")
    preloaded = read_shapefile(shp_path)
    print(f"  共 {len(preloaded[0])} 個 InSAR 點")

    results = []
    for inst in instruments:
        name = inst["name"]
        e, n = inst["e"], inst["n"]
        print(f"  提取 {name} (E={e:.2f}, N={n:.2f}) [{mode}]...", end="")

        result = extract_single_twd97(shp_path, e, n, mode, radius, field_date_map,
                                      _preloaded=preloaded)
        print(f" 匹配 {result['matched_count']} 點, 最近 {result['nearest_distance']:.1f}m")
        results.append((inst, result))

    return results


def zero_timeseries(timeseries, zero_date_str):
    """
    對 InSAR 時間序列進行歸零處理

    因 InSAR 時間點稀疏，若歸零日期不在資料中，
    使用線性內插計算歸零基準值。保留所有時間點。

    Args:
        timeseries: [(date_str, value), ...]
        zero_date_str: 歸零日期 (YYYY-MM-DD 或 YYYY/MM/DD)

    Returns:
        (zeroed_timeseries, zero_info_dict)
    """
    zero_date = datetime.strptime(zero_date_str.replace('-', '/'), "%Y/%m/%d")

    # 轉換為 (datetime, value) 並排序
    dated = []
    for ds, val in timeseries:
        dt = datetime.strptime(ds, "%Y/%m/%d")
        dated.append((dt, val))
    dated.sort(key=lambda x: x[0])

    # 找歸零基準值
    zero_value = None
    method = None

    # 精確匹配
    for dt, val in dated:
        if dt == zero_date:
            zero_value = val
            method = "exact"
            break

    if zero_value is None:
        # 找前後最近的兩個點做線性內插
        before = [(dt, val) for dt, val in dated if dt < zero_date]
        after = [(dt, val) for dt, val in dated if dt > zero_date]

        if before and after:
            dt_b, val_b = before[-1]
            dt_a, val_a = after[0]
            ratio = (zero_date - dt_b).days / (dt_a - dt_b).days
            zero_value = val_b + ratio * (val_a - val_b)
            method = f"interpolated ({dt_b.strftime('%Y/%m/%d')}~{dt_a.strftime('%Y/%m/%d')}, ratio={ratio:.2f})"
        elif before:
            # 歸零日期在所有資料之後，用最後一筆
            zero_value = before[-1][1]
            method = f"last_available ({before[-1][0].strftime('%Y/%m/%d')})"
        elif after:
            # 歸零日期在所有資料之前，用第一筆
            zero_value = after[0][1]
            method = f"first_available ({after[0][0].strftime('%Y/%m/%d')})"

    # 歸零
    zeroed = []
    for dt, val in dated:
        zeroed.append((dt.strftime("%Y/%m/%d"), val - zero_value))

    info = {
        "zero_date": zero_date_str,
        "zero_value": zero_value,
        "method": method,
    }

    return zeroed, info


def save_timeseries_csv(timeseries, output_path, header=("日期", "累積變形量(mm)")):
    """將時間序列儲存為 CSV"""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for date_str, val in timeseries:
            writer.writerow([date_str, f"{val:.6f}"])


# ==============================================================================
# 批次處理設定：3 個 InSAR 站點的 GNSS 儀器座標 (TWD97/TM2)
# 座標來源：從各站 GNSS 數據檔的解算後 E/N 值取平均
# ==============================================================================

INSAR_DATA_DIR = r"D:\北科任務大檔案\114Ardswc_273150_2022to2023_3MT_InSAR"

BATCH_SITES = [
    {
        "site": "新竹縣-尖石鄉-D077(泰崗)",
        "shp": os.path.join(INSAR_DATA_DIR, "063_新竹縣-尖石鄉-D077", "defo_conv_policy066.shp"),
        "instruments": [
            {"name": "GP5(H1)",          "e": 279906.39, "n": 2723422.51},
            {"name": "GP6(H1)",          "e": 279655.77, "n": 2723301.44},
            {"name": "GP7(H1)",          "e": 280048.27, "n": 2723230.31},
            {"name": "GP8(H1)",          "e": 279856.10, "n": 2723040.95},
            {"name": "JS077-G2(TG02)",   "e": 279926.32, "n": 2723317.51},
            {"name": "JS077-G3(TG03)",   "e": 279696.67, "n": 2723168.01},
        ],
    },
    {
        "site": "新竹縣-尖石鄉-T001(秀巒)",
        "shp": os.path.join(INSAR_DATA_DIR, "066_新竹縣-尖石鄉-T001", "defo_conv_policy066.shp"),
        "instruments": [
            {"name": "G1(H4)",           "e": 278881.03, "n": 2718093.97},
            {"name": "G2(H4)",           "e": 279005.77, "n": 2720072.83},
            {"name": "GP3(H4)",          "e": 279059.62, "n": 2719507.90},
            {"name": "GP4(H4)",          "e": 279086.42, "n": 2719433.69},
            {"name": "JS077-G4(TG04)",   "e": 279536.26, "n": 2723118.40},
            {"name": "JS077-G5(TG05)",   "e": 279577.40, "n": 2722949.15},
            {"name": "JS077-G6(TG06)",   "e": 279435.05, "n": 2723138.48},
        ],
    },
    {
        "site": "花蓮縣-秀林鄉-D027(銅門)",
        "shp": os.path.join(INSAR_DATA_DIR, "260_花蓮縣-秀林鄉-D027", "defo_conv_policy260.shp"),
        "instruments": [
            {"name": "T23-G1(HG)",       "e": 299751.16, "n": 2650920.97},
            {"name": "T23-G2(HG)",       "e": 299957.69, "n": 2650678.17},
            {"name": "T23-G3(HG)",       "e": 299795.44, "n": 2650561.75},
            {"name": "T23-G4(HG)",       "e": 299663.19, "n": 2650691.60},
            {"name": "T24-G5(HG)",       "e": 299642.76, "n": 2650936.59},
        ],
    },
]

INSAR_OUTPUT_DIR = r"data\insar_extracted"
INSAR_ZEROED_DIR = r"data\insar_zeroed"


def run_batch(mode="nearest", radius=50, output_dir=INSAR_OUTPUT_DIR,
              zero_date=None, zeroed_dir=INSAR_ZEROED_DIR):
    """
    批次提取所有站點的 InSAR 時間序列

    Args:
        mode: "nearest", "average", 或 "both"
        radius: average 模式的搜尋半徑（公尺）
        output_dir: 提取結果輸出目錄
        zero_date: 歸零日期 (YYYY-MM-DD)，None 時不歸零
        zeroed_dir: 歸零結果輸出目錄
    """
    os.makedirs(output_dir, exist_ok=True)

    for site_config in BATCH_SITES:
        site_name = site_config["site"]
        shp_path = site_config["shp"]
        instruments = site_config["instruments"]

        print(f"\n{'='*60}")
        print(f"站點: {site_name}")
        print(f"{'='*60}")

        if not os.path.exists(shp_path):
            print(f"  錯誤: shapefile 不存在 — {shp_path}")
            continue

        for m in (["nearest", "average"] if mode == "both" else [mode]):
            results = extract_batch(shp_path, instruments, mode=m, radius=radius)

            # 儲存原始提取結果
            site_dir = os.path.join(output_dir, site_name, m)
            os.makedirs(site_dir, exist_ok=True)

            for inst, result in results:
                fname = f"{inst['name']}.csv"
                out_path = os.path.join(site_dir, fname)
                save_timeseries_csv(result["timeseries"], out_path)

            print(f"  -> {m} 提取已儲存 {len(results)} 個檔案至 {site_dir}")

            # 歸零處理
            if zero_date:
                zeroed_site_dir = os.path.join(zeroed_dir, site_name, m)
                os.makedirs(zeroed_site_dir, exist_ok=True)

                for inst, result in results:
                    ts = result["timeseries"]
                    zeroed_ts, info = zero_timeseries(ts, zero_date)
                    fname = f"{inst['name']}.csv"
                    out_path = os.path.join(zeroed_site_dir, fname)
                    save_timeseries_csv(
                        zeroed_ts, out_path,
                        header=("日期", "歸零後變形量(mm)"),
                    )

                print(f"  -> {m} 歸零已儲存 {len(results)} 個檔案至 {zeroed_site_dir}"
                      f" (基準: {zero_date}, {info['method']})")


def main():
    parser = argparse.ArgumentParser(
        description="從 InSAR defo_conv shapefile 提取時間序列",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  # 單一座標 (WGS84)
  python extract_insar.py single <shp> <lat> <lon> --mode nearest

  # 批次提取 3 個站點所有 GNSS 儀器
  python extract_insar.py batch --mode both --radius 100
        """
    )
    subparsers = parser.add_subparsers(dest="command")

    # single 子命令
    p_single = subparsers.add_parser("single", help="單一座標提取")
    p_single.add_argument("shp_path", help="defo_conv shapefile 路徑")
    p_single.add_argument("lat", type=float, help="WGS84 緯度")
    p_single.add_argument("lon", type=float, help="WGS84 經度")
    p_single.add_argument("--mode", choices=["nearest", "average"], default="nearest")
    p_single.add_argument("--radius", type=float, default=50)
    p_single.add_argument("-o", "--output", help="輸出 CSV 路徑")

    # batch 子命令
    p_batch = subparsers.add_parser("batch", help="批次提取 3 個站點")
    p_batch.add_argument("--mode", choices=["nearest", "average", "both"], default="both",
                         help="提取模式 (預設: both)")
    p_batch.add_argument("--radius", type=float, default=100,
                         help="average 模式的搜尋半徑，公尺 (預設: 100)")
    p_batch.add_argument("-o", "--output-dir", default=INSAR_OUTPUT_DIR,
                         help=f"輸出目錄 (預設: {INSAR_OUTPUT_DIR})")
    p_batch.add_argument("--zero-date", default=None,
                         help="歸零基準日期 YYYY-MM-DD (預設: 不歸零)")
    p_batch.add_argument("--zeroed-dir", default=INSAR_ZEROED_DIR,
                         help=f"歸零結果輸出目錄 (預設: {INSAR_ZEROED_DIR})")

    args = parser.parse_args()

    if args.command == "single":
        print(f"讀取 shapefile: {args.shp_path}")
        result = extract_single(
            args.shp_path, args.lat, args.lon,
            mode=args.mode, radius=args.radius,
        )
        tx, ty = result["target_twd97"]
        print(f"目標座標: WGS84({args.lat}, {args.lon}) -> TWD97({tx:.2f}, {ty:.2f})")
        print(f"模式: {result['mode']}, 匹配: {result['matched_count']} 點, "
              f"最近: {result['nearest_distance']:.1f}m\n")

        if args.output:
            save_timeseries_csv(result["timeseries"], args.output)
            print(f"已儲存: {args.output}")
        else:
            print(f"{'日期':<14} {'累積變形量(mm)':>16}")
            print("-" * 32)
            for date_str, val in result["timeseries"]:
                print(f"{date_str:<14} {val:>16.6f}")

    elif args.command == "batch":
        run_batch(mode=args.mode, radius=args.radius, output_dir=args.output_dir,
                  zero_date=args.zero_date, zeroed_dir=args.zeroed_dir)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
