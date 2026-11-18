"""Load configs/level1.yaml into one settings object."""

from dataclasses import dataclass, replace
from pathlib import Path

try:
    import yaml
except ImportError:
    from ruamel.yaml import YAML

    _y = YAML(typ="safe")

    class _YamlCompat:
        @staticmethod
        def safe_load(stream):
            return _y.load(stream)

    yaml = _YamlCompat()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "level1.yaml"


@dataclass(frozen=True)
class Tier:
    """One points band inside a rule. minimum and maximum are feature cutoffs."""

    points: float
    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class Config:
    """Every tunable number the Bank AI reads."""

    currency: str
    main_days: int
    recent_days: int
    baseline_days: int
    baseline_offset_days: int
    lookback_days: int
    min_txn_7d: int
    min_in_value: float
    velocity_cap: float
    dwell_cap_minutes: float
    dormancy_cap_days: float
    rule_tiers: dict
    dormancy_min_txn_count: int
    notable: dict
    ml_weight: float
    rule_weight: float
    band_medium: int
    band_high: int
    band_critical: int
    merchant_max_adjustment: int
    merchant_weights: dict
    merchant_thresholds: dict
    merchant_block: dict
    suppress_days: int
    model: dict
    snapshot_step_days: int
    detection_delay_days: int
    time_forward_days: int
    train_fraction: float
    validation_fraction: float
    high_band_target_fraction: float

    def with_bands(self, medium, high, critical):
        """Return a copy that uses band cutoffs chosen during training."""
        return replace(
            self,
            band_medium=int(medium),
            band_high=int(high),
            band_critical=int(critical),
        )


def _tiers(raw_tiers):
    return tuple(
        Tier(
            points=float(item["points"]),
            minimum=None if "minimum" not in item else float(item["minimum"]),
            maximum=None if "maximum" not in item else float(item["maximum"]),
        )
        for item in raw_tiers
    )


def load_config(path=None):
    """Read the YAML file. Missing keys raise a clear error."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    rules = raw["rules"]
    guard = raw["merchant_guard"]
    return Config(
        currency=str(raw["currency"]),
        main_days=int(raw["windows"]["main_days"]),
        recent_days=int(raw["windows"]["recent_days"]),
        baseline_days=int(raw["windows"]["baseline_days"]),
        baseline_offset_days=int(raw["windows"]["baseline_offset_days"]),
        lookback_days=int(raw["windows"]["lookback_days"]),
        min_txn_7d=int(raw["gate"]["min_txn_7d"]),
        min_in_value=float(raw["gate"]["min_in_value"]),
        velocity_cap=float(raw["caps"]["velocity_ratio"]),
        dwell_cap_minutes=float(raw["caps"]["dwell_minutes"]),
        dormancy_cap_days=float(raw["caps"]["dormancy_days"]),
        rule_tiers={name: _tiers(spec["tiers"]) for name, spec in rules.items()},
        dormancy_min_txn_count=int(rules["dormancy"]["min_txn_count"]),
        notable={key: float(value) for key, value in raw["notable"].items()},
        ml_weight=float(raw["blend"]["ml_weight"]),
        rule_weight=float(raw["blend"]["rule_weight"]),
        band_medium=int(raw["bands"]["medium"]),
        band_high=int(raw["bands"]["high"]),
        band_critical=int(raw["bands"]["critical"]),
        merchant_max_adjustment=int(guard["max_adjustment"]),
        merchant_weights={key: float(value) for key, value in guard["weights"].items()},
        merchant_thresholds={key: float(value) for key, value in guard["thresholds"].items()},
        merchant_block={key: float(value) for key, value in guard["block_if"].items()},
        suppress_days=int(raw["feedback"]["suppress_days"]),
        model=dict(raw["model"]),
        snapshot_step_days=int(raw["snapshots"]["step_days"]),
        detection_delay_days=int(raw["snapshots"]["detection_delay_days"]),
        time_forward_days=int(raw["snapshots"]["time_forward_days"]),
        train_fraction=float(raw["snapshots"]["train_fraction"]),
        validation_fraction=float(raw["snapshots"]["validation_fraction"]),
        high_band_target_fraction=float(raw["split"]["high_band_target_fraction"]),
    )
