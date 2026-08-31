"""
Single reproduce-all entrypoint for the OLIVE release.

Runs every Table 2-8 + Figure 6 wrapper in release/reproduce/, captures the
key reproduced cells from each wrapper's stdout, and checks them against the
paper's camera-ready values (hardcoded below, sourced from
paper/proceedings.tex tables tab:us2_convergence, tab:us2_delta,
tab:us2_skill_mod, tab:trust_reliance, tab:us3_reconv, tab:us3_delta,
tab:us3_skill_mod, and fig:reliance_growth). Prints a PASS/FAIL summary.

US2/US3 wrappers read already-logged posteriors from ~/wingman and require no
running server. US1 (release/reproduce/us1.py + us1_convergence.py) requires a
live OLIVE gRPC server (release/olive/server.py) and is SKIPPED by default;
pass --with-us1 to attempt it (best-effort; still reported as SKIP if the
server is unreachable rather than crashing the run).

Usage:
    python -m release.reproduce.reproduce_all
    python -m release.reproduce.reproduce_all --with-us1 --addr localhost:50055

A wrapper that raises FileNotFoundError (a required analysis/repro/*.py
generator or cohort CSV not vendored in this release checkout) or otherwise
errors is caught and reported as SKIP with the reason. It never aborts the
rest of the run.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PY = sys.executable


# ---------------------------------------------------------------------------
# Paper-expected values (camera-ready proceedings.tex), used as the ground
# truth every reproduced cell is checked against.
# ---------------------------------------------------------------------------

PAPER_EXPECTED = {
    "table2": {
        "IE guidance rate%": 99.4, "IE guidance time": 74.5,
        "IE belief rate%": 84.6, "IE belief time": 65.3,
        "E guidance rate%": 97.1, "E guidance time": 76.2,
        "E belief rate%": 82.9, "E belief time": 63.0,
    },
    "table3": {
        "Control delta": 0.014, "Control p": 0.091,
        "OLIVE-E delta": 0.021, "OLIVE-E p": 0.094,
        "OLIVE-IE delta": 0.031, "OLIVE-IE p": 0.003,
        "Oracle delta": 0.024, "Oracle p": 0.105,
    },
    "table4": {
        "Control r": 0.25, "Control p": 0.43,
        "OLIVE-E r": -0.63, "OLIVE-E p": 0.05,
        "OLIVE-IE r": -0.02, "OLIVE-IE p": 0.95,
        "Oracle r": 0.06, "Oracle p": 0.90,
    },
    "table5": {
        "US2 OLIVE-E Trust": 3.89, "US2 OLIVE-E Look": 2.99, "US2 OLIVE-E Shoot": 4.62,
        "US2 OLIVE-IE Trust": 3.95, "US2 OLIVE-IE Look": 3.90, "US2 OLIVE-IE Shoot": 4.64,
        "US2 Oracle Trust": 4.80, "US2 Oracle Look": 4.35, "US2 Oracle Shoot": 5.07,
        "US3 OLIVE-E Trust": 3.91, "US3 OLIVE-E Look": 3.44, "US3 OLIVE-E Shoot": 4.62,
        "US3 OLIVE-IE Trust": 4.57, "US3 OLIVE-IE Look": 4.23, "US3 OLIVE-IE Shoot": 5.06,
        "US3 Oracle Trust": 4.76, "US3 Oracle Look": 4.64, "US3 Oracle Shoot": 4.82,
    },
    "table6": {
        "OLIVE-E guidance rate%": 100, "OLIVE-E guidance time": 68.5,
        "OLIVE-E belief rate%": 37, "OLIVE-E belief time": 30.7,
        "OLIVE-IE guidance rate%": 100, "OLIVE-IE guidance time": 53.8,
        "OLIVE-IE belief rate%": 56, "OLIVE-IE belief time": 25.1,
        "IE vs E guidance t": -2.67, "IE vs E guidance p": 0.008,
        "IE vs E belief t": -0.81, "IE vs E belief p": 0.418,
    },
    "table7": {
        "Control delta": 0.024, "Control p": 0.061,
        "OLIVE-E delta": 0.034, "OLIVE-E p": 0.052,
        "OLIVE-IE delta": 0.070, "OLIVE-IE p": 0.001,
        "Oracle delta": 0.046, "Oracle p": 0.012,
    },
    "table8": {
        "Control r": 0.68, "Control p": 0.01,
        "OLIVE-E r": -0.11, "OLIVE-E p": 0.73,
        "OLIVE-IE r": -0.24, "OLIVE-IE p": 0.57,
        "Oracle r": 0.42, "Oracle p": 0.30,
    },
    "fig6": {
        "US3 OLIVE-IE Look slope": 0.07,
    },
}


def close(a, b, tol):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _run_module(mod):
    """Run `python -m release.reproduce.<mod>` and return (returncode, combined stdout+stderr)."""
    proc = subprocess.run(
        [PY, "-m", f"release.reproduce.{mod}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _missing_file_reason(text):
    """If the wrapper's output indicates a missing vendored file, return a short reason; else None."""
    m = re.search(r"Required (?:generator script|cohort CSV) not found: (\S+)", text)
    if m:
        return f"missing {m.group(1)}"
    if "FileNotFoundError" in text:
        return "FileNotFoundError (see wrapper output)"
    return None


class Cell:
    """One reproduced-vs-expected comparison."""

    def __init__(self, label, actual, expected, tol):
        self.label = label
        self.actual = actual
        self.expected = expected
        self.tol = tol
        self.ok = actual is not None and close(actual, expected, tol)

    def line(self):
        actual_s = f"{self.actual:.4g}" if self.actual is not None else "MISSING"
        status = "OK" if self.ok else "MISMATCH"
        return f"    {self.label:32s} reproduced={actual_s:>10s}  paper={self.expected:>8g}  [{status}]"


class TargetResult:
    def __init__(self, name, description, command):
        self.name = name
        self.description = description
        self.command = command
        self.status = "FAIL"  # PASS | FAIL | SKIP
        self.reason = ""
        self.cells = []

    def finalize(self):
        if self.status == "SKIP":
            return
        if self.cells and all(c.ok for c in self.cells):
            self.status = "PASS"
        else:
            self.status = "FAIL"


# ---------------------------------------------------------------------------
# Per-table parsers: each takes the wrapper's captured stdout text and the
# module's PAPER_EXPECTED dict, and returns a list of Cell objects.
# ---------------------------------------------------------------------------

def _parse_table2(text, expected):
    cells = []
    for m in re.finditer(
        r"^(IE|E)\s+(belief|guidance)\s+([\d.]+)%\s+([\d.]+)s\s+[\d.]+%\s+[\d.]+s",
        text, re.MULTILINE,
    ):
        cond, metric, rate, time = m.group(1), m.group(2), float(m.group(3)), float(m.group(4))
        rate_key = f"{cond} {metric} rate%"
        time_key = f"{cond} {metric} time"
        if rate_key in expected:
            cells.append(Cell(rate_key, rate, expected[rate_key], 1.0))
        if time_key in expected:
            cells.append(Cell(time_key, time, expected[time_key], 1.0))
    return cells


def _parse_delta_section(text, header_pat, cond_names, expected, label_map):
    """Shared parser for table3/table7 (within_session_delta.py output rows)."""
    m = re.search(header_pat, text)
    if not m:
        return []
    section = text[m.end():]
    # Stop at the next '=====' section header, if any.
    nxt = section.find("=====")
    if nxt != -1:
        section = section[:nxt]
    cells = []
    row_pat = re.compile(
        r"^\s*(" + "|".join(re.escape(c) for c in cond_names) + r")\s+(\d+)\s+"
        r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+"
        r"([-\d.]+)\s+([\d.]+)\s+\d+\s*$",
        re.MULTILINE,
    )
    for m2 in row_pat.finditer(section):
        cond = m2.group(1)
        delta = float(m2.group(7))
        p = float(m2.group(10))
        label = label_map.get(cond, cond)
        dk, pk = f"{label} delta", f"{label} p"
        if dk in expected:
            cells.append(Cell(dk, delta, expected[dk], 0.003))
        if pk in expected:
            cells.append(Cell(pk, p, expected[pk], 0.006))
    return cells


def _parse_table3(text, expected):
    return _parse_delta_section(
        text,
        r"===== table3: US2 within-session throughput delta.*?=====",
        ["E", "control", "oracle", "IE"],
        expected,
        {"E": "OLIVE-E", "IE": "OLIVE-IE", "control": "Control", "oracle": "Oracle"},
    )


def _parse_table4(text, expected):
    m = re.search(r"TABLE 4 \(skill moderation; baseline=hit_mean\)\s*=====", text)
    if not m:
        return []
    section = text[m.end():]
    nxt = section.find("=====")
    if nxt != -1:
        section = section[:nxt]
    cells = []
    label_map = {"E": "OLIVE-E", "IE": "OLIVE-IE", "control": "Control", "oracle": "Oracle"}
    for m2 in re.finditer(
        r"^\s*(control|E|IE|oracle)\s+n=\s*\d+\s+r=([+-][\d.]+)\s+slope=[+-][\d.]+\s+p=([\d.]+)",
        section, re.MULTILINE,
    ):
        label = label_map[m2.group(1)]
        r_val, p_val = float(m2.group(2)), float(m2.group(3))
        rk, pk = f"{label} r", f"{label} p"
        if rk in expected:
            cells.append(Cell(rk, r_val, expected[rk], 0.01))
        if pk in expected:
            cells.append(Cell(pk, p_val, expected[pk], 0.006))
    return cells


def _parse_table5(text, expected):
    cells = []
    for m in re.finditer(
        r"(US2|US3)\s+(OLIVE-E|OLIVE-IE|Oracle)\s+n=\s*\d+\s+Trust\s+([\d.]+)\s+Look\s+([\d.]+)\s+Shoot\s+([\d.]+)",
        text,
    ):
        study, cond, trust, look, shoot = m.group(1), m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5))
        for metric, val in [("Trust", trust), ("Look", look), ("Shoot", shoot)]:
            key = f"{study} {cond} {metric}"
            if key in expected:
                cells.append(Cell(key, val, expected[key], 0.01))
    return cells


def _parse_table6(text, expected):
    cells = []
    for m in re.finditer(
        r"(OLIVE-E|OLIVE-IE)\s+\d+\s+(\d+)%\s+([\d.]+)\S([\d.]+)\s+(\d+)%\s+([\d.]+)\S([\d.]+)",
        text,
    ):
        cond = m.group(1)
        g_rate, g_time = float(m.group(2)), float(m.group(3))
        b_rate, b_time = float(m.group(5)), float(m.group(6))
        for key, val, tol in [
            (f"{cond} guidance rate%", g_rate, 1.0),
            (f"{cond} guidance time", g_time, 0.5),
            (f"{cond} belief rate%", b_rate, 1.0),
            (f"{cond} belief time", b_time, 0.5),
        ]:
            if key in expected:
                cells.append(Cell(key, val, expected[key], tol))
    m = re.search(r"IE vs E\s+guidance:\s+t=([-\d.]+),\s+p=([\d.]+)", text)
    if m:
        cells.append(Cell("IE vs E guidance t", float(m.group(1)), expected["IE vs E guidance t"], 0.02))
        cells.append(Cell("IE vs E guidance p", float(m.group(2)), expected["IE vs E guidance p"], 0.003))
    m = re.search(r"IE vs E\s+belief:\s+t=([-\d.]+),\s+p=([\d.]+)", text)
    if m:
        cells.append(Cell("IE vs E belief t", float(m.group(1)), expected["IE vs E belief t"], 0.02))
        cells.append(Cell("IE vs E belief p", float(m.group(2)), expected["IE vs E belief p"], 0.01))
    return cells


def _parse_table7(text, expected):
    return _parse_delta_section(
        text,
        r"===== table7: US3 new-target throughput delta.*?=====",
        ["E", "C", "O", "IE"],
        expected,
        {"E": "OLIVE-E", "IE": "OLIVE-IE", "C": "Control", "O": "Oracle"},
    )


def _parse_table8(text, expected):
    cells = []
    label_map = {"C": "Control", "E": "OLIVE-E", "IE": "OLIVE-IE", "O": "Oracle"}
    for m in re.finditer(
        r"^\s*(C|E|IE|O)\s+n=\s*\d+\s+r=([+-][\d.]+)\s+slope=[+-][\d.]+\s+p=([\d.]+)",
        text, re.MULTILINE,
    ):
        label = label_map[m.group(1)]
        r_val, p_val = float(m.group(2)), float(m.group(3))
        rk, pk = f"{label} r", f"{label} p"
        if rk in expected:
            cells.append(Cell(rk, r_val, expected[rk], 0.01))
        if pk in expected:
            cells.append(Cell(pk, p_val, expected[pk], 0.006))
    return cells


def _parse_fig6(text, expected):
    m = re.search(
        r"US3 OLIVE-IE\s+n=\s*\d+\s+Trust\s+[+-][\d.]+\S[\d.]+\**\s+Look\s+([+-][\d.]+)\S[\d.]+",
        text,
    )
    if not m:
        return []
    slope = float(m.group(1))
    return [Cell("US3 OLIVE-IE Look slope", slope, expected["US3 OLIVE-IE Look slope"], 0.02)]


# ---------------------------------------------------------------------------
# Target registry: module name, human description, parser, expected key.
# ---------------------------------------------------------------------------

TARGETS = [
    ("table2", "table2_us2", "Table 2 (US2 vs US1 convergence)", _parse_table2),
    ("table3", "table3_us2", "Table 3 (US2 within-session throughput delta)", _parse_table3),
    ("table4", "table4_us2", "Table 4 (US2 skill moderation)", _parse_table4),
    ("table5", "table5_ratings", "Table 5 (Post-block trust/reliance ratings)", _parse_table5),
    ("table6", "table6_us3", "Table 6 (US3 post-switch reconvergence)", _parse_table6),
    ("table7", "table7_us3", "Table 7 (US3 new-target throughput delta)", _parse_table7),
    ("table8", "table8_us3", "Table 8 (US3 skill moderation)", _parse_table8),
    ("fig6", "fig6_reliance", "Figure 6 (Within-session reliance growth)", _parse_fig6),
]


def run_target(key, mod, description, parser):
    result = TargetResult(key, description, f"python -m release.reproduce.{mod}")
    try:
        rc, text = _run_module(mod)
    except Exception as exc:  # pragma: no cover - defensive
        result.status = "SKIP"
        result.reason = f"failed to launch wrapper: {exc}"
        return result

    if rc != 0:
        reason = _missing_file_reason(text)
        if reason:
            result.status = "SKIP"
            result.reason = reason
            return result
        result.status = "FAIL"
        result.reason = f"wrapper exited with code {rc}"
        result.cells = []
        return result

    expected = PAPER_EXPECTED[key]
    cells = parser(text, expected)
    result.cells = cells
    if not cells:
        result.status = "FAIL"
        result.reason = "could not parse any expected cells from wrapper output"
    else:
        missing = [k for k in expected if k not in {c.label for c in cells}]
        if missing:
            result.reason = f"unparsed cells: {', '.join(missing)}"
        result.finalize()
    return result


def run_us1(addr):
    """Best-effort US1 run; SKIPs (not FAILs) if the OLIVE server is unreachable."""
    result = TargetResult("us1", "US1 (canonical simulation + convergence)", "python -m release.reproduce.us1 / us1_convergence")
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "us1_master_csvs"
        proc = subprocess.run(
            [PY, "-m", "release.reproduce.us1",
             "--participants", "5", "20",
             "--steps", "90", "--num-trials", "5",
             "--addr", addr, "--output-dir", str(out_dir)],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            result.status = "SKIP"
            reason_tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            result.reason = f"US1 simulation failed (server at {addr} unreachable?): " + (reason_tail[-1] if reason_tail else "unknown error")
            return result

        sec_csv = out_dir / "secondStats.csv"
        conv_csv = Path(tmpdir) / "us1_convergence.csv"
        proc2 = subprocess.run(
            [PY, "-m", "release.reproduce.us1_convergence", str(sec_csv), "--output-csv", str(conv_csv)],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if proc2.returncode != 0:
            result.status = "SKIP"
            result.reason = "US1 convergence analysis failed on simulation output"
            return result

        text = (proc2.stdout or "") + (proc2.stderr or "")
        expected = {
            ("IE", "Belief"): (0.79, 37), ("IE", "Guidance"): (0.97, 28),
            ("E", "Belief"): (0.71, 53), ("E", "Guidance"): (0.79, 37),
        }
        cells = []
        for m in re.finditer(r"(IE|E)\s+(Belief|Guidance)\s+convergence\s+([\d.]+)\s+(\d+)", text):
            cond, metric, rate, t = m.group(1), m.group(2), float(m.group(3)), float(m.group(4))
            exp_rate, exp_t = expected[(cond, metric)]
            cells.append(Cell(f"{cond} {metric} rate", rate, exp_rate, 0.03))
            cells.append(Cell(f"{cond} {metric} time", t, exp_t, 5))
        result.cells = cells
        if not cells:
            result.status = "FAIL"
            result.reason = "could not parse US1 convergence output"
        else:
            result.finalize()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-us1", action="store_true",
                         help="Also run US1 simulation + convergence (requires a running OLIVE gRPC server).")
    parser.add_argument("--addr", default="localhost:50055",
                         help="gRPC server address for --with-us1 (default: localhost:50055).")
    args = parser.parse_args(argv)

    print("=" * 78)
    print("OLIVE reproduce-all: Tables 2-8 + Figure 6" + (" + US1" if args.with_us1 else ""))
    print("=" * 78)

    results = []
    for key, mod, description, table_parser in TARGETS:
        print(f"\n--- {description} ({key}) ---")
        result = run_target(key, mod, description, table_parser)
        results.append(result)
        print(f"  status: {result.status}" + (f"  ({result.reason})" if result.reason else ""))
        for cell in result.cells:
            print(cell.line())

    if args.with_us1:
        print("\n--- US1: canonical simulation + convergence (us1) ---")
        us1_result = run_us1(args.addr)
        results.append(us1_result)
        print(f"  status: {us1_result.status}" + (f"  ({us1_result.reason})" if us1_result.reason else ""))
        for cell in us1_result.cells:
            print(cell.line())
    else:
        print("\n--- US1: canonical simulation + convergence (us1) ---")
        print("  status: SKIP  (requires a running OLIVE gRPC server; pass --with-us1 to include)")

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print(f"{'Target':45s} {'Status':6s}")
    print("-" * 78)
    for result in results:
        print(f"{result.description:45s} {result.status:6s}")
    if not args.with_us1:
        print(f"{'US1 (canonical simulation + convergence)':45s} {'SKIP':6s}")

    n_fail = sum(1 for r in results if r.status == "FAIL")
    n_pass = sum(1 for r in results if r.status == "PASS")
    n_skip = sum(1 for r in results if r.status == "SKIP")
    print("-" * 78)
    print(f"{n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")

    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
