
from dataclasses import dataclass
from typing import Optional

@dataclass
class RunConfig:
    headless: bool
    manual_only: bool
    excel_file: Optional[str]
    start_row: Optional[int]
    end_row: Optional[int]
    idle_timeout_ms: int
    web_timeout_s: int
    range_enabled: bool
    keep_open: bool
