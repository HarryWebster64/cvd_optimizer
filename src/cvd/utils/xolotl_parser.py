"""Xolotl output parsing.

Xolotl writes cluster-dynamics results to `retentionOut.txt` in its case
directory: a `#`-prefixed header naming each column, followed by one
whitespace-delimited data row per timestep. This module reads that file and
converts it into crystal_growth_metrics.csv, matching the
`xolotl_case/crystal_growth_metrics.csv` output declared in dvc.yaml.

Column names depend on Xolotl's configuration (species tracked, material,
etc.); this parser looks columns up by name from the header rather than by
hardcoded position. Against our real W100 (tungsten PSI) configuration
(workflows/_shared/xolotl/params.jinja2), a real run produces:

    #time fluence Helium_content Vacancy_content Interstitial_content
    Helium_bulk Vacancy_bulk Interstitial_bulk Helium_surface
    Vacancy_surface Interstitial_surface Helium_burst Deuterium_burst
    Tritium_burst

Column mapping, determined by inspecting real output (not guessed):
  - `time`           -> `time`, directly.
  - `defect_density` -> `Vacancy_content + Interstitial_content`. This is a
    physically sound mapping: vacancies and interstitials are exactly the
    point defects being tracked, not an approximation.
  - `thickness`      -> `fluence`. Xolotl/W100 models species *retention*
    within a fixed-thickness substrate (its actual PSI/fusion-materials
    purpose), not epitaxial layer growth, so there is no literal thickness
    column to read. Cumulative fluence (particle arrival, monotonically
    increasing) is the closest available proxy. This is an explicit
    placeholder pending real growth-rate physics, not a validated
    fluence-to-thickness conversion.
"""

from __future__ import annotations

import csv
from pathlib import Path

XOLOTL_OUTPUT_FILENAME = "retentionOut.txt"

CSV_FIELDNAMES = ("time", "thickness", "defect_density")

_TIME_COLUMN = "time"
_THICKNESS_PROXY_COLUMN = "fluence"
_DEFECT_COLUMNS = ("Vacancy_content", "Interstitial_content")


def _parse_header(header_line: str) -> dict[str, int]:
    """Map column name -> index from Xolotl's `#`-prefixed header line."""
    names = header_line.lstrip("#").split()
    return {name: index for index, name in enumerate(names)}


def _parse_retention_file(retention_path: Path) -> list[dict[str, float]]:
    """Parse Xolotl's retentionOut.txt into rows of
    (time, thickness, defect_density), mapping columns by name (see module
    docstring) rather than assuming a fixed column layout.
    """
    rows: list[dict[str, float]] = []
    column_index: dict[str, int] | None = None

    with open(retention_path) as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("#"):
                column_index = _parse_header(line)
                continue

            if column_index is None:
                raise ValueError(
                    f"{retention_path}:{line_no}: data row before header line: {line!r}"
                )

            columns = line.split()
            required = {_TIME_COLUMN, _THICKNESS_PROXY_COLUMN, *_DEFECT_COLUMNS}
            missing = required - column_index.keys()
            if missing:
                raise ValueError(
                    f"{retention_path}: header is missing expected column(s): {sorted(missing)}"
                )

            def value(name: str) -> float:
                return float(columns[column_index[name]])

            rows.append(
                {
                    "time": value(_TIME_COLUMN),
                    "thickness": value(_THICKNESS_PROXY_COLUMN),
                    "defect_density": sum(value(name) for name in _DEFECT_COLUMNS),
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
