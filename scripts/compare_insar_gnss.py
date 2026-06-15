"""
InSAR vs GNSS LOS 比對工具

將 GNSS E/N/U 位移投影到衛星 LOS 方向，與 InSAR defo_raw（LOS 方向變形量）比對。
公式: d_LOS = -sin(θ)cos(φ)·dE + sin(θ)sin(φ)·dN + cos(θ)·dU
"""

import math
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from extract_insar import (
    FIELD_DATE_MAP, extract_single_twd97, read_shapefile, zero_timeseries,
)

matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

ZERO_DATE = "2023-12-01"
SEPARATED_DIR = r"data\seperated"
INSAR_DATA_DIR = r"D:\北科任務大檔案\114Ardswc_273150_2022to2023_3MT_InSAR"
OUTPUT_DIR = r"data\insar_comparison"

# 衛星參數（ALOS-2 升軌，從 aux 輔助圖確認）
# 入射角取典型值，可依實際資料調整
DEFAULT_INCIDENCE_DEG = 38.0
DEFAULT_HEADING_DEG = 350.0  # 升軌飛行方向角

# 比對設定
COMPARE_SITES = [
    {
        "site": "新竹縣-尖石鄉-D077(泰崗)",
        "shp": os.path.join(INSAR_DATA_DIR, "063_新竹縣-尖石鄉-D077", "defo_simp_policy066"),
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
        "shp": os.path.join(INSAR_DATA_DIR, "066_新竹縣-尖石鄉-T001", "defo_simp_policy066"),
        "instruments": [
            {"name": "JS077-G4(TG04)", "e": 279536.26, "n": 2723118.40},
            {"name": "JS077-G5(TG05)", "e": 279577.40, "n": 2722949.15},
            {"name": "JS077-G6(TG06)", "e": 279435.05, "n": 2723138.48},
        ],
    },
    {
        "site": "花蓮縣-秀林鄉-D027(銅門)",
        "shp": os.path.join(INSAR_DATA_DIR, "260_花蓮縣-秀林鄉-D027", "defo_simp_policy260"),
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


def read_gnss_as_los(site, instrument, los_vec):
    """讀取原始 GNSS，計算每日 LOS 位移（以 ZERO_DATE 為基準歸零）"""
    path = os.path.join(SEPARATED_DIR, site, "GNSS地表變位", f"{instrument}.xlsx")
    df = pd.read_excel(path)

    time_col = df.columns[1]
    e_col = df.columns[2]
    n_col = df.columns[3]
    h_col = df.columns[4]

    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df = df.dropna(subset=[time_col]).sort_values(time_col)
    for col in [e_col, n_col, h_col]:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['date'] = df[time_col].dt.date
    daily = df.drop_duplicates(subset=['date'], keep='last').copy()

    # 找歸零基準值
    zero_dt = pd.to_datetime(ZERO_DATE).date()
    e0, n0, h0 = _interpolate_zero(daily, e_col, n_col, h_col, zero_dt)

    # 位移 (m → mm) 並投影到 LOS
    dE = (daily[e_col].values - e0) * 1000
    dN = (daily[n_col].values - n0) * 1000
    dU = (daily[h_col].values - h0) * 1000

    los_mm = los_vec["east"] * dE + los_vec["north"] * dN + los_vec["up"] * dU

    result = pd.DataFrame()
    result['date'] = pd.to_datetime(daily['date'].values)
    result['los_mm'] = los_mm
    return result


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
        return tuple(
            b[c] + ratio * (a[c] - b[c]) for c in [e_col, n_col, h_col]
        )
    elif not before.empty:
        r = before.iloc[-1]
        return r[e_col], r[n_col], r[h_col]
    else:
        r = after.iloc[0]
        return r[e_col], r[n_col], r[h_col]


def extract_insar_los(shp_path, e, n, mode, radius, preloaded=None):
    """提取 InSAR LOS 時間序列並歸零"""
    result = extract_single_twd97(
        shp_path, e, n, mode=mode, radius=radius, _preloaded=preloaded,
    )
    zeroed_ts, info = zero_timeseries(result["timeseries"], ZERO_DATE)

    df = pd.DataFrame(zeroed_ts, columns=['date', 'defo_mm'])
    df['date'] = pd.to_datetime(df['date'])
    return df, result["matched_count"], result["nearest_distance"]


def plot_los_comparison(site_config, output_dir=OUTPUT_DIR,
                        incidence=DEFAULT_INCIDENCE_DEG,
                        heading=DEFAULT_HEADING_DEG):
    """繪製單站所有儀器的 LOS 比對圖"""
    site = site_config["site"]
    instruments = site_config["instruments"]

    los_vec = compute_los_vectors(incidence, heading)
    print(f"  LOS 向量: E={los_vec['east']:.3f}, N={los_vec['north']:.3f}, U={los_vec['up']:.3f}")
    print(f"  (入射角={incidence}°, 飛行方向={heading}°)")

    # 預載 shapefile
    shp = site_config["shp"]
    print(f"  載入 defo_simp...")
    preloaded = read_shapefile(shp)

    radius = 45
    n_inst = len(instruments)
    fig, axes = plt.subplots(n_inst, 1, figsize=(14, 4 * n_inst), sharex=True)
    if n_inst == 1:
        axes = [axes]

    zero_line_date = pd.to_datetime(ZERO_DATE)

    for ax, inst in zip(axes, instruments):
        name = inst["name"]
        e, n = inst["e"], inst["n"]

        # InSAR — defo_simp
        insar_n, cnt_n, dist_n = extract_insar_los(
            shp, e, n, "nearest", radius, preloaded=preloaded)
        insar_a, cnt_a, _ = extract_insar_los(
            shp, e, n, "average", radius, preloaded=preloaded)

        # GNSS LOS
        try:
            gnss = read_gnss_as_los(site, name, los_vec)
            # 裁切到 InSAR 範圍
            t_min = insar_n['date'].min() - pd.Timedelta(days=30)
            t_max = insar_n['date'].max() + pd.Timedelta(days=30)
            gnss_clip = gnss[(gnss['date'] >= t_min) & (gnss['date'] <= t_max)]
            ax.plot(gnss_clip['date'], gnss_clip['los_mm'],
                    color='steelblue', linewidth=0.6, alpha=0.7, label='GNSS LOS')
        except Exception as ex:
            print(f"    {name}: GNSS 讀取失敗 ({ex})")

        # InSAR 點
        ax.scatter(insar_n['date'], insar_n['defo_mm'],
                   color='red', s=60, zorder=5, label='InSAR simp (nearest)')
        ax.scatter(insar_a['date'], insar_a['defo_mm'],
                   color='orange', s=60, marker='D', zorder=5,
                   label=f'InSAR simp (avg {radius}m)')

        ax.axvline(zero_line_date, color='gray', linestyle='--', alpha=0.5)
        ax.axhline(0, color='lightgray', linewidth=0.5)
        ax.set_ylabel('位移 (mm)')
        ax.set_title(f'{name}  (距InSAR最近點 {dist_n:.0f}m, {radius}m內{cnt_a}點)',
                     fontsize=10, loc='left')
        ax.grid(True, alpha=0.3)
        ax.legend(loc='upper left', fontsize=8)

    axes[-1].set_xlabel('日期')
    fig.suptitle(
        f'InSAR vs GNSS (LOS) — {site}\n'
        f'defo_simp  入射角={incidence}°  飛行方向={heading}°  歸零={ZERO_DATE}',
        fontsize=13, fontweight='bold',
    )
    plt.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    safe_site = site.split('(')[0]
    out_path = os.path.join(output_dir, f"LOS_{safe_site}.png")
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  已儲存: {out_path}")


def main():
    print("InSAR vs GNSS LOS 比對")
    print(f"歸零基準日: {ZERO_DATE}\n")

    for site_config in COMPARE_SITES:
        print(f"{'='*60}")
        print(f"站點: {site_config['site']}")
        print(f"{'='*60}")
        plot_los_comparison(site_config)
        print()


if __name__ == "__main__":
    main()
