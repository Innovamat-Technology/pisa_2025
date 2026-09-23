"""Run the whole pipeline, step by step. Usage: python code/python/scripts/run_all.py [first_step]"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOMAINS = ("math", "scie", "read")
STEPS = ([("01_extract.py",), ("02_build_base.py",), ("03_irt_homepos.py",), ("04_harmonise.py",)]
         + [("05_quartile_changes.py", d) for d in DOMAINS] + [("06_reclassification.py",), ("07_four_cycle_series.py",)]
         + [(f, d) for f in ("08_items.py", "09_correlations_pared.py", "10_composite_weights.py",
                             "11_missing_and_thresholds.py", "12_systems.py") for d in DOMAINS]
         + [("13_figures.py",)])
first = int(sys.argv[1]) if len(sys.argv) > 1 else 1
for step in STEPS:
    if int(step[0][:2]) < first:
        continue
    print(f"\n##### {' '.join(step)}", flush=True)
    subprocess.run([sys.executable, str(HERE / step[0]), *step[1:]], check=True)
