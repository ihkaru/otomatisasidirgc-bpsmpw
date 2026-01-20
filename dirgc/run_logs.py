import csv
import re
from datetime import datetime, timedelta
from pathlib import Path

LOGS_DIR = "logs"

def _next_run_number(date_dir):
    max_run = 0
    # Scan both xlsx (legacy) and csv
    for path in list(date_dir.glob("run*_*.xlsx")) + list(date_dir.glob("run*_*.csv")):
        match = re.match(r"run(\d+)_", path.stem)
        if not match:
            continue
        try:
            number = int(match.group(1))
        except ValueError:
            continue
        if number > max_run:
            max_run = number
    return max_run + 1


def build_run_log_path(now=None):
    now = now or datetime.now()
    date_folder = now.strftime("%Y%m%d")
    date_dir = Path(LOGS_DIR) / date_folder
    date_dir.mkdir(parents=True, exist_ok=True)
    run_number = _next_run_number(date_dir)
    time_label = now.strftime("%H%M")
    filename = f"run{run_number}_{time_label}.csv"
    return date_dir / filename


def write_run_log(rows, output_path):
    columns = [
        "no",
        "idsbr",
        "nama_usaha",
        "alamat",
        "keberadaanusaha_gc",
        "latitude",
        "longitude",
        "status",
        "catatan",
    ]

    # Write CSV using standard library
    str_path = str(output_path)
    try:
        with open(str_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                # Ensure all fields exist
                clean_row = {col: str(row.get(col, "")) for col in columns}
                writer.writerow(clean_row)
    except Exception as e:
        raise RuntimeError(f"Failed to write CSV log: {e}")


def _read_log_file(path):
    """Helper to read log file (CSV or Excel) into DataFrame or list of dicts."""
    path_str = str(path)
    if path_str.endswith(".xlsx"):
        try:
            import pandas as pd
            return pd.read_excel(path_str, dtype=str)
        except ImportError:
            return None # Cannot read Excel without pandas
        except Exception:
            return None
    elif path_str.endswith(".csv"):
        try:
            import pandas as pd
            # Use pandas if available for robust parsing
            return pd.read_csv(path_str, dtype=str)
        except ImportError:
            # Fallback to csv module
            try:
                with open(path_str, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    return list(reader) # Return list of dicts directly
            except Exception:
                return None
    return None

def get_last_processed_row():
    # ... (Simplified logic similar to before but using _read_log_file) ...
    # For brevity, let's just reuse the pandas logic if available, or manual check for CSV
    
    # Actually, let's keep it simple and robust
    try:
        import pandas as pd
    except ImportError:
        pass # We will handle list of dicts if pandas missing

    today = datetime.now()
    candidate_logs = []
    
    for day_offset in range(7):
        check_date = today - timedelta(days=day_offset)
        folder_name = check_date.strftime("%Y%m%d")
        folder_path = Path(LOGS_DIR) / folder_name
        
        if folder_path.exists():
            day_logs = list(folder_path.glob("run*_*.csv")) + list(folder_path.glob("run*_*.xlsx"))
            if day_logs:
                candidate_logs.extend(day_logs)
                break # Only latest day

    if not candidate_logs:
        return 0

    candidate_logs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    max_row = 0
    for log_path in candidate_logs[:3]:
        data = _read_log_file(log_path)
        if data is None: continue
        
        # If pandas DataFrame
        if hasattr(data, "columns"):
            if "no" not in data.columns or "status" not in data.columns: continue
            completed = data[data["status"].astype(str).str.lower().isin(["berhasil", "skipped"])]
            if not completed.empty:
                try:
                    current_max = int(completed["no"].astype(float).max())
                    if current_max > max_row: max_row = current_max
                except: pass
        # If list of dicts (fallback)
        elif isinstance(data, list):
             for row in data:
                 if row.get("status", "").lower() in ["berhasil", "skipped"]:
                     try:
                         r_no = int(float(row.get("no")))
                         if r_no > max_row: max_row = r_no
                     except: pass
                     
    return max_row


def get_completed_idsbrs(days_back=30):
    completed_ids = set()
    today = datetime.now()
    
    for day_offset in range(days_back):
        check_date = today - timedelta(days=day_offset)
        folder_name = check_date.strftime("%Y%m%d")
        folder_path = Path(LOGS_DIR) / folder_name
        
        if not folder_path.exists():
            continue
            
        logs = list(folder_path.glob("run*_*.csv")) + list(folder_path.glob("run*_*.xlsx"))
        for log_path in logs:
            data = _read_log_file(log_path)
            if data is None: continue
            
            valid_stats = ["berhasil", "sukses"]
            
            if hasattr(data, "columns"):
                 if "idsbr" not in data.columns or "status" not in data.columns: continue
                 valid_mask = data["status"].astype(str).str.lower().isin(valid_stats)
                 done_ids = data.loc[valid_mask, "idsbr"].dropna().astype(str).tolist()
                 completed_ids.update(done_ids)
            elif isinstance(data, list):
                 for row in data:
                     if row.get("status", "").lower() in valid_stats:
                         idsbr = row.get("idsbr")
                         if idsbr: completed_ids.add(str(idsbr))

    return completed_ids
