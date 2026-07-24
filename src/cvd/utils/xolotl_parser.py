"""Xolotl output parsing.

Xolotl writes cluster-dynamics results to a plain-text file in its case
directory (conventionally `retentionOut.txt`). This module reads that file
and converts it into crystal_growth_metrics.csv, matching the
`xolotl_case/crystal_growth_metrics.csv` output declared in dvc.yaml.

Xolotl's real output columns depend on its solver configuration -- it was
originally built to track helium retention in fusion first-wall components,
not epitaxial growth -- so the mapping from raw cluster-dynamics quantities
(interstitial/vacancy cluster concentrations) to `thickness` and
`defect_density` will need real domain calibration once Xolotl is actually
run against CVD substrate parameters. For now this parser expects
`retentionOut.txt` to already contain whitespace-separated
`time thickness defect_density` columns, one row per output timestep,
consistent with the placeholder schema the rest of the pipeline expects.
"""

from __future__ import annotations

import csv
from pathlib import Path

XOLOTL_OUTPUT_FILENAME = "retentionOut.txt"

CSV_FIELDNAMES = ("time", "thickness", "defect_density")


def _parse_retention_file(retention_path: Path) -> list[dict[str, float]]:
    """Parse Xolotl's whitespace-delimited retentionOut.txt into rows of
    (time, thickness, defect_density). Blank lines and lines starting with
    `#` (comments/headers) are skipped.
    """
    rows: list[dict[str, float]] = []
    with open(retention_path) as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            columns = line.split()
            if len(columns) < 3:
                raise ValueError(
                    f"{retention_path}:{line_no}: expected 'time thickness defect_density', "
                    f"got {line!r}"
                )

            time_s, thickness, defect_density = columns[:3]
            rows.append(
                {
                    "time": float(time_s),
                    "thickness": float(thickness),
                    "defect_density": float(defect_density),
                }
            )
    return rows


def extract_crystal_metrics(case_dir: str | Path) -> list[dict[str, float]]:
    """Read Xolotl's retentionOut.txt from `case_dir` and return parsed
    (time, thickness, defect_density) rows."""
    case_dir = Path(case_dir)
    retention_path = case_dir / XOLOTL_OUTPUT_FILENAME

    if not retention_path.exists():
        raise FileNotFoundError(f"Xolotl output file not found: {retention_path}")

    return _parse_retention_file(retention_path)


def write_crystal_growth_metrics(case_dir: str | Path, output_dir: str | Path | None = None) -> Path:
    """Convert Xolotl's retentionOut.txt into crystal_growth_metrics.csv.

    `output_dir` defaults to `case_dir`, matching the dvc.yaml stage output
    `xolotl_case/crystal_growth_metrics.csv`.
    """
    case_dir = Path(case_dir)
    output_dir = Path(output_dir) if output_dir is not None else case_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = extract_crystal_metrics(case_dir)

    output_path = output_dir / "crystal_growth_metrics.csv"
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(CSV_FIELDNAMES))
        writer.writeheader()
        writer.writerows(rows)

    return output_path
