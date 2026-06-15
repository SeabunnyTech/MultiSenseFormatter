"""
傾斜儀剖面圖繪製工具
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# 設定中文字體
matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

def parse_depth_profile(depth_str):
    """
    解析深度剖面字串
    格式: "深度1 A值1 B值1 深度2 A值2 B值2 ..."
    返回: depths, a_values, b_values
    """
    parts = str(depth_str).split()
    depths = []
    a_values = []
    b_values = []

    i = 0
    while i < len(parts) - 2:
        try:
            depth = float(parts[i])
            a_val = float(parts[i + 1])
            b_val = float(parts[i + 2])
            depths.append(depth)
            a_values.append(a_val)
            b_values.append(b_val)
            i += 3
        except (ValueError, IndexError):
            break

    return np.array(depths), np.array(a_values), np.array(b_values)


def plot_inclinometer(file_path, output_path=None):
    """
    繪製傾斜儀剖面圖
    """
    # 讀取資料
    df = pd.read_excel(file_path)

    # 取得欄位名稱（處理編碼問題）
    cols = df.columns.tolist()
    time_col = cols[1]  # 系統時間
    depth_col = cols[2]  # 深度（含剖面資料）

    # 建立圖表
    fig, axes = plt.subplots(1, 2, figsize=(12, 10), sharey=True)

    # 顏色映射
    colors = plt.cm.viridis(np.linspace(0, 0.8, len(df)))

    for idx, row in df.iterrows():
        # 解析深度剖面
        depths, a_vals, b_vals = parse_depth_profile(row[depth_col])

        # 取得日期標籤
        date_label = str(row[time_col])[:10]

        # 繪製 A 軸
        axes[0].plot(a_vals, depths, '-', color=colors[idx],
                     linewidth=1.5, label=date_label)

        # 繪製 B 軸
        axes[1].plot(b_vals, depths, '-', color=colors[idx],
                     linewidth=1.5, label=date_label)

    # 設定 A 軸子圖
    axes[0].set_xlabel('A 軸位移量 (mm)', fontsize=12)
    axes[0].set_ylabel('深度 (m)', fontsize=12)
    axes[0].set_title('A 軸方向', fontsize=14)
    axes[0].invert_yaxis()  # 深度向下遞增
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(loc='lower left', fontsize=9)
    axes[0].axvline(x=0, color='gray', linestyle='--', alpha=0.5)

    # 設定 B 軸子圖
    axes[1].set_xlabel('B 軸位移量 (mm)', fontsize=12)
    axes[1].set_title('B 軸方向', fontsize=14)
    axes[1].invert_yaxis()
    axes[1].grid(True, alpha=0.3)
    axes[1].legend(loc='lower left', fontsize=9)
    axes[1].axvline(x=0, color='gray', linestyle='--', alpha=0.5)

    # 主標題
    instrument_name = df.iloc[0, 0]
    fig.suptitle(f'傾斜儀剖面圖 - {instrument_name}', fontsize=16, fontweight='bold')

    plt.tight_layout()

    # 儲存或顯示
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'圖表已儲存至: {output_path}')
    else:
        plt.show()

    return fig


def plot_combined_vector(file_path, output_path=None):
    """
    繪製合成位移向量圖（A軸和B軸合成）
    """
    df = pd.read_excel(file_path)
    cols = df.columns.tolist()
    depth_col = cols[2]

    fig, ax = plt.subplots(figsize=(8, 10))
    colors = plt.cm.viridis(np.linspace(0, 0.8, len(df)))

    for idx, row in df.iterrows():
        depths, a_vals, b_vals = parse_depth_profile(row[depth_col])

        # 計算合成位移量
        combined = np.sqrt(a_vals**2 + b_vals**2)

        date_label = str(row[cols[1]])[:10]
        ax.plot(combined, depths, '-', color=colors[idx],
                linewidth=1.5, label=date_label)

    ax.set_xlabel('合成位移量 (mm)', fontsize=12)
    ax.set_ylabel('深度 (m)', fontsize=12)
    ax.set_title(f'傾斜儀合成位移剖面圖 - {df.iloc[0, 0]}', fontsize=14, fontweight='bold')
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3)
    ax.legend(loc='lower left')

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f'圖表已儲存至: {output_path}')
    else:
        plt.show()

    return fig


if __name__ == '__main__':
    # 範例使用
    file_path = r'data/seperated/花蓮縣-秀林鄉-D027(銅門)/傾斜儀/T22-BH1(DS188_H1).xlsx'

    # 繪製 A/B 軸分開的剖面圖
    plot_inclinometer(file_path, 'inclinometer_profile.png')

    # 繪製合成位移圖
    plot_combined_vector(file_path, 'inclinometer_combined.png')
