from pathlib import Path
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "disaster_Dataset_FEATURED.csv"
MODEL_DIR = BASE_DIR / "model"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_FILE = MODEL_DIR / "all_disaster_feature_names.txt"
METRICS_FILE = MODEL_DIR / "all_disaster_model_metrics.json"


# ============================================================
# FEATURES USED BY EVERY DISASTER-SPECIFIC MODEL
# ============================================================

FEATURES = [
    # Population / severity
    "affected_population",
    "severity_score",
    "affected_area_km2",
    "vulnerability_score",
    "impact_score",
    "population_density",
    "dris_score",

    # Weather / hazard signals
    "magnitude",
    "depth",
    "rainfall",
    "rainfall_72h_mm",
    "wind_speed",
    "humidity",

    # Flood signals
    "flood_extent_km2",
    "flood_depth_m",
    "flood_velocity_ms",
    "flood_severity",

    # Wildfire / earthquake signals
    "fire_detection_count",
    "fire_frp_sum",
    "fire_frp_max",
    "earthquake_count",

    # Access / logistics
    "road_blockage_probability",
    "logistics_accessibility_score",

    # Engineered features
    "affected_population_ratio",
    "demographic_vulnerability_index",
    "infrastructure_damage_index",
    "logistics_difficulty_index",
    "vulnerability_load",
    "flood_intensity_index",
    "rainfall_pressure_index",
    "response_access_index",
    "average_emergency_distance_km",
    "month",
]

TARGETS = [
    "food_demand",
    "water_demand_litres",
    "medical_kit_demand",
    "shelter_demand",
]


# ============================================================
# HELPERS
# ============================================================

def slugify_disaster_type(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
    )


def model_path_for(disaster_type: str) -> Path:
    return MODEL_DIR / f"resource_model_{slugify_disaster_type(disaster_type)}.pkl"


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 76)
print("      ALL-DISASTER RESOURCE DEMAND MODEL TRAINING")
print("=" * 76)

if not DATA_FILE.exists():
    raise FileNotFoundError(f"Dataset not found: {DATA_FILE}")

df = pd.read_csv(DATA_FILE)

missing = [c for c in FEATURES + TARGETS + ["disaster_type"] if c not in df.columns]
if missing:
    raise ValueError(
        "Required columns missing from featured dataset: " + ", ".join(missing)
    )

print(f"\nDataset records : {len(df)}")
print(f"Model features   : {len(FEATURES)}")
print(f"Target outputs   : {len(TARGETS)}")

# Save the common model feature order used by the backend.
with open(FEATURE_FILE, "w", encoding="utf-8") as file:
    for feature in FEATURES:
        file.write(feature + "\n")


disaster_types = sorted(df["disaster_type"].dropna().astype(str).unique())
print("Disaster types   :", ", ".join(disaster_types))

all_metrics = {}


# ============================================================
# TRAIN ONE MODEL FOR EACH DISASTER TYPE
# ============================================================

for disaster_type in disaster_types:

    disaster_df = df[df["disaster_type"].astype(str) == disaster_type].copy()

    # Convert model columns to numeric and fill any unexpected missing values.
    X = disaster_df[FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0)
    y = disaster_df[TARGETS].apply(pd.to_numeric, errors="coerce").fillna(0)

    if len(disaster_df) < 100:
        print(f"\nSkipping {disaster_type}: not enough records ({len(disaster_df)}).")
        continue

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
    )

    print("\n" + "-" * 76)
    print(f"Training model for: {disaster_type}")
    print(f"Records           : {len(disaster_df)}")
    print(f"Training samples  : {len(X_train)}")
    print(f"Testing samples   : {len(X_test)}")

    # Slight depth / leaf limits keep files manageable while preserving strong performance.
    model = RandomForestRegressor(
        n_estimators=60,
        max_depth=22,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=-1,
    )

    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    disaster_metrics = {}

    for i, target in enumerate(TARGETS):
        actual = y_test.iloc[:, i]
        predicted = predictions[:, i]

        r2 = r2_score(actual, predicted)
        mae = mean_absolute_error(actual, predicted)
        rmse = np.sqrt(mean_squared_error(actual, predicted))

        disaster_metrics[target] = {
            "R2": float(r2),
            "MAE": float(mae),
            "RMSE": float(rmse),
        }

        print(
            f"{target:<26} "
            f"R2={r2:.4f}  MAE={mae:.2f}  RMSE={rmse:.2f}"
        )

    out_path = model_path_for(disaster_type)
    with open(out_path, "wb") as file:
        pickle.dump(model, file)

    print(f"Saved model       : {out_path.name}")

    all_metrics[disaster_type] = {
        "records": int(len(disaster_df)),
        "training_samples": int(len(X_train)),
        "testing_samples": int(len(X_test)),
        "metrics": disaster_metrics,
    }


with open(METRICS_FILE, "w", encoding="utf-8") as file:
    json.dump(all_metrics, file, indent=4)

print("\n" + "=" * 76)
print("ALL DISASTER MODELS TRAINED SUCCESSFULLY")
print("=" * 76)
print("Feature list :", FEATURE_FILE.name)
print("Metrics      :", METRICS_FILE.name)
