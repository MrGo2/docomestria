"""Train + GATE the live role classifier. Reads live_role_table.csv, runs
evaluate_oof (GroupKFold-by-pdf), enforces the acceptance gate, writes reports,
fits the final model artifact. Exits non-zero if the gate FAILS.

Run: /Users/carlos/.pyenv/versions/3.12.9/bin/python scripts/train_live_role_classifier.py
"""

from __future__ import annotations

import csv
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from docomestria.training.role_classifier import (  # noqa: E402
    evaluate_oof,
    feature_importances,
    fit_final_model,
    load_dataset,
    render_report_md,
)

TRAIN_DIR = ROOT / ".planning" / "extraction" / "training"
CSV_PATH = TRAIN_DIR / "live_role_table.csv"
COV_PATH = TRAIN_DIR / "live_coverage.csv"

N_SPLITS = 5
RANDOM_STATE = 0
MACRO_F1_BAR = 0.85
PER_ROLE_F1_FLOOR = 0.50
COVERAGE_OVERALL = 90.0
COVERAGE_PER_ROLE = 70.0


def main() -> int:
    df = load_dataset(CSV_PATH)
    result = evaluate_oof(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)
    imps = feature_importances(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)

    failures: list[str] = []

    macro = result["macro_f1"]
    if macro < MACRO_F1_BAR:
        failures.append(f"macro-F1 {macro:.4f} < {MACRO_F1_BAR}")

    overall = 0.0
    cov_per_role: dict[str, dict] = {}
    if not COV_PATH.exists():
        failures.append(f"coverage file missing ({COV_PATH}) — build step did not run")
    else:
        with open(COV_PATH, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["role"] == "__overall__":
                    overall = float(r["pct"])
                else:
                    cov_per_role[r["role"]] = {
                        "total": int(r["total"]),
                        "pct": float(r["pct"]),
                    }
        if overall < COVERAGE_OVERALL:
            failures.append(f"overall coverage {overall:.1f}% < {COVERAGE_OVERALL}%")
        for role, d in cov_per_role.items():
            if d["total"] > 0 and d["pct"] < COVERAGE_PER_ROLE:
                failures.append(f"role '{role}' coverage {d['pct']:.1f}% < {COVERAGE_PER_ROLE}%")

    expected_roles = {role for role, d in cov_per_role.items() if d["total"] > 0}
    for role in sorted(expected_roles):
        if role not in result["labels"]:
            failures.append(f"role '{role}' present in golden but absent from trained labels")
            continue
        f1 = result["per_class"].get(role, {}).get("f1-score", 0.0)
        if f1 <= PER_ROLE_F1_FLOOR:
            failures.append(f"role '{role}' F1 {f1:.3f} <= {PER_ROLE_F1_FLOOR}")

    (TRAIN_DIR / "live_role_model_report.md").write_text(
        render_report_md(result, imps), encoding="utf-8"
    )
    payload = {k: v for k, v in result.items() if k != "oof_pred"}
    payload["top_importances"] = imps[:40]
    payload["gate"] = {
        "macro_f1_bar": MACRO_F1_BAR,
        "coverage_overall_pct": round(overall, 2),
        "coverage_per_role": cov_per_role,
        "failures": failures,
    }
    (TRAIN_DIR / "live_role_model_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    with open(TRAIN_DIR / "live_role_model_confusion.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["true\\pred"] + result["labels"])
        for lab, row in zip(result["labels"], result["confusion"], strict=True):
            w.writerow([lab] + row)

    print(
        f"macro-F1={macro:.4f}  baseline={result['baseline_macro_f1']:.4f}  "
        f"rows={result['n_rows']}  coverage={overall:.1f}%"
    )
    if failures:
        print("GATE: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    artifact = fit_final_model(df, random_state=RANDOM_STATE)
    (TRAIN_DIR / "live_role_model.pkl").write_bytes(pickle.dumps(artifact))
    print("GATE: PASS -> live_role_model.pkl written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
