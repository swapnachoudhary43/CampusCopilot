"""Train the complaint classifiers and save metrics.json from this run."""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ml.train import train_from_frame  # noqa: E402
from scripts.complaint_corpus import COMPLAINT_ROWS  # noqa: E402


def export_csv() -> Path:
    target = ROOT / "data" / "sample_complaints" / "complaints.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(COMPLAINT_ROWS, columns=["text", "category"])
    frame.insert(0, "id", range(1, len(frame) + 1))
    frame["source"] = "synthetic_project_authored"
    frame.to_csv(target, index=False)
    return target


def main() -> None:
    csv_path = export_csv()
    frame = pd.read_csv(csv_path)
    metrics = train_from_frame(frame, ROOT / "models")
    print(f"Rows: {metrics['rows']}")
    print(f"Train: {metrics['train_size']}  Test: {metrics['test_size']}")
    print(f"Deployed model: {metrics['deployed_model']}")
    for name, scores in metrics["models"].items():
        print(
            f"{name}: accuracy={scores['accuracy']:.4f} "
            f"precision_macro={scores['precision_macro']:.4f} "
            f"recall_macro={scores['recall_macro']:.4f} "
            f"f1_macro={scores['f1_macro']:.4f}"
        )
    print(metrics["selection_reason"])


if __name__ == "__main__":
    main()
