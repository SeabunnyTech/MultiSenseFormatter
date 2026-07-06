import os
import pandas as pd
import sys
from abc import ABC, abstractmethod


class Colors:
    """ANSI 終端顏色代碼"""
    YELLOW = '\033[93m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'


class BaseProcessor(ABC):
    """
    感測器資料處理基類

    負責：檔案搜集、進度顯示、共用檢查邏輯
    支援同一感測器的多種表頭格式
    """

    def __init__(self, config, zero_date_str, force_overwrite=False, zero_date_map=None):
        self.config = config
        self.sensor_name = config["sensor_name"]
        self.target_subdir = config["target_subdir"]
        self.input_root_dir = config["input_path"]
        self.output_root_dir = config["output_path"]
        self.enable_cumulative = config.get("enable_cumulative", False)
        self.force_overwrite = force_overwrite

        self.zero_date = self._parse_zero_date(zero_date_str)
        self.default_zero_date = self.zero_date
        self.zero_date_map = {}
        if zero_date_map:
            for k, v in zero_date_map.items():
                self.zero_date_map[k] = self._parse_zero_date(v)

    def _parse_zero_date(self, zero_date_str):
        """解析歸零日期字串"""
        try:
            return pd.to_datetime(zero_date_str).date()
        except ValueError:
            print(f"{Colors.RED}ERROR: 無效的日期格式 '{zero_date_str}'，請使用 YYYY-MM-DD{Colors.ENDC}")
            sys.exit(1)

    def run(self):
        """主執行流程"""
        # 確保輸出根目錄存在
        os.makedirs(self.output_root_dir, exist_ok=True)

        files_to_process = self._collect_files()
        total_files = len(files_to_process)

        if total_files == 0:
            print(f"在 '{self.target_subdir}' 子目錄中找不到檔案")
            return

        # 檢查已存在的輸出檔案，若非強制模式則詢問用戶
        if not self.force_overwrite:
            existing_files = self._find_existing_outputs(files_to_process)
            if existing_files:
                action = self._ask_overwrite_action(len(existing_files), total_files)
                if action == "skip":
                    pass  # 維持預設行為
                elif action == "overwrite":
                    self.force_overwrite = True
                elif action == "clean":
                    self._clean_sensor_output_dir()

        self._print_start_info(total_files)
        counters = self._init_counters()

        for i, input_file_path in enumerate(files_to_process, start=1):
            self._process_file(i, total_files, input_file_path, counters)

        self._print_summary(counters)
        self._cleanup_empty_dirs()

        if counters["error"] > 0:
            print(f"\n{Colors.RED}處理完成，但有 {counters['error']} 個錯誤{Colors.ENDC}")
            sys.exit(1)

    def _find_existing_outputs(self, files_to_process):
        """找出已存在的輸出檔案"""
        existing = []
        for input_file_path in files_to_process:
            output_path = self._get_output_path_no_create(input_file_path)
            if os.path.exists(output_path):
                existing.append(output_path)
        return existing

    def _get_output_path_no_create(self, input_file_path):
        """計算輸出檔案路徑（不建立目錄）"""
        file_name = os.path.basename(input_file_path)
        relative_path = os.path.relpath(os.path.dirname(input_file_path), self.input_root_dir)
        output_dir = os.path.join(self.output_root_dir, relative_path)
        output_file_name = os.path.splitext(file_name)[0] + '.csv'
        return os.path.join(output_dir, output_file_name)

    def _ask_overwrite_action(self, existing_count, total_count):
        """詢問用戶如何處理已存在的檔案"""
        print(f"\n發現 {existing_count}/{total_count} 個輸出檔案已存在", flush=True)
        print("請選擇處理方式：", flush=True)
        print("  [1] 跳過已存在的檔案（預設）", flush=True)
        print("  [2] 覆蓋已存在的檔案", flush=True)
        print("  [3] 清空此感測器的輸出目錄後重新處理", flush=True)

        while True:
            try:
                choice = input("請輸入選項 [1/2/3]（直接按 Enter 為預設）: ").strip()
                if choice == "" or choice == "1":
                    return "skip"
                elif choice == "2":
                    return "overwrite"
                elif choice == "3":
                    confirm = input(f"確定要清空 '{self.target_subdir}' 的所有輸出嗎？[y/N]: ").strip().lower()
                    if confirm == 'y':
                        return "clean"
                    else:
                        print("已取消，將跳過已存在的檔案")
                        return "skip"
                else:
                    print("無效的選項，請重新輸入")
            except EOFError:
                # 非互動模式，使用預設值
                return "skip"

    def _clean_sensor_output_dir(self):
        """清空此感測器的輸出目錄"""
        print(f"\n清空 '{self.target_subdir}' 相關的輸出目錄...")

        for root, dirs, files in os.walk(self.output_root_dir):
            if self.target_subdir in root.split(os.sep):
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        os.remove(file_path)
                        print(f"  - 刪除: {file_path}")
                    except OSError as e:
                        print(f"  - 刪除失敗 {file_path}: {e}")

    def _print_start_info(self, total_files):
        """顯示處理開始資訊"""
        print(f"\n處理感測器: {self.sensor_name}")
        print(f"找到 {total_files} 個檔案，開始處理")
        print(f"歸零基準日期: {self.zero_date}")
        if self.enable_cumulative:
            print(f"累計計算: 啟用")

    def _init_counters(self):
        """初始化計數器"""
        return {
            "processed": 0,
            "skipped_exist": 0,
            "skipped_header": 0,
            "skipped_date": 0,
            "error": 0
        }

    def _collect_files(self):
        """搜集所有待處理的檔案"""
        files_to_process = []
        print(f"搜尋目錄 '{self.input_root_dir}' 中的 '{self.target_subdir}'...")

        for root, _, files in os.walk(self.input_root_dir):
            if self.target_subdir in root.split(os.sep):
                for file_name in files:
                    is_data_file = file_name.endswith('.xlsx') or file_name.endswith('.csv')
                    is_temp_file = file_name.startswith('~$')
                    if is_data_file and not is_temp_file:
                        files_to_process.append(os.path.join(root, file_name))

        return files_to_process

    def _read_file(self, file_path, **kwargs):
        """根據副檔名讀取檔案"""
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path, **kwargs)
        return pd.read_excel(file_path, **kwargs)

    def _find_matching_format(self, actual_columns):
        """從設定中找出匹配的表頭格式"""
        for fmt in self.config["formats"]:
            if actual_columns == fmt["expected_columns"]:
                return fmt
        return None

    def _get_location_name(self, input_file_path):
        """從檔案路徑提取地點名稱"""
        try:
            relative_dir = os.path.relpath(os.path.dirname(input_file_path), self.input_root_dir)
            return relative_dir.split(os.sep)[0]
        except (ValueError, IndexError):
            return "Unknown"

    def _get_output_path(self, input_file_path):
        """計算輸出檔案路徑"""
        file_name = os.path.basename(input_file_path)
        relative_path = os.path.relpath(os.path.dirname(input_file_path), self.input_root_dir)
        output_dir = os.path.join(self.output_root_dir, relative_path)
        os.makedirs(output_dir, exist_ok=True)
        output_file_name = os.path.splitext(file_name)[0] + '.csv'
        return os.path.join(output_dir, output_file_name)

    def _process_file(self, i, total_files, input_file_path, counters):
        """處理單一檔案"""
        file_name = os.path.basename(input_file_path)
        location_name = self._get_location_name(input_file_path)

        # 按站號套用歸零日期
        if self.zero_date_map:
            station_num = location_name.split('_')[0]
            self.zero_date = self.zero_date_map.get(station_num, self.default_zero_date)

        # 顯示進度
        progress_prefix = f"[{i:>{len(str(total_files))}}/{total_files}]"
        print(f"{progress_prefix} 處理 [{location_name}] '{file_name}'...")

        try:
            output_file_path = self._get_output_path(input_file_path)

            # 檢查輸出檔案是否已存在
            if os.path.exists(output_file_path) and not self.force_overwrite:
                print(f"{Colors.YELLOW}  -> 跳過 (檔案已存在){Colors.ENDC}")
                counters["skipped_exist"] += 1
                return

            # 快速讀取表頭進行格式驗證
            df_header = self._read_file(input_file_path, nrows=0)
            df_header.columns = [col.strip() for col in df_header.columns]
            matched_format = self._find_matching_format(list(df_header.columns))

            if not matched_format:
                print(f"{Colors.YELLOW}  -> 跳過 (無法識別表頭: {list(df_header.columns)}){Colors.ENDC}")
                counters["skipped_header"] += 1
                return

            # 完整讀取並處理檔案
            df = self._read_file(input_file_path)
            df.columns = [col.strip() for col in df.columns]
            output_df = self._process_data(df, matched_format)

            if output_df is None:
                counters["skipped_date"] += 1
                return

            # 輸出結果
            output_df.to_csv(output_file_path, header=False, index=False, encoding='utf-8')
            print(f"{Colors.GREEN}  -> OK (格式: '{matched_format['id']}'){Colors.ENDC}")
            counters["processed"] += 1

        except Exception as e:
            print(f"{Colors.RED}  -> 錯誤 ({e}){Colors.ENDC}")
            counters["error"] += 1

    @abstractmethod
    def _process_data(self, df, matched_format):
        """
        感測器特定的資料處理邏輯（由子類實作）

        Returns:
            DataFrame: 處理後的資料，或 None 表示跳過此檔案
        """
        pass

    def _print_summary(self, counters):
        """顯示處理摘要"""
        print("\n--- 處理摘要 ---")
        print(f"成功處理: {counters['processed']}")
        print(f"跳過 (已存在): {counters['skipped_exist']}")
        print(f"跳過 (表頭不符): {counters['skipped_header']}")
        print(f"跳過 (日期範圍外): {counters['skipped_date']}")
        print(f"錯誤: {counters['error']}")
        print("----------------")

    def _cleanup_empty_dirs(self):
        """清理空目錄"""
        print(f"\n清理 '{self.output_root_dir}' 中的空目錄...")

        for root, dirs, _ in os.walk(self.output_root_dir, topdown=False):
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    if not os.listdir(dir_path):
                        print(f"  - 移除空目錄: {dir_path}")
                        os.rmdir(dir_path)
                except OSError as e:
                    print(f"  - 移除目錄失敗 {dir_path}: {e}")



class ZeroingProcessor(BaseProcessor):
    """
    歸零處理器

    將感測器數值以指定日期為基準進行歸零計算
    支援多欄位處理及累計計算
    """

    def _process_data(self, df, matched_format):
        """處理資料：歸零計算，可選累計計算"""
        value_configs = matched_format["value_columns"]
        time_col = matched_format.get("time_column", "系統時間")

        # 1. 時間處理與每日採樣
        df_daily = self._prepare_daily_data(df, time_col)
        if df_daily is None:
            return None

        # 2. 驗證日期範圍
        df_filtered = self._filter_by_zero_date(df_daily)
        if df_filtered is None:
            return None

        # 3. 歸零計算
        zero_values = self._get_zero_values(df_filtered, value_configs)
        if zero_values is None:
            return None

        self._apply_zeroing(df_filtered, value_configs, zero_values)

        # 4. 累計計算（可選）
        if self.enable_cumulative:
            self._apply_cumulative(df_filtered, value_configs)

        # 5. 建立輸出 DataFrame
        return self._build_output(df_filtered, time_col, value_configs)

    def _prepare_daily_data(self, df, time_col):
        """準備每日資料：時間轉換、排序、每日取最後一筆"""
        df[time_col] = pd.to_datetime(df[time_col].astype(str))
        df = df.sort_values(by=time_col).reset_index(drop=True)
        df['date_only'] = df[time_col].dt.date

        df_daily = df.drop_duplicates(subset=['date_only'], keep='last').copy()

        if df_daily.empty:
            print(f"{Colors.YELLOW}  -> 跳過 (無資料){Colors.ENDC}")
            return None

        return df_daily

    def _filter_by_zero_date(self, df_daily):
        """根據歸零日期篩選資料"""
        max_date = df_daily['date_only'].max()

        if self.zero_date > max_date:
            print(f"{Colors.YELLOW}  -> 跳過 (歸零日期 {self.zero_date} 晚於最後資料日期 {max_date}){Colors.ENDC}")
            return None

        return df_daily[df_daily['date_only'] >= self.zero_date].copy()

    def _get_zero_values(self, df_filtered, value_configs):
        """取得歸零基準值，若歸零日期不在資料中則以第一筆資料為基準"""
        zero_row = df_filtered[df_filtered['date_only'] == self.zero_date]

        if zero_row.empty:
            # 資料起始日在歸零日期之後，以第一筆資料作為歸零基準
            zero_row = df_filtered.iloc[[0]]
            actual_date = df_filtered['date_only'].iloc[0]
            print(f"  -> 歸零日期 {self.zero_date} 無資料，改以首筆資料日期 {actual_date} 為基準")

        zero_values = {}
        for v_conf in value_configs:
            col_name = v_conf["name"]
            zero_values[col_name] = pd.to_numeric(zero_row[col_name].iloc[0], errors='coerce')

        return zero_values

    def _apply_zeroing(self, df_filtered, value_configs, zero_values):
        """套用歸零計算"""
        for v_conf in value_configs:
            col_name = v_conf["name"]
            output_name = v_conf["output_name"]
            df_filtered[col_name] = pd.to_numeric(df_filtered[col_name], errors='coerce')
            df_filtered[output_name] = df_filtered[col_name] - zero_values[col_name]

    def _apply_cumulative(self, df_filtered, value_configs):
        """套用累計計算"""
        for v_conf in value_configs:
            output_name = v_conf["output_name"]
            cumulative_name = output_name.replace("歸零值", "累計")
            df_filtered[cumulative_name] = df_filtered[output_name].cumsum()

    def _build_output(self, df_filtered, time_col, value_configs):
        """建立輸出 DataFrame"""
        output_df = pd.DataFrame()
        output_df[time_col] = df_filtered[time_col].dt.strftime('%Y/%m/%d %H:%M')

        for v_conf in value_configs:
            output_df[v_conf["name"]] = df_filtered[v_conf["name"]].values
            output_df[v_conf["output_name"]] = df_filtered[v_conf["output_name"]].values

            # 如果啟用累計，加入累計欄位
            if self.enable_cumulative:
                cumulative_name = v_conf["output_name"].replace("歸零值", "累計")
                output_df[cumulative_name] = df_filtered[cumulative_name].values

        return output_df


class SeasonalRainfallProcessor(BaseProcessor):
    """
    季節性雨量處理器

    依據台灣乾濕季進行累積計算：
    - 濕季：5/1 至 11/30
    - 乾季：12/1 至 4/30
    每個季節開始時累積歸零
    """

    def __init__(self, config, force_overwrite=False, zero_date_map=None):
        # 雨量計不使用歸零日期，傳入一個不影響處理的預設值
        super().__init__(config, zero_date_str="1900-01-01", force_overwrite=force_overwrite, zero_date_map=zero_date_map)
        self.enable_cumulative = False  # 不使用通用累計邏輯

        # 季節設定
        self.seasons = config.get("seasons", {
            "wet": {"start_month": 5, "start_day": 1, "end_month": 11, "end_day": 30},
            "dry": {"start_month": 12, "start_day": 1, "end_month": 4, "end_day": 30},
        })

    def _print_start_info(self, total_files):
        """顯示處理開始資訊"""
        print(f"\n處理感測器: {self.sensor_name}")
        print(f"找到 {total_files} 個檔案，開始處理")
        print(f"季節累積模式：濕季 5/1-11/30，乾季 12/1-4/30")

    def _get_season(self, date):
        """判斷日期屬於哪個季節，回傳 (季節名稱, 該季起始日期)"""
        month = date.month
        day = date.day
        year = date.year

        wet = self.seasons["wet"]
        # 濕季：5/1 - 11/30
        if (month > wet["start_month"] or
            (month == wet["start_month"] and day >= wet["start_day"])) and \
           (month < wet["end_month"] or
            (month == wet["end_month"] and day <= wet["end_day"])):
            season_start = pd.Timestamp(year=year, month=wet["start_month"], day=wet["start_day"])
            return ("wet", season_start)

        # 乾季：12/1 - 4/30（跨年）
        dry = self.seasons["dry"]
        if month >= dry["start_month"]:
            # 12月，乾季起始於當年 12/1
            season_start = pd.Timestamp(year=year, month=dry["start_month"], day=dry["start_day"])
            return ("dry", season_start)
        else:
            # 1-4月，乾季起始於前一年 12/1
            season_start = pd.Timestamp(year=year-1, month=dry["start_month"], day=dry["start_day"])
            return ("dry", season_start)

    def _process_data(self, df, matched_format):
        """處理資料：季節性累積計算"""
        time_col = matched_format.get("time_column", "系統時間")
        value_col = matched_format.get("value_column", "24小時累積雨量")
        output_col = matched_format.get("output_column", "季節累積雨量")

        # 1. 時間處理與排序，每日取最後一筆
        df[time_col] = pd.to_datetime(df[time_col].astype(str))
        df = df.sort_values(by=time_col).reset_index(drop=True)
        df['date_only'] = df[time_col].dt.date
        df = df.drop_duplicates(subset=['date_only'], keep='last').copy()

        if df.empty:
            print(f"{Colors.YELLOW}  -> 跳過 (無資料){Colors.ENDC}")
            return None

        # 2. 計算每筆資料的季節和季節起始日
        df['_season_info'] = df[time_col].apply(self._get_season)
        df['_season'] = df['_season_info'].apply(lambda x: x[0])
        df['_season_start'] = df['_season_info'].apply(lambda x: x[1])

        # 3. 按季節分組計算累積
        # 使用 season_start 作為分組依據（這樣每個季節週期都是獨立的）
        df[output_col] = df.groupby('_season_start')[value_col].cumsum()

        # 4. 建立輸出 DataFrame
        output_df = pd.DataFrame()
        output_df[time_col] = df[time_col].dt.strftime('%Y/%m/%d %H:%M')
        output_df[value_col] = df[value_col].values
        output_df[output_col] = df[output_col].values

        return output_df


class GNSSProcessor(BaseProcessor):
    """
    GNSS 資料處理器

    1.  每日取最後一筆資料
    2.  選取特定欄位 (E, N, U)
    3.  以指定日期為基準進行歸零
    4.  計算歸零後的累積位移 (mm)
    5.  計算星曆（小數點年份）
    6.  額外輸出 .txt 檔案（星曆、解算後E/N/U值）
    7.  可選：將三維位移投影至 SAR 雷達視線方向 (LOS)
    """

    def __init__(self, config, zero_date_str, force_overwrite=False, zero_date_map=None):
        super().__init__(config, zero_date_str, force_overwrite, zero_date_map=zero_date_map)
        # 用於暫存 TXT 輸出資料
        self._txt_output_df = None
        # 多衛星 LOS 投影設定
        sat_config = config.get("satellite_table", {})
        sat_file = sat_config.get("file")
        if sat_file and os.path.exists(sat_file):
            heading_angles = sat_config.get("heading_angles", {"ASC": 350, "DES": 190})
            self._satellites = self._parse_satellite_table(sat_file, heading_angles)
            self._los_output_name = sat_config.get("los_output_name", "累積LOS位移(mm)")
        else:
            self._satellites = []
            self._los_output_name = "累積LOS位移(mm)"

    def _print_start_info(self, total_files):
        """顯示處理開始資訊（含衛星 LOS 投影狀態）"""
        print(f"\n處理感測器: {self.sensor_name}")
        print(f"找到 {total_files} 個檔案，開始處理")
        print(f"歸零基準日期: {self.zero_date}")
        if self._satellites:
            print(f"衛星 LOS 投影: {len(self._satellites)} 個軌道/Swath 組態")
        else:
            print(f"衛星 LOS 投影: 未啟用")

    @staticmethod
    def _compute_los_unit_vectors(incidence_deg, heading_deg):
        """
        根據入射角和衛星飛行方向角計算 LOS 投影的單位向量

        公式: d_LOS = e_vec·dE + n_vec·dN + u_vec·dU
          其中:
            u_vec =  cos(θ)
            n_vec =  sin(θ)·sin(φ)
            e_vec = -sin(θ)·cos(φ)

        Args:
            incidence_deg: 入射角（度），從垂直方向量測
            heading_deg:   衛星飛行方向角（度），從北方順時針量測
        """
        import math
        theta = math.radians(incidence_deg)
        phi = math.radians(heading_deg)
        u_vec = math.cos(theta)
        n_vec = math.sin(theta) * math.sin(phi)
        e_vec = -math.sin(theta) * math.cos(phi)
        return {"up": u_vec, "north": n_vec, "east": e_vec}

    @staticmethod
    def _parse_angle(value):
        """解析入射角，範圍值取平均"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and '~' in value:
            parts = value.split('~')
            return sum(float(p.strip()) for p in parts) / len(parts)
        return float(value)

    def _parse_satellite_table(self, file_path, heading_angles):
        """
        解析衛星入射角表

        表格結構：左半部為 ASC（欄 0-2），右半部為 DES（欄 4-6）
        每組欄位為：軌道編號、Swath 編號、入射角
        軌道編號使用向下填充（NaN 表示同上）
        """
        df = pd.read_excel(file_path, header=None)
        satellites = []

        # 解析 ASC 組（欄 0, 1, 2），從第 3 列開始（跳過標題列）
        current_track = None
        for i in range(2, len(df)):
            track = df.iloc[i, 0]
            swath = df.iloc[i, 1]
            angle = df.iloc[i, 2]

            if pd.notna(track):
                current_track = str(track)

            if pd.notna(swath) and pd.notna(angle):
                satellites.append({
                    "orbit": "ASC",
                    "track": current_track,
                    "swath": int(swath),
                    "incidence_angle": self._parse_angle(angle),
                    "heading_angle": heading_angles.get("ASC", 350),
                })

        # 解析 DES 組（欄 4, 5, 6）
        current_track = None
        for i in range(2, len(df)):
            track = df.iloc[i, 4]
            swath = df.iloc[i, 5]
            angle = df.iloc[i, 6]

            if pd.notna(track):
                current_track = str(track)

            if pd.notna(swath) and pd.notna(angle):
                satellites.append({
                    "orbit": "DES",
                    "track": current_track,
                    "swath": int(swath),
                    "incidence_angle": self._parse_angle(angle),
                    "heading_angle": heading_angles.get("DES", 190),
                })

        return satellites

    def _process_file(self, i, total_files, input_file_path, counters):
        """處理單一檔案（覆寫以支援額外 TXT 輸出）"""
        file_name = os.path.basename(input_file_path)
        location_name = self._get_location_name(input_file_path)

        # 按站號套用歸零日期
        if self.zero_date_map:
            station_num = location_name.split('_')[0]
            self.zero_date = self.zero_date_map.get(station_num, self.default_zero_date)

        # 顯示進度
        progress_prefix = f"[{i:>{len(str(total_files))}}/{total_files}]"
        print(f"{progress_prefix} 處理 [{location_name}] '{file_name}'...")

        try:
            output_file_path = self._get_output_path(input_file_path)
            txt_output_path = os.path.splitext(output_file_path)[0] + '.txt'

            # 檢查輸出檔案是否已存在
            if os.path.exists(output_file_path) and not self.force_overwrite:
                print(f"{Colors.YELLOW}  -> 跳過 (檔案已存在){Colors.ENDC}")
                counters["skipped_exist"] += 1
                return

            # 快速讀取表頭進行格式驗證
            df_header = self._read_file(input_file_path, nrows=0)
            df_header.columns = [col.strip() for col in df_header.columns]
            matched_format = self._find_matching_format(list(df_header.columns))

            if not matched_format:
                print(f"{Colors.YELLOW}  -> 跳過 (無法識別表頭: {list(df_header.columns)}){Colors.ENDC}")
                counters["skipped_header"] += 1
                return

            # 完整讀取並處理檔案
            df = self._read_file(input_file_path)
            df.columns = [col.strip() for col in df.columns]
            output_df = self._process_data(df, matched_format)

            if output_df is None:
                counters["skipped_date"] += 1
                return

            # 輸出 CSV
            output_df.to_csv(output_file_path, header=False, index=False, encoding='utf-8')

            # 輸出 TXT（星曆、解算後E/N/U值）
            if self._txt_output_df is not None:
                self._txt_output_df.to_csv(txt_output_path, sep='\t', header=False, index=False, encoding='utf-8')

            # 為每個衛星組態生成含 LOS 投影的檔案
            sat_count = 0
            base_path = os.path.splitext(output_file_path)[0]
            for sat in self._satellites:
                sat_suffix = f"_{sat['orbit']}_{sat['track']}_S{sat['swath']}"
                sat_output_path = base_path + sat_suffix + '.csv'

                los_vectors = self._compute_los_unit_vectors(
                    sat["incidence_angle"], sat["heading_angle"]
                )

                sat_df = output_df.copy()
                sat_df[self._los_output_name] = (
                    los_vectors["east"] * output_df['累積E位移(mm)']
                    + los_vectors["north"] * output_df['累積N位移(mm)']
                    + los_vectors["up"] * output_df['累積U位移(mm)']
                )

                sat_df.to_csv(sat_output_path, header=False, index=False, encoding='utf-8')
                sat_count += 1

            if sat_count > 0:
                print(f"{Colors.GREEN}  -> OK (格式: '{matched_format['id']}', 含 {sat_count} 個衛星 LOS 檔案){Colors.ENDC}")
            else:
                print(f"{Colors.GREEN}  -> OK (格式: '{matched_format['id']}'){Colors.ENDC}")
            counters["processed"] += 1

        except Exception as e:
            print(f"{Colors.RED}  -> 錯誤 ({e}){Colors.ENDC}")
            counters["error"] += 1

    def _calculate_ephemeris(self, dt):
        """
        計算星曆（小數點年份）

        公式：(日期 - 當年1月1日) / 年天數 + 年份
        閏年為 366 天，非閏年為 365 天
        """
        import calendar
        year = dt.year
        year_start = pd.Timestamp(year=year, month=1, day=1)
        days_in_year = 366 if calendar.isleap(year) else 365
        day_of_year = (dt - year_start).days
        return year + day_of_year / days_in_year

    def _process_data(self, df, matched_format):
        """處理 GNSS 資料"""
        value_configs = matched_format["value_columns"]
        time_col = matched_format.get("time_column", "系統時間")
        rename_map = matched_format.get("rename_map", {})
        final_columns = matched_format.get("final_columns", [])

        # 1. 時間處理與每日採樣
        df[time_col] = pd.to_datetime(df[time_col].astype(str), errors='coerce')
        df.dropna(subset=[time_col], inplace=True) # 移除無法解析的日期
        df = df.sort_values(by=time_col).reset_index(drop=True)
        df['date_only'] = df[time_col].dt.date
        df_daily = df.drop_duplicates(subset=['date_only'], keep='last').copy()

        if df_daily.empty:
            print(f"{Colors.YELLOW}  -> 跳過 (無有效資料){Colors.ENDC}")
            return None

        # 2. 驗證日期範圍
        max_date = df_daily['date_only'].max()
        if self.zero_date > max_date:
            print(f"{Colors.YELLOW}  -> 跳過 (歸零日期 {self.zero_date} 晚於最後資料日期 {max_date}){Colors.ENDC}")
            return None
        df_filtered = df_daily[df_daily['date_only'] >= self.zero_date].copy()
        if df_filtered.empty:
            print(f"{Colors.YELLOW}  -> 跳過 (篩選後無資料){Colors.ENDC}")
            return None

        # 3. 取得歸零基準值，若歸零日期不在資料中則以第一筆資料為基準
        zero_row = df_filtered[df_filtered['date_only'] == self.zero_date]
        if zero_row.empty:
            zero_row = df_filtered.iloc[[0]]
            actual_date = df_filtered['date_only'].iloc[0]
            print(f"  -> 歸零日期 {self.zero_date} 無資料，改以首筆資料日期 {actual_date} 為基準")

        zero_values = {}
        for v_conf in value_configs:
            col_name = v_conf["name"]
            if col_name not in zero_row.columns:
                print(f"{Colors.RED}  -> 錯誤 (欄位 '{col_name}' 不存在){Colors.ENDC}")
                raise ValueError(f"欄位 '{col_name}' 不存在")
            zero_values[col_name] = pd.to_numeric(zero_row[col_name], errors='coerce').iloc[0]

        # 4. 套用歸零計算與單位轉換 (m -> mm)
        for v_conf in value_configs:
            col_name = v_conf["name"]
            output_name = v_conf["output_name"]
            # 確保欄位是數值型別
            df_filtered[col_name] = pd.to_numeric(df_filtered[col_name], errors='coerce')
            df_filtered[output_name] = (df_filtered[col_name] - zero_values[col_name]) * 1000

        # 5. 欄位重命名
        if rename_map:
            df_filtered.rename(columns=rename_map, inplace=True)

        # 6. 計算星曆
        df_filtered['星曆'] = df_filtered[time_col].apply(self._calculate_ephemeris)

        # 7. 建立與排序最終輸出 DataFrame
        output_df = pd.DataFrame()

        # 確保所有需要的欄位都存在
        for col in final_columns:
            if col == '星曆':
                output_df[col] = df_filtered[col].values
            elif col in df_filtered.columns:
                output_df[col] = df_filtered[col].values
            else:
                # 如果欄位不存在，填入空值
                print(f"{Colors.YELLOW}  -> 警告 (欄位 '{col}' 不在最終資料中，將填入空值){Colors.ENDC}")
                output_df[col] = pd.NA

        # 格式化時間欄位
        if time_col in output_df.columns:
            output_df[time_col] = pd.to_datetime(output_df[time_col]).dt.strftime('%Y/%m/%d %H:%M')

        # 8. 準備 TXT 輸出資料（星曆、解算後E/N/U值）
        txt_columns = ['星曆', '解算後E值', '解算後N值', '解算後U值']
        self._txt_output_df = pd.DataFrame()
        for col in txt_columns:
            if col in df_filtered.columns:
                self._txt_output_df[col] = df_filtered[col].values

        return output_df
