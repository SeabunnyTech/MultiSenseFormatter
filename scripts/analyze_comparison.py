"""InSAR vs GNSS LOS 定量比對分析"""
import math
import os

import numpy as np
import pandas as pd

from extract_insar import (
    FIELD_DATE_MAP, extract_single_twd97, read_shapefile, zero_timeseries,
)

ZERO_DATE = "2023-12-01"
INSAR_DATA_DIR = r"D:\北科任務大檔案\114Ardswc_273150_2022to2023_3MT_InSAR"
SEPARATED_DIR = r"data\seperated"

theta = math.radians(38.0)
phi = math.radians(350.0)
LOS_VEC = {
    "east": -math.sin(theta) * math.cos(phi),
    "north": math.sin(theta) * math.sin(phi),
    "up": math.cos(theta),
}

SITES = [
    {
        "site": "新竹縣-尖石鄉-D077(泰崗)",
        "shp_raw": os.path.join(INSAR_DATA_DIR, "063_新竹縣-尖石鄉-D077", "defo_raw_policy066"),
        "shp_conv": os.path.join(INSAR_DATA_DIR, "063_新竹縣-尖石鄉-D077", "defo_conv_policy066"),
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
        "shp_raw": os.path.join(INSAR_DATA_DIR, "066_新竹縣-尖石鄉-T001", "defo_raw_policy066"),
        "shp_conv": os.path.join(INSAR_DATA_DIR, "066_新竹縣-尖石鄉-T001", "defo_conv_policy066"),
        "instruments": [
            {"name": "JS077-G4(TG04)", "e": 279536.26, "n": 2723118.40},
            {"name": "JS077-G5(TG05)", "e": 279577.40, "n": 2722949.15},
            {"name": "JS077-G6(TG06)", "e": 279435.05, "n": 2723138.48},
        ],
    },
    {
        "site": "花蓮縣-秀林鄉-D027(銅門)",
        "shp_raw": os.path.join(INSAR_DATA_DIR, "260_花蓮縣-秀林鄉-D027", "defo_raw_policy260"),
        "shp_conv": os.path.join(INSAR_DATA_DIR, "260_花蓮縣-秀林鄉-D027", "defo_conv_policy260"),
        "instruments": [
            {"name": "T23-G1(HG)", "e": 299751.16, "n": 2650920.97},
            {"name": "T23-G2(HG)", "e": 299957.69, "n": 2650678.17},
            {"name": "T23-G3(HG)", "e": 299795.44, "n": 2650561.75},
            {"name": "T23-G4(HG)", "e": 299663.19, "n": 2650691.60},
        ],
    },
]


def read_gnss_los(site, instrument):
    path = os.path.join(SEPARATED_DIR, site, "GNSS地表變位", f"{instrument}.xlsx")
    df = pd.read_excel(path)
    tc, ec, nc, hc = df.columns[1], df.columns[2], df.columns[3], df.columns[4]
    df[tc] = pd.to_datetime(df[tc], errors="coerce")
    df = df.dropna(subset=[tc]).sort_values(tc)
    for c in [ec, nc, hc]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = df[tc].dt.date
    daily = df.drop_duplicates(subset=["date"], keep="last").copy()

    zero_dt = pd.to_datetime(ZERO_DATE).date()
    exact = daily[daily["date"] == zero_dt]
    if not exact.empty:
        e0, n0, h0 = exact[ec].iloc[0], exact[nc].iloc[0], exact[hc].iloc[0]
    else:
        before = daily[daily["date"] < zero_dt]
        after = daily[daily["date"] > zero_dt]
        if not before.empty and not after.empty:
            b, a = before.iloc[-1], after.iloc[0]
            total = (a["date"] - b["date"]).days
            ratio = (zero_dt - b["date"]).days / total if total > 0 else 0
            e0 = b[ec] + ratio * (a[ec] - b[ec])
            n0 = b[nc] + ratio * (a[nc] - b[nc])
            h0 = b[hc] + ratio * (a[hc] - b[hc])
        elif not before.empty:
            e0, n0, h0 = before.iloc[-1][ec], before.iloc[-1][nc], before.iloc[-1][hc]
        else:
            e0, n0, h0 = after.iloc[0][ec], after.iloc[0][nc], after.iloc[0][hc]

    dE = (daily[ec].values - e0) * 1000
    dN = (daily[nc].values - n0) * 1000
    dU = (daily[hc].values - h0) * 1000
    los_mm = LOS_VEC["east"] * dE + LOS_VEC["north"] * dN + LOS_VEC["up"] * dU

    result = pd.DataFrame()
    result["date"] = pd.to_datetime(daily["date"].values)
    result["los_mm"] = los_mm
    return result


def get_insar_ts(shp_path, e, n, mode, radius, preloaded):
    result = extract_single_twd97(shp_path, e, n, mode=mode, radius=radius, _preloaded=preloaded)
    zeroed_ts, info = zero_timeseries(result["timeseries"], ZERO_DATE)
    df = pd.DataFrame(zeroed_ts, columns=["date", "defo_mm"])
    df["date"] = pd.to_datetime(df["date"])
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


def main():
    all_results = []

    for sc in SITES:
        site = sc["site"]
        print(f"\n{'=' * 70}")
        print(f"站點: {site}")
        print(f"{'=' * 70}")

        preloaded_raw = read_shapefile(sc["shp_raw"])
        preloaded_conv = read_shapefile(sc["shp_conv"])
        print(f"  InSAR 點數: raw={len(preloaded_raw[0])}, conv={len(preloaded_conv[0])}")

        for inst in sc["instruments"]:
            name = inst["name"]
            e, n = inst["e"], inst["n"]

            insar_raw_n, cnt_n, dist_n = get_insar_ts(
                sc["shp_raw"], e, n, "nearest", 100, preloaded_raw)
            insar_raw_a, cnt_a, _ = get_insar_ts(
                sc["shp_raw"], e, n, "average", 100, preloaded_raw)
            insar_conv_a, cnt_c, _ = get_insar_ts(
                sc["shp_conv"], e, n, "average", 100, preloaded_conv)

            row = {
                "站點": site,
                "儀器": name,
                "距最近InSAR(m)": round(dist_n, 0),
                "avg點數(raw)": cnt_a,
                "avg點數(conv)": cnt_c,
                "InSAR_raw_nearest_range": f"{insar_raw_n['defo_mm'].min():.1f}~{insar_raw_n['defo_mm'].max():.1f}",
                "InSAR_raw_avg_range": f"{insar_raw_a['defo_mm'].min():.1f}~{insar_raw_a['defo_mm'].max():.1f}",
                "InSAR_conv_avg_range": f"{insar_conv_a['defo_mm'].min():.1f}~{insar_conv_a['defo_mm'].max():.1f}",
            }

            print(f"\n  {name}: 距最近InSAR={dist_n:.0f}m, avg點數(raw/conv)={cnt_a}/{cnt_c}")

            # GNSS
            try:
                gnss = read_gnss_los(site, name)
                gnss_min = gnss["date"].min()
                gnss_max = gnss["date"].max()
                insar_min = insar_raw_n["date"].min()
                insar_max = insar_raw_n["date"].max()

                overlap_start = max(gnss_min, insar_min)
                overlap_end = min(gnss_max, insar_max)

                row["GNSS日期範圍"] = f"{gnss_min.date()}~{gnss_max.date()}"

                if overlap_start < overlap_end:
                    row["重疊期間"] = f"{overlap_start.date()}~{overlap_end.date()}"
                    gnss_clip = gnss[(gnss["date"] >= insar_min) & (gnss["date"] <= insar_max)]
                    row["GNSS_LOS_std(mm)"] = round(gnss_clip["los_mm"].std(), 1)

                    print(f"    GNSS: {gnss_min.date()}~{gnss_max.date()}, "
                          f"重疊: {overlap_start.date()}~{overlap_end.date()}")
                    print(f"    GNSS LOS std={gnss_clip['los_mm'].std():.1f}mm")

                    for label, idf in [("raw_nearest", insar_raw_n), ("raw_avg", insar_raw_a),
                                        ("conv_avg", insar_conv_a)]:
                        pairs = match_insar_gnss(idf, gnss)
                        if len(pairs) > 0:
                            rmse = np.sqrt(np.mean(pairs["diff_mm"] ** 2))
                            mean_diff = pairs["diff_mm"].mean()
                            corr = pairs["insar_mm"].corr(pairs["gnss_mm"])
                            row[f"RMSE_{label}(mm)"] = round(rmse, 1)
                            row[f"MeanDiff_{label}(mm)"] = round(mean_diff, 1)
                            row[f"Corr_{label}"] = round(corr, 3) if not np.isnan(corr) else "N/A"
                            row[f"匹配點數_{label}"] = len(pairs)
                            print(f"    {label}: 匹配{len(pairs)}點, "
                                  f"RMSE={rmse:.1f}mm, 平均差={mean_diff:.1f}mm, r={corr:.3f}")
                        else:
                            print(f"    {label}: 無匹配點")
                else:
                    row["重疊期間"] = "無"
                    print(f"    GNSS: {gnss_min.date()}~{gnss_max.date()} — 無時間重疊")
            except Exception as ex:
                row["GNSS日期範圍"] = f"讀取失敗: {ex}"
                print(f"    GNSS: 讀取失敗 ({ex})")

            all_results.append(row)

    # Save summary CSV
    df = pd.DataFrame(all_results)
    os.makedirs("data/insar_comparison", exist_ok=True)
    df.to_csv("data/insar_comparison/comparison_summary.csv", index=False, encoding="utf-8-sig")
    print(f"\n\n摘要已儲存: data/insar_comparison/comparison_summary.csv")


if __name__ == "__main__":
    main()
