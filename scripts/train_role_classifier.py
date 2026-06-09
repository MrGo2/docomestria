#!/usr/bin/env python3
"""Train the Job-A role classifier from role_table.csv and write model + report.

Usage:  python3 scripts/train_role_classifier.py
Deterministic: fixed random_state, unshuffled GroupKFold.
"""
from __future__ import annotations

import csv
import json
import pickle
from pathlib import Path

from docomestria.training.role_classifier import (
    load_dataset, evaluate_oof, feature_importances, fit_final_model, render_report_md,
)

ROOT = Path(__file__).resolve().parents[1]
TRAIN_DIR = ROOT / ".planning" / "extraction" / "training"
CSV_PATH = TRAIN_DIR / "role_table.csv"
N_SPLITS = 5
RANDOM_STATE = 0


def main() -> int:
    df = load_dataset(CSV_PATH)
    result = evaluate_oof(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)
    imps = feature_importances(df, n_splits=N_SPLITS, random_state=RANDOM_STATE)

    # report.md
    (TRAIN_DIR / "role_model_report.md").write_text(
        render_report_md(result, imps), encoding="utf-8")
    # report.json (drop the bulky oof_pred from the JSON headline)
    json_payload = {k: v for k, v in result.items() if k != "oof_pred"}
    json_payload["top_importances"] = imps[:40]
    (TRAIN_DIR / "role_model_report.json").write_text(
        json.dumps(json_payload, indent=2, sort_keys=True), encoding="utf-8")
    # confusion.csv
    with open(TRAIN_DIR / "role_model_confusion.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["true\\pred"] + result["labels"])
        for lab, row in zip(result["labels"], result["confusion"]):
            w.writerow([lab] + row)
    # final model
    artifact = fit_final_model(df, random_state=RANDOM_STATE)
    (TRAIN_DIR / "role_model.pkl").write_bytes(pickle.dumps(artifact))

    print(f"macro-F1={result['macro_f1']:.4f}  "
          f"baseline={result['baseline_macro_f1']:.4f}  "
          f"delta={result['macro_f1'] - result['baseline_macro_f1']:+.4f}  "
          f"rows={result['n_rows']} (dropped {result['n_dropped_dups']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
