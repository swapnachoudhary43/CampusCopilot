"""Complaint classification scores and the saved experiment report."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.entities import User
from app.schemas.api import PredictRequest
from app.services.ml.predict import ModelNotReady, metrics_path, predict_category
from app.services.ml.priority import suggest_priority

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/metrics")
def metrics(actor: User = Depends(require_roles("admin"))):
    path = metrics_path()
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Model metrics are not available yet. Run python scripts/train_model.py.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@router.post("/predict")
def predict(
    body: PredictRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    priority = suggest_priority(body.text)
    try:
        prediction = predict_category(body.text)
    except ModelNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {**prediction, **priority}
