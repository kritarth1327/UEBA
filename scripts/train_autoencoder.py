import json
import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "daily_behavior_profiles.csv"
ARTIFACT_DIR = ROOT / "backend" / "artifacts"

MODEL_PATH = ARTIFACT_DIR / "dense_autoencoder.pt"
SCALER_PATH = ARTIFACT_DIR / "autoencoder_scaler.joblib"
THRESHOLD_PATH = ARTIFACT_DIR / "autoencoder_threshold.json"
METADATA_PATH = ARTIFACT_DIR / "autoencoder_metadata.json"

FEATURES = [
    "logon_count",
    "after_hours_logons",
    "file_copied_removable",
    "email_count",
    "email_external_count",
    "email_attachment_count",
    "http_request_count",
    "http_after_hours_count",
    "removable_device_events",
    "total_session_duration",
]

SEED = 42
BATCH_SIZE = 1024
MAX_EPOCHS = 40
PATIENCE = 5
LEARNING_RATE = 0.001
THRESHOLD_PERCENTILE = 99.0

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
elif (
    hasattr(torch.backends, "mps")
    and torch.backends.mps.is_available()
):
    DEVICE = torch.device("mps")
else:
    DEVICE = torch.device("cpu")

print(f"Using device: {DEVICE}")


# --------------------------------------------------
# Model architecture
# --------------------------------------------------

class DenseAutoencoder(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
        )

        self.decoder = nn.Sequential(
            nn.Linear(8, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, input_dim),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


def reconstruction_errors(model, values, batch_size=4096):
    """Return one mean-squared reconstruction error per row."""
    model.eval()
    errors = []

    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            batch = torch.as_tensor(
                values[start:start + batch_size],
                dtype=torch.float32,
                device=DEVICE,
            )
            reconstructed = model(batch)
            batch_errors = torch.mean(
                (batch - reconstructed) ** 2,
                dim=1,
            )
            errors.extend(batch_errors.cpu().numpy().tolist())

    return np.asarray(errors, dtype=np.float64)


# --------------------------------------------------
# Load and validate the dataset
# --------------------------------------------------

if not DATA_PATH.exists():
    raise FileNotFoundError(
        f"Processed dataset not found: {DATA_PATH}\n"
        "Run the CERT preprocessing script first."
    )

ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA_PATH, parse_dates=["date"])

required_columns = ["user_id", "date", *FEATURES]
missing = sorted(set(required_columns) - set(df.columns))

if missing:
    raise ValueError(f"Missing required columns: {missing}")

if df.empty:
    raise ValueError("The processed dataset is empty.")

if df[FEATURES].isna().any().any():
    raise ValueError("Feature columns contain missing values.")

if (df[FEATURES] < 0).any().any():
    raise ValueError(
        "Features contain negative values; inspect preprocessing first."
    )

df = df.sort_values(["date", "user_id"]).reset_index(drop=True)

# Keep each calendar date entirely within one split.
unique_dates = np.array(sorted(df["date"].dt.normalize().unique()))

if len(unique_dates) < 10:
    raise ValueError("Not enough distinct dates for chronological splitting.")

train_end = int(len(unique_dates) * 0.70)
validation_end = int(len(unique_dates) * 0.85)

train_dates = set(unique_dates[:train_end])
validation_dates = set(unique_dates[train_end:validation_end])
test_dates = set(unique_dates[validation_end:])

date_values = df["date"].dt.normalize()

train_df = df[date_values.isin(train_dates)].copy()
validation_df = df[date_values.isin(validation_dates)].copy()
test_df = df[date_values.isin(test_dates)].copy()

print("\nDataset summary")
print("------------------------------")
print(f"Total profiles: {len(df):,}")
print(f"Unique users: {df['user_id'].nunique():,}")
print(f"Training profiles: {len(train_df):,}")
print(f"Validation profiles: {len(validation_df):,}")
print(f"Test profiles: {len(test_df):,}")
print(f"Training dates: {train_df['date'].min()} to {train_df['date'].max()}")
print(
    "Validation dates: "
    f"{validation_df['date'].min()} to {validation_df['date'].max()}"
)
print(f"Test dates: {test_df['date'].min()} to {test_df['date'].max()}")


# --------------------------------------------------
# Transform features and fit scaler on training data
# --------------------------------------------------

# Counts and durations are nonnegative. log1p reduces the influence
# of extremely large values while preserving zero values.
X_train_raw = np.log1p(train_df[FEATURES].to_numpy(dtype=np.float32))
X_val_raw = np.log1p(validation_df[FEATURES].to_numpy(dtype=np.float32))
X_test_raw = np.log1p(test_df[FEATURES].to_numpy(dtype=np.float32))

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train_raw).astype(np.float32)
X_val = scaler.transform(X_val_raw).astype(np.float32)
X_test = scaler.transform(X_test_raw).astype(np.float32)

train_loader = DataLoader(
    TensorDataset(torch.from_numpy(X_train)),
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0,
)

validation_tensor = torch.from_numpy(X_val).to(DEVICE)

model = DenseAutoencoder(input_dim=len(FEATURES)).to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
criterion = nn.MSELoss()

best_validation_loss = float("inf")
best_state = None
epochs_without_improvement = 0

print("\nTraining dense autoencoder")
print("------------------------------")

for epoch in range(1, MAX_EPOCHS + 1):
    model.train()
    total_loss = 0.0
    total_rows = 0

    for (batch,) in train_loader:
        batch = batch.to(DEVICE)

        optimizer.zero_grad()
        reconstructed = model(batch)
        loss = criterion(reconstructed, batch)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * len(batch)
        total_rows += len(batch)

    train_loss = total_loss / total_rows

    model.eval()
    with torch.no_grad():
        validation_reconstruction = model(validation_tensor)
        validation_loss = criterion(
            validation_reconstruction,
            validation_tensor,
        ).item()

    print(
        f"Epoch {epoch:02d}/{MAX_EPOCHS} | "
        f"train_loss={train_loss:.6f} | "
        f"validation_loss={validation_loss:.6f}"
    )

    if validation_loss < best_validation_loss:
        best_validation_loss = validation_loss
        best_state = {
            key: value.detach().cpu().clone()
            for key, value in model.state_dict().items()
        }
        epochs_without_improvement = 0
    else:
        epochs_without_improvement += 1

    if epochs_without_improvement >= PATIENCE:
        print(f"Early stopping after epoch {epoch}.")
        break

if best_state is None:
    raise RuntimeError("Training did not produce a valid model.")

model.load_state_dict(best_state)
model.eval()


# --------------------------------------------------
# Select threshold using validation data only
# --------------------------------------------------

validation_errors = reconstruction_errors(model, X_val)
threshold = float(
    np.percentile(validation_errors, THRESHOLD_PERCENTILE)
)

test_errors = reconstruction_errors(model, X_test)
test_anomalies = test_errors > threshold

print("\nEvaluation summary")
print("------------------------------")
print(f"Best validation loss: {best_validation_loss:.6f}")
print(f"Threshold percentile: {THRESHOLD_PERCENTILE}")
print(f"Reconstruction-error threshold: {threshold:.8f}")
print(f"Validation profiles above threshold: {(validation_errors > threshold).sum():,}")
print(f"Test profiles: {len(test_errors):,}")
print(f"Test profiles above threshold: {test_anomalies.sum():,}")
print(
    "Test alert rate: "
    f"{100.0 * test_anomalies.mean():.2f}%"
)
print(
    "Test reconstruction error — median: "
    f"{np.median(test_errors):.8f}, "
    f"95th percentile: {np.percentile(test_errors, 95):.8f}, "
    f"99th percentile: {np.percentile(test_errors, 99):.8f}"
)


# --------------------------------------------------
# Save model, scaler, threshold and metadata
# --------------------------------------------------

torch.save(model.cpu().state_dict(), MODEL_PATH)
joblib.dump(scaler, SCALER_PATH)

threshold_info = {
    "threshold": threshold,
    "validation_percentile": THRESHOLD_PERCENTILE,
    "validation_profiles": int(len(validation_errors)),
    "validation_date_start": str(validation_df["date"].min().date()),
    "validation_date_end": str(validation_df["date"].max().date()),
    "method": "validation reconstruction-error percentile",
}

metadata = {
    "model_name": "dense_autoencoder",
    "version": "1.0.0",
    "architecture": [len(FEATURES), 32, 16, 8, 16, 32, len(FEATURES)],
    "features": FEATURES,
    "preprocessing": {
        "transformation": "numpy.log1p",
        "scaler": "StandardScaler",
        "scaler_fitted_on": "training split only",
    },
    "training": {
        "seed": SEED,
        "epochs_completed": epoch,
        "best_validation_loss": best_validation_loss,
        "training_profiles": int(len(train_df)),
        "validation_profiles": int(len(validation_df)),
        "test_profiles": int(len(test_df)),
        "training_date_start": str(train_df["date"].min().date()),
        "training_date_end": str(train_df["date"].max().date()),
        "test_date_start": str(test_df["date"].min().date()),
        "test_date_end": str(test_df["date"].max().date()),
    },
    "threshold_method": (
        "99th percentile of validation reconstruction errors; "
        "not optimized against ground-truth labels"
    ),
    "limitations": [
        "The available processed profiles do not contain confirmed anomaly labels.",
        "The early chronological training period is assumed to be predominantly normal; "
        "this assumption has not been verified against scenario ground truth.",
        "The threshold is a statistical operating point, not proof of malicious activity.",
        "Above-threshold profiles are anomaly candidates, not confirmed insider threats.",
    ],
}

with open(THRESHOLD_PATH, "w", encoding="utf-8") as file:
    json.dump(threshold_info, file, indent=2)

with open(METADATA_PATH, "w", encoding="utf-8") as file:
    json.dump(metadata, file, indent=2)

print("\nSaved artifacts")
print("------------------------------")
print(f"Model:     {MODEL_PATH}")
print(f"Scaler:    {SCALER_PATH}")
print(f"Threshold: {THRESHOLD_PATH}")
print(f"Metadata:  {METADATA_PATH}")
print("\nTraining completed successfully.")
