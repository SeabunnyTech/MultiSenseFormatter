"""
InSAR vs GNSS LOS 比對工具

將 GNSS E/N/U 位移投影到衛星 LOS 方向，與 InSAR defo_simp（LOS 方向變形量）比對。
公式: d_LOS = -sin(θ)cos(φ)·dE + sin(θ)sin(φ)·dN + cos(θ)·dU

用法:
  # 批次模式
  python compare_insar_gnss.py --batch data/insar-batches/05_MT --gnss-source data/batches/08_監測數據-seperated

  # 舊模式（硬編碼站點）
  python compare_insar_gnss.py
"""

import argparse
import math
import os
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from extract_insar import (
    discover_batch_sites, extract_single_twd97, load_date_mappings,
    read_shapefile, zero_timeseries,
)

matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# 衛星參數
DEFAULT_INCIDENCE_DEG = 38.0
DEFAULT_HEADING_DEG = 350.0

# 舊模式預設值
LEGACY_ZERO_DATE = "2023-12-01"
LEGACY_SEPARATED_DIR = r"data\seperated"
LEGACY_INSAR_DATA_DIR = r"D:\北科任務大檔案\114Ardswc_273150_2022to2023_3MT_InSAR"
LEGACY_OUTPUT_DIR = r"data\insar_comparison"
LEGACY_FIELD_DATE_MAP = {
    "Field5":  "2022/01/23", "Field6":  "2022/03/20", "Field7":  "2022/04/03",
    "Field8":  "2022/09/18", "Field9":  "2022/10/16", "Field10": "2023/03/19",
    "Field11": "2023/04/02", "Field12": "2023/07/23", "Field13": "2023/09/17",
    "Field14": "2023/10/01", "Field15": "2024/03/31",
}
LEGACY_SITES = [
    {
        "site": "新竹縣-尖石鄉-D077(泰崗)",
        "shp": os.path.join(LEGACY_INSAR_DATA_DIR, "063_新竹縣-尖石鄉-D077", "defo_simp_policy066"),
        "instruments": [
            {"name": "GP5(H1)",        "e": 279906.39, "n": 2723422.51},
            {"name": "GP6(H1)",        "e": 279655.77, "n": 2723301.44},
            {"name": "GP7(H1)",        "e": 280048.27, "n": 2723230.31},
            {"name": "GP8(H1)",        "e": 279856.10, "n": 2723040.95},
            {"name": "JS077-G2(TG02)", "e": 279926.32, "n": 2723317.51},
            {"name": "JS077-G3(TG03)", "e": 279696.67, "n": 2723168.01},
        ],
    },
    {
        "site": "新竹縣-尖石鄉-T001(秀巒)",
        "shp": os.path.join(LEGACY_INSAR_DATA_DIR, "066_新竹縣-尖石鄉-T001", "defo_simp_policy066"),
        "instruments": [
            {"name": "JS077-G4(TG04)", "e": 279536.26, "n": 2723118.40},
            {"name": "JS077-G5(TG05)", "e": 279577.40, "n": 2722949.15},
            {"name": "JS077-G6(TG06)", "e": 279435.05, "n": 2723138.48},
        ],
    },
    {
        "site": "花蓮縣-秀林鄉-D027(銅門)",
        "shp": os.path.join(LEGACY_INSAR_DATA_DIR, "260_花蓮縣-秀林鄉-D027", "defo_simp_policy260"),
        "instruments": [
            {"name": "T23-G1(HG)", "e": 299751.16, "n": 2650920.97},
            {"name": "T23-G2(HG)", "e": 299957.69, "n": 2650678.17},
            {"name": "T23-G3(HG)", "e": 299795.44, "n": 2650561.75},
            {"name": "T23-G4(HG)", "e": 299663.19, "n": 2650691.60},
            {"name": "T24-G5(HG)", "e": 299642.76, "n": 2650936.59},
        ],
    },
]


def compute_los_vectors(incidence_deg, heading_deg):
    """計算 LOS 投影單位向量"""
    theta = math.radians(incidence_deg)
    phi = math.radians(heading_deg)
    return {
        "east":  -math.sin(theta) * math.cos(phi),
        "north":  math.sin(theta) * math.sin(phi),
        "up":     math.cos(theta),
    }


def _interpolate_zero(daily, e_col, n_col, h_col, zero_dt):
    """線性內插歸零基準值"""
    exact = daily[daily['date'] == zero_dt]
    if not exact.empty:
        return exact[e_col].iloc[0], exact[n_col].iloc[0], exact[h_col].iloc[0]

    before = daily[daily['date'] < zero_dt]
    after = daily[daily['date'] > zero_dt]

    if not before.empty and not after.empty:
        b, a = before.iloc[-1], after.iloc[0]
        total = (a['date'] - b['date']).days
        ratio = (zero_dt - b['date']).days / total if total > 0 else 0
        return tuple(b[c] + ratio * (a[c] - b[c]) for c in [e_col, n_col, h_col])
    elif not before.empty:
        r = before.iloc[-1]
        return r[e_col], r[n_col], r[h_col]
    else:
        r = after.iloc[0]
        return r[e_col], r[n_col], r[h_col]


def read_gnss_as_los(gnss_path, los_vec, zero_date):
    """讀取 GNSS 檔案 (csv 或 xlsx)，計算每日 LOS 位移"""
    if gnss_path.endswith('.csv'):
        df = pd.read_csv(gnss_path, low_memory=False)
    else:
        df = pd.read_excel(gnss_path)

    df.columns = [c.strip() for c in df.columns]

    time_col = next((c for c in df.columns if c == '系統時間'), df.columns[1])
    e_col = next((c for c in df.columns if c in ('解算後E值', 'E')), None)
    n_col = next((c for c in df.columns if c in ('解算後N值', 'N')), None)
    h_col = next((c for c in df.columns if c in ('解算後H值', 'H')), None)

    if not all([e_col, n_col, h_col]):
        raise ValueError(f"找不到 E/N/H 欄位: {list(df.columns)}")

    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=[time_col]).sort_values(time_col)
    for col in [e_col, n_col, h_col]:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['date'] = df[time_col].dt.date
    daily = df.drop_duplicates(subset=['date'], keep='last').copy()

    zero_dt = pd.to_datetime(zero_date).date()
    e0, n0, h0 = _interpolate_zero(daily, e_col, n_col, h_col, zero_dt)

    dE = (daily[e_col].values - e0) * 1000
    dN = (daily[n_col].values - n0) * 1000
    dU = (daily[h_col].values - h0) * 1000
    los_mm = los_vec["east"] * dE + los_vec["north"] * dN + los_vec["up"] * dU

    result = pd.DataFrame()
    result['date'] = pd.to_datetime(daily['date'].values)
    result['los_mm'] = los_mm
    return result


def extract_insar_los(shp_path, e, n, mode, radius, zero_date,
                      field_date_map=None, preloaded=None):
    """提取 InSAR LOS 時間序列並歸零"""
    result = extract_single_twd97(
        shp_path, e, n, mode=mode, radius=radius,
        field_date_map=field_date_map, _preloaded=preloaded,
    )
    zeroed_ts, info = zero_timeseries(result["timeseries"], zero_date)

    df = pd.DataFrame(zeroed_ts, columns=['date', 'defo_mm'])
    df['date'] = pd.to_datetime(df['date'])
    return df, result["matched_count"], result["nearest_distance"]


def match_insar_gnss(insar_df, gnss_df, max_days=3):
    """將 InSAR 日期與最近的 GNSS 日期配對"""
    pairs = []
    for _, row in insar_df.iterrows():
        idate = row["date"]
        nearby = gnss_df[
            (gnss_df["date"] >= idate - pd.Timedelta(days=max_days))
            & (gnss_df["date"] <= idate + pd.Timedelta(days=max_days))
        ]
        if not nearby.empty:
            idx = (nearby["date"] - idate).abs().argsort().iloc[0]
            gnss_val = nearby.iloc[idx]["los_mm"]
            pairs.append({
                "date": idate,
                "insar_mm": row["defo_mm"],
                "gnss_mm": gnss_val,
                "diff_mm": row["defo_mm"] - gnss_val,
            })
    return pd.DataFrame(pairs)


def plot_los_comparison(site_config, gnss_source_dir, output_dir, zero_date,
                        field_date_map=None,
                        incidence=DEFAULT_INCIDENCE_DEG,
                        heading=DEFAULT_HEADING_DEG, radius=45):
    """繪製單站所有儀器的 LOS 比對圖，並回傳統計結果"""
    site = site_config["site"]
    instruments = site_config["instruments"]
    shp = site_config["shp"]

    los_vec = compute_los_vectors(incidence, heading)
    print(f"  LOS 向量: E={los_vec['east']:.3f}, N={los_vec['north']:.3f}, U={los_vec['up']:.3f}")

    print(f"  載入 shapefile...")
    preloaded = read_shapefile(shp)

    n_inst = len(instruments)
    fig, axes = plt.subplots(n_inst, 1, figsize=(14, 4 * n_inst), sharex=True)
    if n_inst == 1:
        axes = [axes]

    zero_line_date = pd.to_datetime(zero_date)
    stats = []

    for ax, inst in zip(axes, instruments):
        name = inst["name"]
        e, n = inst["e"], inst["n"]

        # InSAR
        insar_n, cnt_n, dist_n = extract_insar_los(
            shp, e, n, "nearest", radius, zero_date,
            field_date_map=field_date_map, preloaded=preloaded)
        insar_a, cnt_a, _ = extract_insar_los(
            shp, e, n, "average", radius, zero_date,
            field_date_map=field_date_map, preloaded=preloaded)

        row = {"站點": site, "儀器": name, "距最近InSAR(m)": round(dist_n, 0),
               "avg點數": cnt_a, "歸零日期": zero_date}

        # GNSS LOS
        gnss_dir = os.path.join(gnss_source_dir, site, "GNSS地表變位")
        gnss_path = None
        for ext in ['.csv', '.xlsx']:
            p = os.path.join(gnss_dir, f"{name}{ext}")
            if os.path.exists(p):
                gnss_path = p
                break

        gnss_plotted = False
        if gnss_path:
            try:
                gnss = read_gnss_as_los(gnss_path, los_vec, zero_date)
                t_min = insar_n['date'].min() - pd.Timedelta(days=30)
                t_max = insar_n['date'].max() + pd.Timedelta(days=30)
                gnss_clip = gnss[(gnss['date'] >= t_min) & (gnss['date'] <= t_max)]

                if not gnss_clip.empty:
                    ax.plot(gnss_clip['date'], gnss_clip['los_mm'],
                            color='steelblue', linewidth=0.6, alpha=0.7, label='GNSS LOS')
                    gnss_plotted = True

                    # 統計
                    pairs = match_insar_gnss(insar_n, gnss)
                    if len(pairs) > 0:
                        rmse = np.sqrt(np.mean(pairs["diff_mm"] ** 2))
                        corr = pairs["insar_mm"].corr(pairs["gnss_mm"])
                        row["匹配點數"] = len(pairs)
                        row["RMSE(mm)"] = round(rmse, 1)
                        row["相關係數"] = round(corr, 3) if not np.isnan(corr) else "N/A"
                        print(f"    {name}: {len(pairs)}點匹配, RMSE={rmse:.1f}mm, r={corr:.3f}")
                    else:
                        row["匹配點數"] = 0
                        print(f"    {name}: 無時間重疊")
                else:
                    row["匹配點數"] = 0
                    print(f"    {name}: GNSS 與 InSAR 無時間重疊")
            except Exception as ex:
                print(f"    {name}: GNSS 讀取失敗 ({ex})")
        else:
            print(f"    {name}: 找不到 GNSS 檔案")

        # InSAR 點
        ax.scatter(insar_n['date'], insar_n['defo_mm'],
                   color='red', s=60, zorder=5, label='InSAR simp (nearest)')
        ax.scatter(insar_a['date'], insar_a['defo_mm'],
                   color='orange', s=60, marker='D', zorder=5,
                   label=f'InSAR simp (avg {radius}m)')

        ax.axvline(zero_line_date, color='gray', linestyle='--', alpha=0.5)
        ax.axhline(0, color='lightgray', linewidth=0.5)
        ax.set_ylabel('位移 (mm)')
        title = f'{name}  (距InSAR最近點 {dist_n:.0f}m, {radius}m內{cnt_a}點)'
        if "RMSE(mm)" in row:
            title += f'  RMSE={row["RMSE(mm)"]}mm'
        ax.set_title(title, fontsize=10, loc='left')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left', fontsize=8)

        stats.append(row)

    axes[-1].set_xlabel('日期')
    fig.suptitle(
        f'InSAR vs GNSS (LOS) — {site}\n'
        f'defo_simp  入射角={incidence}°  飛行方向={heading}°  歸零={zero_date}',
        fontsize=13, fontweight='bold',
    )
    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    safe_site = site.replace('(', '_').replace(')', '').replace(' ', '')
    out_path = os.path.join(output_dir, f"LOS_{safe_site}.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已儲存: {out_path}")

    return stats


def run_batch(batch_dir, gnss_source_dir, output_dir,
              incidence=DEFAULT_INCIDENCE_DEG, heading=DEFAULT_HEADING_DEG,
              radius=45):
    """批次比對所有站點"""
    import shapefile as shp_module

    # 載入日期對照表
    print("載入日期對照表...")
    fdms = load_date_mappings(batch_dir)

    # 發現站點
    print(f"\n掃描 InSAR 資料: {batch_dir}")
    sites = discover_batch_sites(batch_dir, gnss_source_dir)
    if not sites:
        print("無法發現有效的站點配置")
        sys.exit(1)

    all_stats = []

    for site_config in sites:
        shp_path = site_config["shp"]

        print(f"\n{'='*60}")
        print(f"站點: {site_config['site']}")
        print(f"{'='*60}")

        # 選擇日期對照表
        sf = shp_module.Reader(shp_path)
        fc = len([f[0] for f in sf.fields[1:] if f[0].strip().startswith('Field')])
        site_fdm = fdms.get(fc)
        if not site_fdm:
            for map_fc, fdm_candidate in sorted(fdms.items()):
                if map_fc >= fc:
                    site_fdm = {f"Field{5+i}": fdm_candidate[f"Field{5+i}"] for i in range(fc)}
                    break

        # 歸零日期 = InSAR 起始日
        zero_date = site_fdm["Field5"] if site_fdm else "2015/01/01"
        print(f"  歸零日期: {zero_date}")

        stats = plot_los_comparison(
            site_config, gnss_source_dir, output_dir, zero_date,
            field_date_map=site_fdm, incidence=incidence, heading=heading,
            radius=radius,
        )
        all_stats.extend(stats)

    # 儲存統計摘要
    if all_stats:
        df = pd.DataFrame(all_stats)
        summary_path = os.path.join(output_dir, "comparison_summary.csv")
        df.to_csv(summary_path, index=False, encoding="utf-8-sig")
        print(f"\n統計摘要已儲存: {summary_path}")


def main():
    parser = argparse.ArgumentParser(
        description="InSAR vs GNSS LOS 比對工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python compare_insar_gnss.py --batch data/insar-batches/05_MT --gnss-source data/batches/08_監測數據-seperated
  python compare_insar_gnss.py   # 舊模式（硬編碼站點）
        """
    )
    parser.add_argument("--batch", "-b", type=str, metavar="PATH",
                        help="InSAR 批次資料夾")
    parser.add_argument("--gnss-source", type=str, metavar="PATH",
                        help="GNSS 分類後資料夾")
    parser.add_argument("--incidence", type=float, default=DEFAULT_INCIDENCE_DEG,
                        help=f"入射角 (預設: {DEFAULT_INCIDENCE_DEG}°)")
    parser.add_argument("--heading", type=float, default=DEFAULT_HEADING_DEG,
                        help=f"飛行方向角 (預設: {DEFAULT_HEADING_DEG}°)")
    parser.add_argument("--radius", type=float, default=45,
                        help="average 模式搜尋半徑 (預設: 45m)")
    parser.add_argument("-o", "--output-dir", default=None,
                        help="輸出目錄 (預設: {batch}-comparison)")

    args = parser.parse_args()

    if args.batch:
        if not args.gnss_source:
            print("錯誤: --batch 模式需要指定 --gnss-source")
            sys.exit(1)

        batch_path = args.batch.rstrip('/\\')
        output_dir = args.output_dir or (batch_path + '-comparison')

        run_batch(batch_path, args.gnss_source, output_dir,
                  incidence=args.incidence, heading=args.heading,
                  radius=args.radius)
    else:
        # 舊模式
        print("InSAR vs GNSS LOS 比對（舊模式）")
        print(f"歸零基準日: {LEGACY_ZERO_DATE}\n")

        for site_config in LEGACY_SITES:
            print(f"{'='*60}")
            print(f"站點: {site_config['site']}")
            print(f"{'='*60}")
            plot_los_comparison(
                site_config, LEGACY_SEPARATED_DIR, LEGACY_OUTPUT_DIR,
                LEGACY_ZERO_DATE, field_date_map=LEGACY_FIELD_DATE_MAP,
            )
            print()


if __name__ == "__main__":
    main()
