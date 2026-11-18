"""Model training for Bank AI: Logistic Regression (Baseline 2) and LightGBM (Primary).

Enforces monotone constraints and produces calibrated risk probabilities (0-100).
"""

from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import pickle
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from lightgbm import LGBMClassifier

from bank_ai.config import Config
from bank_ai.features.build import ML_FEATURES, monotone_vector
from bank_ai.models.explain import ModelExplainer
from bank_ai.schemas import assert_features_exclude_labels


class TrainedBankAIModels:
    """Container holding trained models, scalers, and explainers."""

    def __init__(
        self,
        lgbm: LGBMClassifier,
        logreg: LogisticRegression,
        scaler: StandardScaler,
        explainer: ModelExplainer,
        feature_names: Tuple[str, ...] = ML_FEATURES,
        best_threshold: float = 0.5,
    ):
        self.lgbm = lgbm
        self.logreg = logreg
        self.scaler = scaler
        self.explainer = explainer
        self.feature_names = list(feature_names)
        self.best_threshold = best_threshold

    def predict_lgbm_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict risk probability (0.0 to 1.0) using primary LightGBM model."""
        features_df = X[self.feature_names].fillna(0.0)
        return self.lgbm.predict_proba(features_df)[:, 1]

    def predict_logreg_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict risk probability (0.0 to 1.0) using baseline Logistic Regression."""
        features_df = X[self.feature_names].fillna(0.0)
        X_scaled = self.scaler.transform(features_df)
        return self.logreg.predict_proba(X_scaled)[:, 1]


def train_models(
    train_df: pd.DataFrame,
    cfg: Config,
    val_df: Optional[pd.DataFrame] = None,
) -> TrainedBankAIModels:
    """Train Logistic Regression and LightGBM models according to Section 5 specifications.

    LightGBM settings:
    - n_estimators: ~300
    - learning_rate: 0.05
    - num_leaves: 15
    - min_child_samples: 30
    - subsample: 0.8
    - monotone_constraints: velocity, pass-through, fan-in, fan-out, dormancy shock, new-payee are +1; dwell is -1
    - scale_pos_weight: sqrt(neg/pos)
    """
    assert_features_exclude_labels(ML_FEATURES)

    X_train = train_df[list(ML_FEATURES)].fillna(0.0)
    y_train = train_df["target"].values

    # Imbalance scale_pos_weight: sqrt(neg / max(1, pos))
    pos_count = int(np.sum(y_train == 1))
    neg_count = int(np.sum(y_train == 0))
    if pos_count > 0:
        scale_pos = float(np.sqrt(neg_count / pos_count))
    else:
        scale_pos = 1.0

    # 1. Train Baseline #2: Logistic Regression (scaled features, balanced)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    logreg = LogisticRegression(
        class_weight="balanced",
        max_iter=cfg.model.get("logreg_max_iter", 500),
        random_state=42,
    )
    logreg.fit(X_train_scaled, y_train)

    # 2. Train Primary: LightGBM with Monotone Constraints
    mono_vec = monotone_vector()
    # LightGBM accepts monotone constraints as comma-separated string or list
    lgbm = LGBMClassifier(
        n_estimators=cfg.model.get("n_estimators", 300),
        learning_rate=cfg.model.get("learning_rate", 0.05),
        num_leaves=cfg.model.get("num_leaves", 15),
        min_child_samples=min(cfg.model.get("min_child_samples", 30), max(5, len(X_train) // 10)),
        subsample=cfg.model.get("subsample", 0.8),
        colsample_bytree=cfg.model.get("colsample_bytree", 0.8),
        scale_pos_weight=scale_pos,
        monotone_constraints=mono_vec,
        random_state=42,
        verbosity=-1,
    )
    lgbm.fit(X_train, y_train)

    # 3. Create SHAP Explainer
    explainer = ModelExplainer(lgbm, list(ML_FEATURES))

    # 4. Calibration / High cutoff selection on validation set
    threshold = 0.5
    if val_df is not None and len(val_df) > 0:
        val_probs = lgbm.predict_proba(val_df[list(ML_FEATURES)].fillna(0.0))[:, 1]
        target_pct = (1.0 - cfg.high_band_target_fraction) * 100
        threshold = float(np.percentile(val_probs, target_pct))
        threshold = max(0.40, min(0.90, threshold))

    return TrainedBankAIModels(
        lgbm=lgbm,
        logreg=logreg,
        scaler=scaler,
        explainer=explainer,
        best_threshold=threshold,
    )


def save_artifacts(models: TrainedBankAIModels, save_dir: Path) -> Path:
    """Save trained model artifacts to disk."""
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    out_file = save_dir / "bank_ai_models.pkl"
    with open(out_file, "wb") as f:
        pickle.dump(models, f)
    return out_file


def load_artifacts(file_path: Path) -> TrainedBankAIModels:
    """Load model artifacts from disk."""
    with open(file_path, "rb") as f:
        models = pickle.load(f)
    return models
