from __future__ import annotations
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
PATTERN=re.compile(r'Mapping\[str,\s*object\]|\bpayload:\s*object\b|OperationResult\[object\]')
rows=[]
for base in (ROOT/'noetrium_platform',ROOT/'projects'):
 for path in base.rglob('*.py'):
  if '__pycache__' in path.parts: continue
  for line_no,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
   if PATTERN.search(line): rows.append({'path':str(path.relative_to(ROOT)),'line':line_no,'source':line.strip()})
print(json.dumps({'weak_contract_count':len(rows),'rows':rows},ensure_ascii=False,sort_keys=True))
raise SystemExit(0)
