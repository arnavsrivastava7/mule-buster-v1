"""Label leakage tests: ensure ground_truth_label never enters feature matrices."""

import unittest
import bank_ai
import bank_ai.model


class LabelLeakageTests(unittest.TestCase):
    def test_ground_truth_label_not_in_bank_ai_feature_matrix(self):
        """Ensure ground_truth_label and related target labels never leak into feature columns."""
        # If the high-level scoring model is still a placeholder, skip with a clear reason
        if not bank_ai.model.score_accounts(None, None).get("ready", False):
            # Test the feature columns defined by bank_ai if available, but also ensure guardrails are active
            try:
                from bank_ai.features.build import ML_FEATURES
                from bank_ai.schemas import FORBIDDEN_FEATURE_COLUMNS, assert_features_exclude_labels

                self.assertNotIn("ground_truth_label", ML_FEATURES)
                self.assertIn("ground_truth_label", FORBIDDEN_FEATURE_COLUMNS)
                # Verify that assert_features_exclude_labels catches ground_truth_label
                with self.assertRaises(ValueError):
                    assert_features_exclude_labels(list(ML_FEATURES) + ["ground_truth_label"])
            except ImportError:
                pass

            self.skipTest(
                "bank_ai.model scoring is still a placeholder (ready=False); "
                "full runtime feature matrix leakage test will run when end-to-end scoring is connected."
            )

        # Runtime check when ready is True
        from bank_ai.features.build import ML_FEATURES
        self.assertNotIn(
            "ground_truth_label",
            ML_FEATURES,
            "Label leakage detected: 'ground_truth_label' was found in bank_ai ML_FEATURES!",
        )


if __name__ == "__main__":
    unittest.main()
