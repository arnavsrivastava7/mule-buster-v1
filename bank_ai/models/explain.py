"""Model explainability using SHAP TreeExplainer.

Extracts top positive feature contributions for each scored account to
generate grounded, evidence-backed reason codes.
"""

from typing import List, Dict, Any, Union
import numpy as np
import pandas as pd
import shap

from bank_ai.features.build import ML_FEATURES


class ModelExplainer:
    """Wrapper around SHAP TreeExplainer for LightGBM models."""

    def __init__(self, model: Any, feature_names: List[str] = list(ML_FEATURES)):
        self.model = model
        self.feature_names = feature_names
        try:
            self.explainer = shap.TreeExplainer(model)
        except Exception:
            self.explainer = None

    def top_contributors(self, X_row: Union[pd.DataFrame, pd.Series, np.ndarray], top_k: int = 3) -> List[Dict[str, Any]]:
        """Return top positive SHAP contributions for a single account feature row.

        Returns list of dicts: [{"feature": name, "shap": positive_val, "value": raw_val}, ...]
        """
        if self.explainer is None:
            return []

        # Convert row to DataFrame or 2D array if needed
        if isinstance(X_row, pd.Series):
            df_in = pd.DataFrame([X_row[self.feature_names]])
        elif isinstance(X_row, pd.DataFrame):
            df_in = X_row[self.feature_names]
        elif hasattr(X_row, "_fields") or hasattr(X_row, "_asdict"):
            df_in = pd.DataFrame([{f: float(getattr(X_row, f, 0.0)) for f in self.feature_names}])
        elif isinstance(X_row, dict):
            df_in = pd.DataFrame([{f: float(X_row.get(f, 0.0)) for f in self.feature_names}])
        else:
            df_in = pd.DataFrame(np.atleast_2d(X_row), columns=self.feature_names)

        try:
            shap_values = self.explainer.shap_values(df_in)
            # If binary classifier returns list of [neg_class_shap, pos_class_shap]
            if isinstance(shap_values, list) and len(shap_values) > 1:
                vals = shap_values[1][0]
            elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 3:
                vals = shap_values[0, :, 1]
            elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 2:
                vals = shap_values[0]
            else:
                vals = np.array(shap_values).flatten()

            raw_vals = df_in.iloc[0].values
            contributions = []
            for name, s_val, r_val in zip(self.feature_names, vals, raw_vals):
                if s_val > 0.001:  # Only positive risk-increasing contributions
                    contributions.append({
                        "feature": name,
                        "shap": float(s_val),
                        "value": float(r_val),
                    })

            # Sort descending by SHAP importance
            contributions.sort(key=lambda item: item["shap"], reverse=True)
            return contributions[:top_k]
        except Exception:
            return []


def shap_top_contributors(explainer: Union[ModelExplainer, Any], X_row: Any, top_k: int = 3) -> List[Dict[str, Any]]:
    """Helper function to fetch top contributors."""
    if isinstance(explainer, ModelExplainer):
        return explainer.top_contributors(X_row, top_k=top_k)
    return []
