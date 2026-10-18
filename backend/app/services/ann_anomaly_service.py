from pathlib import Path
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging import logger


class ANNAnomalyService:
    """Service interface for Neural Network Anomaly Detection (Dense Autoencoder)."""

    def __init__(self):
        self.model_name = "dense_autoencoder"
        self.version = "1.0.0"
        self.model_path = settings.MODELS_DIR / "dense_autoencoder.pt"
        self.threshold_path = settings.MODELS_DIR / "autoencoder_threshold.json"
        self._model = None
        self._threshold = None
        self._load_model_if_exists()

    def _load_model_if_exists(self):
        if self.model_path.exists():
            try:
                import torch
                self._model = torch.load(str(self.model_path), weights_only=True)
                self._model.eval()
                logger.info(f"Loaded ANN Autoencoder model from {self.model_path}")
            except Exception as e:
                logger.warning(f"Found model file at {self.model_path} but failed to load: {e}")
                self._model = None
        else:
            self._model = None

    def is_available(self) -> bool:
        return self._model is not None

    def predict_reconstruction_error(self, feature_vector: List[float]) -> Optional[float]:
        """Runs autoencoder forward pass and calculates MSE reconstruction error."""
        if not self.is_available():
            return None

        import torch
        import numpy as np

        with torch.no_grad():
            tensor_in = torch.tensor([feature_vector], dtype=torch.float32)
            reconstruction = self._model(tensor_in)
            loss = torch.mean((tensor_in - reconstruction) ** 2).item()
            return float(loss)

    def get_info(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "is_available": self.is_available(),
            "artifact_path": str(self.model_path) if self.model_path.exists() else None,
            "architecture": "Dense Autoencoder (Input -> 32 -> 16 -> 8 -> 16 -> 32 -> Output)",
            "message": "Autoencoder ready for inference" if self.is_available() else "ANN Autoencoder artifact not found. Awaiting CERT dataset training."
        }


ann_anomaly_service = ANNAnomalyService()
