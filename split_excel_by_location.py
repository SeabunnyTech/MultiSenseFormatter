#!/usr/bin/env python3
"""
數據資料檔拆分腳本
功能:
1. 從指定資料夾讀取以地名開頭的數據資料檔
2. 根據儀器編號檔案查找對應的儀器類型
3. 將數據檔的每個分頁拆分成獨立的 xlsx 檔案
4. 按照「地名/儀器類型」的目錄結構儲存
"""

import os
import re
import sys
import pandas as pd


def load_instrument_mapping(instrument_file):
    """
    載入儀器編號檔案,建立儀器編號到儀器類型的映射
    
    Args:
        instrument_file: 儀器編號檔案路徑
    
    Returns:
        dict: {地名: {儀器編號: 儀器類型}}
    """
    print(f"正在載入儀器編號檔案: {instrument_file}")
    
    xls = pd.ExcelFile(instrument_file)
    mapping = {}
    
    for sheet_name in xls.sheet_names:
        # 從分頁名稱提取地名 (例如: "新竹縣-尖石鄉-T001(DS194)" -> "新竹縣-尖石鄉")
        # 處理可能的前導空白字符
        clean_sheet_name = sheet_name.strip().lstrip('_x0009_').strip()
        
        # 提取地名部分
        match = re.match(r'^(.*?-.*?)-', clean_sheet_name)
        if match:
            location = match.group(1)
        else:
            # 如果格式不符,使用整個名稱
            location = clean_sheet_name.split('-')[0] + '-' + clean_sheet_name.split('-')[1] if '-' in clean_sheet_name else clean_sheet_name
        
        # 讀取該分頁的儀器資料
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        if location not in mapping:
            mapping[location] = {}
        
        # 建立儀器編號到儀器類型的映射
        for _, row in df.iterrows():
            instrument_code = str(row['儀器編號']).strip()
            instrument_type = str(row['儀器類型']).strip()
            mapping[location][instrument_code] = instrument_type
    
    print(f"已載入 {len(mapping)} 個地點的儀器資料")
    return mapping


def infer_instrument_type_from_columns(columns):
    """
    根據 CSV 欄位名稱推斷儀器類型

    Args:
        columns: 欄位名稱列表

    Returns:
        str: 推斷的儀器類型，找不到則返回 "未分類"
    """
    # 先去除欄名前後空白，避免「水位高 」「深度 」等尾隨空白造成誤判
    columns = [str(c).strip() for c in columns]
    col_str = ','.join(columns)

    if '解算後E值' in col_str:
        return 'GNSS地表變位'
    # 單頻GPS：欄位為 E/N/H（無「解算後」前綴），併入 GNSS 一併處理
    if 'E' in columns and 'N' in columns and 'H' in columns:
        return 'GNSS地表變位'
    if '方位一觀測值' in col_str and '方位二觀測值' in col_str:
        return '地表傾斜計(雙軸)'
    if '伸張量' in col_str:
        return '地表伸縮計'
    if '累積雨量' in col_str:
        return '雨量計'
    # 時域反射儀（TDR）：深度剖面字串，無對應歸零處理器，單獨歸類另案處理
    if '深度' in col_str and '變位量' in col_str:
        return '時域反射儀'
    if '水位高' in col_str:
        return '水位觀測井'
    if '傾斜量' in col_str:
        return '傾斜儀'
    if '地表伸縮' in col_str:
        return '地表伸縮計'

    return '未分類'


def process_csv_folder(folder_path, instrument_mapping, output_dir):
    """
    處理包含 CSV 檔案的資料夾，分類儲存

    優先使用儀器編號對照表，fallback 到欄位推斷。

    Args:
        folder_path: CSV 資料夾路徑
        instrument_mapping: 儀器編號映射
        output_dir: 輸出目錄
    """
    folder_name = os.path.basename(folder_path)
    print(f"\n正在處理 CSV 資料夾: {folder_name}")

    csv_files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    if not csv_files:
        print(f"  資料夾中沒有 CSV 檔案，跳過")
        return

    print(f"  共有 {len(csv_files)} 個 CSV 檔案")

    # 取得該地點的儀器映射
    match = re.match(r'^(.*?-.*?)-', folder_name)
    if match:
        instrument_mapping_key = match.group(1)
    else:
        instrument_mapping_key = folder_name
    location_mapping = instrument_mapping.get(instrument_mapping_key, {})

    location_dir = os.path.join(output_dir, folder_name)
    os.makedirs(location_dir, exist_ok=True)

    for csv_file in csv_files:
        csv_path = os.path.join(folder_path, csv_file)
        print(f"  處理: {csv_file}")

        df = pd.read_csv(csv_path)

        # 新 CSV 格式：每檔一支儀器、表頭可靠，故以「欄位表頭推斷」為主要分類依據。
        # 僅當表頭無法辨識時，才回退到儀器編號對照表（避免與同鄉鎮 MT 站編號互相污染）。
        csv_name = os.path.splitext(csv_file)[0]
        inferred = infer_instrument_type_from_columns(list(df.columns))
        if inferred != '未分類':
            instrument_types = [inferred]
        else:
            instrument_types = find_instrument_type(csv_name, location_mapping, columns=list(df.columns))

        for instrument_type in instrument_types:
            print(f"    儀器類型: {instrument_type}")

            # 建立儀器類型目錄
            type_dir = os.path.join(location_dir, instrument_type)
            os.makedirs(type_dir, exist_ok=True)

            # 輸出檔名：維持 CSV 格式
            safe_name = re.sub(r'[<>:"/\\|?*]', '_', csv_name)
            output_file = os.path.join(type_dir, f"{safe_name}.csv")

            df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"    已儲存: {output_file}")


def extract_instrument_code(sheet_name):
    """
    從分頁名稱提取儀器編號
    
    例如:
    - "JS077-R(TG02)" -> "R1" 或 "R" (根據實際對應)
    - "GP7(H1)" -> "GP7"
    - "T5(H6)" -> "T5"
    
    Args:
        sheet_name: 分頁名稱
    
    Returns:
        list: 可能的儀器編號列表
    """
    # 移除括號及其內容
    clean_name = re.sub(r'\([^)]*\)', '', sheet_name).strip()
    
    # 移除前綴 (例如 JS077-)
    clean_name = re.sub(r'^[A-Z]+\d+-', '', clean_name)
    
    # 產生可能的儀器編號
    possible_codes = [clean_name]
    
    # 如果是單字母,也嘗試加上數字
    if len(clean_name) == 1:
        possible_codes.extend([f"{clean_name}1", f"{clean_name}2", f"{clean_name}3"])
    
    # 如果有完整的儀器編號格式,也加入原始名稱
    possible_codes.append(sheet_name.split('(')[0].strip())
    
    return possible_codes


def find_instrument_type(sheet_name, location_mapping, columns=None):
    """
    根據分頁名稱查找對應的儀器類型

    優先使用儀器編號對照表匹配，若匹配失敗則 fallback 到欄位推斷。

    Args:
        sheet_name: 分頁名稱
        location_mapping: 該地點的儀器編號映射 dict
        columns: 該分頁的欄位名稱列表（用於 fallback 推斷）

    Returns:
        list: 可能的儀器類型列表,如果找不到則返回 ["未分類"]
    """
    possible_codes = extract_instrument_code(sheet_name)
    matched_types = []

    # Helper to standardize instrument types
    def standardize_type(itype):
        if itype in ['單頻GPS位移', 'GNSS地表變位']:
            return 'GNSS地表變位'
        return itype

    # 1. 嘗試完全匹配
    for code in possible_codes:
        if code in location_mapping:
            matched_types.append(standardize_type(location_mapping[code]))

    # 2. 嘗試前綴匹配 (例如 JS077-G3 匹配 JS077-G4, JS077-G5)
    original_name = sheet_name.split('(')[0].strip()
    # 提取前綴和數字 (例如 JS077-G3 -> prefix=JS077-G, number=3)
    prefix_match = re.match(r'^(.*?)(\d+)$', original_name.replace('-', ''))
    if prefix_match:
        prefix = prefix_match.group(1)
        for key in location_mapping.keys():
            if key.replace('-', '').startswith(prefix):
                matched_types.append(standardize_type(location_mapping[key]))

    # 3. 嘗試模糊匹配
    for code in possible_codes:
        for key in location_mapping.keys():
            if code.upper() in key.upper() or key.upper() in code.upper():
                matched_types.append(standardize_type(location_mapping[key]))

    # Remove duplicates and return
    if matched_types:
        return list(set(matched_types))

    # 4. Fallback: 根據欄位名稱推斷
    if columns is not None:
        inferred = infer_instrument_type_from_columns(columns)
        if inferred != '未分類':
            print(f"  提示: 透過欄位推斷分頁 '{sheet_name}' 的儀器類型為 '{inferred}'")
            return [inferred]

    print(f"  警告: 無法找到分頁 '{sheet_name}' 的儀器類型,將歸類為 '未分類'")
    print(f"  嘗試過的編號: {possible_codes}")
    return ["未分類"]


def process_data_file(data_file, instrument_mapping, output_dir, uncertain_instruments_list):
    """
    處理單個數據資料檔
    
    Args:
        data_file: 數據資料檔路徑
        instrument_mapping: 儀器編號映射
        output_dir: 輸出目錄
        uncertain_instruments_list: 儲存不確定儀器類型的清單 (list of dicts)
    """
    print(f"\n正在處理: {data_file}")
    
    # 提取檔名 (不含副檔名)
    filename_base = os.path.splitext(os.path.basename(data_file))[0]

    # 從檔名提取地名 (例如: "新竹縣-尖石鄉-D077_泰崗_.xlsx" -> "新竹縣-尖石鄉") for instrument mapping lookup
    match = re.match(r'^(.*?-.*?)-', filename_base)
    if match:
        instrument_mapping_key = match.group(1)
    else:
        # Fallback if the pattern doesn't match for instrument mapping key
        instrument_mapping_key = filename_base.split('-')[0] + '-' + filename_base.split('-')[1] if '-' in filename_base else filename_base
    
    # The first-level output folder name will be the full filename_base
    output_folder_name = filename_base
    
    print(f"地點 (輸出資料夾): {output_folder_name}")
    print(f"地點 (儀器映射鍵): {instrument_mapping_key}")
    
    # 取得該地點的儀器映射
    location_mapping = instrument_mapping.get(instrument_mapping_key, {})
    if not location_mapping:
        print(f"  警告: 找不到 '{instrument_mapping_key}' 的儀器編號資料")
    
    # 建立輸出目錄
    location_dir = os.path.join(output_dir, output_folder_name)
    os.makedirs(location_dir, exist_ok=True)
    
    # 載入數據檔
    xls = pd.ExcelFile(data_file)
    
    print(f"  共有 {len(xls.sheet_names)} 個分頁")
    
    # 處理每個分頁
    for sheet_name in xls.sheet_names:
        print(f"  處理分頁: {sheet_name}")

        # 讀取分頁資料
        df = pd.read_excel(xls, sheet_name=sheet_name)

        # 查找儀器類型（傳入欄位名稱作為 fallback 推斷依據）
        instrument_types = find_instrument_type(sheet_name, location_mapping, columns=list(df.columns))

        if len(instrument_types) > 1:
            print(f"  警告: 分頁 '{sheet_name}' 對應到多種儀器類型: {', '.join(instrument_types)}. 將複製儲存。")
            uncertain_instruments_list.append({
                '檔案名稱': os.path.basename(data_file),
                '分頁名稱': sheet_name,
                '可能的儀器類型': ', '.join(instrument_types)
            })
        elif not instrument_types or instrument_types == ["未分類"]:
             print(f"  警告: 分頁 '{sheet_name}' 無法找到儀器類型,將歸類為 '未分類'。")
        
        # 建立輸出檔名 (使用分頁名稱)
        safe_sheet_name = re.sub(r'[<>:"/\\|?*]', '_', sheet_name)
        
        # 針對每個儀器類型儲存一份
        for instrument_type in instrument_types:
            print(f"    儀器類型: {instrument_type}")
            
            # 建立儀器類型目錄
            type_dir = os.path.join(location_dir, instrument_type)
            os.makedirs(type_dir, exist_ok=True)
            
            output_file = os.path.join(type_dir, f"{safe_sheet_name}.xlsx")
            
            # 儲存為新的 Excel 檔案
            df.to_excel(output_file, index=False, engine='openpyxl')
            print(f"    已儲存: {output_file}")


def parse_args():
    """解析命令列參數"""
    import argparse
    parser = argparse.ArgumentParser(
        description="數據資料檔拆分腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python split_excel_by_location.py                                    # 使用預設路徑
  python split_excel_by_location.py --batch data/batches/08_監測數據   # 批次模式
        """
    )
    parser.add_argument(
        '--batch', '-b',
        type=str,
        metavar='PATH',
        help='批次資料夾路徑，輸出至 {batch}-seperated'
    )
    return parser.parse_args()


def main():
    """主程式"""
    args = parse_args()

    from vars import INSTRUMENT_FILE, INPUT_DIR, SEPERATED_DIR

    if args.batch:
        input_dir = args.batch.rstrip('/\\')
        output_dir = input_dir + '-seperated'
    else:
        input_dir = INPUT_DIR
        output_dir = SEPERATED_DIR

    print("=" * 60)
    print("數據資料檔拆分程式")
    print("=" * 60)

    # 1. 載入儀器編號映射
    instrument_mapping = load_instrument_mapping(INSTRUMENT_FILE)

    # 2. 尋找所有數據資料檔 (xlsx 檔案及包含 CSV 的資料夾)
    data_files = []
    csv_folders = []
    error_count = 0
    for entry in os.listdir(input_dir):
        full_path = os.path.join(input_dir, entry)
        # 確認檔名/資料夾名包含地名格式 (XX縣/市-XX鄉/區/鎮)
        if not re.match(r'.*?-.*?-', entry):
            continue
        if entry.endswith('.xlsx') and entry != os.path.basename(INSTRUMENT_FILE):
            data_files.append(full_path)
        elif os.path.isdir(full_path):
            # 檢查資料夾內是否有 CSV 檔案
            if any(f.endswith('.csv') for f in os.listdir(full_path)):
                csv_folders.append(full_path)

    print(f"\n找到 {len(data_files)} 個 Excel 資料檔:")
    for f in data_files:
        print(f"  - {os.path.basename(f)}")
    if csv_folders:
        print(f"找到 {len(csv_folders)} 個 CSV 資料夾:")
        for f in csv_folders:
            print(f"  - {os.path.basename(f)}")

    # 3. 建立輸出目錄
    os.makedirs(output_dir, exist_ok=True)

    # 初始化不確定儀器清單
    uncertain_instruments_data = []

    # 4. 處理每個數據資料檔
    for data_file in data_files:
        try:
            process_data_file(data_file, instrument_mapping, output_dir, uncertain_instruments_data)
        except Exception as e:
            print(f"處理 {data_file} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1

    # 4b. 處理 CSV 資料夾
    for csv_folder in csv_folders:
        try:
            process_csv_folder(csv_folder, instrument_mapping, output_dir)
        except Exception as e:
            print(f"處理 {csv_folder} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
            error_count += 1

    # 5. 儲存不確定儀器清單 (如果有的話)
    if uncertain_instruments_data:
        uncertain_summary_path = os.path.join(output_dir, 'uncertain_instruments_summary.csv')
        df_uncertain = pd.DataFrame(uncertain_instruments_data)
        df_uncertain.to_csv(uncertain_summary_path, index=False, encoding='utf-8-sig')
        print(f"\n已儲存不確定儀器清單: {uncertain_summary_path}")

    # 6. 清理空資料夾
    cleanup_empty_dirs(output_dir)

    print("\n" + "=" * 60)
    print("處理完成!")
    print(f"輸出目錄: {output_dir}")
    print("=" * 60)

    if error_count > 0:
        print(f"\n警告: 處理過程中出現 {error_count} 個錯誤。")
        sys.exit(1)


def cleanup_empty_dirs(path):
    """
    從下而上遍歷路徑，刪除所有空資料夾。
    """
    print(f"\n正在清理輸出目錄中的空資料夾: '{path}'...")
    for root, dirs, files in os.walk(path, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    print(f"  - 正在移除空資料夾: {dir_path}")
                    os.rmdir(dir_path)
            except OSError as e:
                print(f"  - 移除資料夾 {dir_path} 失敗: {e}")

if __name__ == "__main__":
    main()
