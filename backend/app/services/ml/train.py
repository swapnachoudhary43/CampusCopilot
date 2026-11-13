"""Train TF-IDF classifiers and write the real evaluation files.

The vectorizer is fit on the training split only. Identical complaint texts
are rejected so a sentence cannot appear on both sides of the split.
"""

import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC

from app.constants import COMPLAINT_CATEGORIES


def _scores(y_true, y_pred, labels: list[str]) -> dict:
    report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0, labels=labels)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0, labels=labels)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0, labels=labels)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0, labels=labels)),
        "per_class": report,
        "confusion_matrix": matrix.astype(int).tolist(),
        "labels": labels,
    }


def train_from_frame(frame, output_dir: Path, random_state: int = 42, test_size: float = 0.2) -> dict:
    import joblib
    import sklearn

    labels = list(COMPLAINT_CATEGORIES)
    texts = frame["text"].astype(str).str.strip()
    categories = frame["category"].astype(str).str.strip()
    if texts.duplicated().any():
        raise ValueError("Duplicate complaint texts would leak across the train/test split.")
    unknown = sorted(set(categories) - set(labels))
    if unknown:
        raise ValueError(f"Unknown categories in the dataset: {unknown}")

    train_text, test_text, train_y, test_y = train_test_split(
        texts,
        categories,
        test_size=test_size,
        random_state=random_state,
        stratify=categories,
    )
    if set(train_text) & set(test_text):
        raise RuntimeError("Data leakage: the same text is in the train and test splits.")

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    x_train = vectorizer.fit_transform(train_text)
    x_test = vectorizer.transform(test_text)

    candidates = {
        "logistic_regression": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=random_state,
        ),
        "linear_svc": LinearSVC(
            class_weight="balanced",
            random_state=random_state,
            max_iter=5000,
        ),
    }
    results = {}
    fitted = {}
    for name, model in candidates.items():
        model.fit(x_train, train_y)
        predictions = model.predict(x_test)
        results[name] = _scores(test_y, predictions, labels)
        fitted[name] = model

    # Prefer logistic regression when it is within 0.02 macro F1.
    # Its predict_proba values are easier to explain than an SVM margin.
    best_name = max(results, key=lambda name: results[name]["f1_macro"])
    chosen = best_name
    if (
        best_name != "logistic_regression"
        and results["logistic_regression"]["f1_macro"] >= results[best_name]["f1_macro"] - 0.02
    ):
        chosen = "logistic_regression"
        choice_reason = (
            "Logistic regression was deployed because its macro F1 is within 0.02 of the "
            "best model and it can report a class probability."
        )
    elif chosen == "logistic_regression":
        if abs(results["logistic_regression"]["f1_macro"] - results["linear_svc"]["f1_macro"]) < 1e-9:
            choice_reason = (
                "Logistic regression and linear SVM had the same macro F1. "
                "Logistic regression was deployed because it can report a class probability."
            )
        else:
            choice_reason = "Logistic regression had the higher macro F1 and was deployed."
    else:
        choice_reason = (
            "Linear SVM had a clearly higher macro F1 and was deployed. "
            "Its confidence score is a softmax of decision margins, not a probability."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "vectorizer": vectorizer,
        "model": fitted[chosen],
        "model_name": chosen,
        "labels": labels,
    }
    joblib.dump(bundle, output_dir / "deployed.joblib")
    joblib.dump(fitted["logistic_regression"], output_dir / "logreg.joblib")
    joblib.dump(fitted["linear_svc"], output_dir / "linearsvc.joblib")
    joblib.dump(vectorizer, output_dir / "vectorizer.joblib")

    distribution = {label: int((categories == label).sum()) for label in labels}
    metrics = {
        "dataset": "synthetic_project_authored",
        "rows": int(len(frame)),
        "train_size": int(len(train_text)),
        "test_size": int(len(test_text)),
        "test_fraction": test_size,
        "random_state": random_state,
        "stratified": True,
        "vectorizer_fit_on": "training_split_only",
        "class_weight": "balanced",
        "features": "tfidf_word_unigrams_and_bigrams",
        "class_distribution": distribution,
        "models": results,
        "deployed_model": chosen,
        "selection_reason": choice_reason,
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics
