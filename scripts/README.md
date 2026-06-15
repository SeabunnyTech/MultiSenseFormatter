# 輔助腳本

這些腳本不屬於核心處理流程，提供額外的分析與繪圖功能。

## InSAR 相關

| 腳本 | 用途 |
|------|------|
| `extract_insar.py` | 從 InSAR shapefile 提取時間序列，匹配最近 GNSS 站點 |
| `compare_insar_gnss.py` | InSAR vs GNSS LOS 方向位移比對圖 |
| `analyze_comparison.py` | InSAR/GNSS 比對的量化分析（RMSE、相關係數等） |

## 繪圖

| 腳本 | 用途 |
|------|------|
| `plot_inclinometer.py` | 傾斜計剖面圖繪製 |
| `plot_inclinometer.bat` | Windows 批次執行 |
