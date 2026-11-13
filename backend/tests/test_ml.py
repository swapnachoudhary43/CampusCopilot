"""Train the real project corpus in a temporary folder and score one sentence."""

from pathlib import Path

import pandas as pd

from app.services.ml.priority import suggest_priority
from app.services.ml.train import train_from_frame
from scripts.complaint_corpus import COMPLAINT_ROWS


def test_training_split_and_prediction(tmp_path: Path, monkeypatch):
    frame = pd.DataFrame(COMPLAINT_ROWS, columns=["text", "category"])
    metrics = train_from_frame(frame, tmp_path)
    assert metrics["train_size"] + metrics["test_size"] == metrics["rows"]
    assert metrics["vectorizer_fit_on"] == "training_split_only"
    assert metrics["stratified"] is True
    for name in ("logistic_regression", "linear_svc"):
        scores = metrics["models"][name]
        assert 0.0 <= scores["accuracy"] <= 1.0
        assert 0.0 <= scores["precision_macro"] <= 1.0
        assert 0.0 <= scores["recall_macro"] <= 1.0
        assert 0.0 <= scores["f1_macro"] <= 1.0
        assert len(scores["confusion_matrix"]) == 8
    from app.services.ml import predict as predict_module

    monkeypatch.setattr(predict_module, "model_path", lambda: tmp_path / "deployed.joblib")
    predict_module.clear_model_cache()
    predict_category = predict_module.predict_category
    prediction = predict_category("The campus bus did not arrive at the morning stop.")
    assert prediction["predicted_category"] in {row[1] for row in COMPLAINT_ROWS}
    assert prediction["model_name"] == metrics["deployed_model"]
    high = suggest_priority("There is a short circuit and an exposed wire in the lab.")
    assert high["suggested_priority"] == "high"
    assert high["priority_method"] == "rule_based"
    low = suggest_priority("I want to suggest a new notice board near the garden.")
    assert low["suggested_priority"] == "low"
