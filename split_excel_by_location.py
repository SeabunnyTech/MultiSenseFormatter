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
import pandas as pd
from pathlib import Path
import openpyxl
from openpyxl import load_workbook


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


def find_instrument_type(sheet_name, location_mapping):
    """
    根據分頁名稱查找對應的儀器類型
    
    Args:
        sheet_name: 分頁名稱
        location_mapping: 該地點的儀器編號映射 dict
    
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
        
        # 查找儀器類型 (現在會返回列表)
        instrument_types = find_instrument_type(sheet_name, location_mapping)
        
        if len(instrument_types) > 1:
            print(f"  警告: 分頁 '{sheet_name}' 對應到多種儀器類型: {', '.join(instrument_types)}. 將複製儲存。")
            uncertain_instruments_list.append({
                '檔案名稱': os.path.basename(data_file),
                '分頁名稱': sheet_name,
                '可能的儀器類型': ', '.join(instrument_types)
            })
        elif not instrument_types or instrument_types == ["未分類"]:
             print(f"  警告: 分頁 '{sheet_name}' 無法找到儀器類型,將歸類為 '未分類'。")
             # No need to add to uncertain list if it's explicitly '未分類' and only one.
             # The find_instrument_type already prints a warning in this case.

        # 讀取分頁資料 (只需讀取一次)
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
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


def main():
    """主程式"""
    # ===== 設定區域 =====
    # 請修改以下路徑為你的實際路徑
    from vars import INSTRUMENT_FILE, INPUT_DIR, SEPERATED_DIR
    
    # ===== 程式執行 =====
    
    print("=" * 60)
    print("數據資料檔拆分程式")
    print("=" * 60)
    
    # 1. 載入儀器編號映射
    instrument_mapping = load_instrument_mapping(INSTRUMENT_FILE)
    
    # 2. 尋找所有數據資料檔 (假設是以 .xlsx 結尾,但排除儀器編號檔案)
    data_files = []
    for file in os.listdir(INPUT_DIR):
        if file.endswith('.xlsx') and file != os.path.basename(INSTRUMENT_FILE):
            # 確認檔名包含地名格式 (XX縣/市-XX鄉/區/鎮)
            if re.match(r'.*?-.*?-', file):
                data_files.append(os.path.join(INPUT_DIR, file))
    
    print(f"\n找到 {len(data_files)} 個數據資料檔:")
    for f in data_files:
        print(f"  - {os.path.basename(f)}")
    
    # 3. 建立輸出目錄
    os.makedirs(SEPERATED_DIR, exist_ok=True)

    # 初始化不確定儀器清單
    uncertain_instruments_data = []
    
    # 4. 處理每個數據資料檔
    for data_file in data_files:
        try:
            process_data_file(data_file, instrument_mapping, SEPERATED_DIR, uncertain_instruments_data)
        except Exception as e:
            print(f"處理 {data_file} 時發生錯誤: {e}")
            import traceback
            traceback.print_exc()
    
    # 5. 儲存不確定儀器清單 (如果有的話)
    if uncertain_instruments_data:
        uncertain_summary_path = os.path.join(SEPERATED_DIR, 'uncertain_instruments_summary.csv')
        df_uncertain = pd.DataFrame(uncertain_instruments_data)
        df_uncertain.to_csv(uncertain_summary_path, index=False, encoding='utf-8-sig') # Use utf-8-sig for BOM
        print(f"\n已儲存不確定儀器清單: {uncertain_summary_path}")
    
    print("\n" + "=" * 60)
    print("處理完成!")
    print(f"輸出目錄: {SEPERATED_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
