"""Quick structural analysis of the extracted stock register text."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "stock_register_extracted.txt"
text = SRC.read_text(encoding="utf-8")
parts = re.split(r"===== PAGE (\d+) =====", text)

for i in range(1, len(parts), 2):
    page = int(parts[i])
    body = parts[i + 1]
    nums = [int(x) for x in re.findall(r"(?m)^(\d{1,3})\s*$", body) if 1 <= int(x) <= 150]
    print(f"page {page:2d}  int-lines={nums[:6]} ... {nums[-6:]}  count={len(nums)}")
