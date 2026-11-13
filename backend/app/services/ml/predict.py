"""Load the saved complaint classifier and score new text.

The vectorizer and classifier are loaded from models/deployed.joblib, which
is produced by scripts/train_model.py. Nothing here refits the vectorizer.
"""

from functools import lru_cache

import numpy as np

from app.core.config import get_settings


class ModelNotReady(Exception):
    """Raised when the training script has not been run yet."""


def model_path():
    return get_settings().model_dir / "deployed.joblib"


def metrics_path():
    return get_settings().model_dir / "metrics.json"


@lru_cache
def _load_bundle(path_text: str, modified: float):
    import joblib

    return joblib.load(path_text)


def load_bundle():
    path = model_path()
    if not path.exists():
        raise ModelNotReady(
            "The complaint classifier has not been trained. Run: python scripts/train_model.py"
        )
    return _load_bundle(str(path), path.stat().st_mtime)


def clear_model_cache() -> None:
    _load_bundle.cache_clear()


def predict_category(text: str) -> dict:
    bundle = load_bundle()
    vectorizer = bundle["vectorizer"]
    model = bundle["model"]
    features = vectorizer.transform([text])
    label = str(model.predict(features)[0])
    confidence = None
    confidence_type = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(features)[0]
        confidence = float(np.max(probabilities))
        confidence_type = "predicted_class_probability"
    elif hasattr(model, "decision_function"):
        margins = np.asarray(model.decision_function(features)[0], dtype=float)
        # A larger margin means the model is further from the decision boundary.
        # This is not a probability.
        shifted = margins - np.max(margins)
        exp_scores = np.exp(shifted)
        confidence = float(exp_scores.max() / exp_scores.sum())
        confidence_type = "softmax_of_decision_margins_not_a_probability"
    return {
        "predicted_category": label,
        "confidence": None if confidence is None else round(confidence, 4),
        "confidence_type": confidence_type,
        "model_name": bundle.get("model_name"),
    }
