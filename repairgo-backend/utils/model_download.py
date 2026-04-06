import os
from typing import List

from huggingface_hub import hf_hub_download

from utils.logger import logger

MODEL_FILES: List[str] = [
    "reliability_model.joblib",
    "reliability_scaler.joblib",
    "demand_model.joblib",
    "demand_scaler.joblib",
    "fraud_model.joblib",
    "fraud_scaler.joblib",
    "fraud_feature_stats.joblib",
]


def download_models_if_needed() -> bool:
    repo_id = os.getenv("HF_REPO")
    token = os.getenv("HF_TOKEN")
    if not repo_id or not token:
        logger.info("HF_REPO or HF_TOKEN not set, skipping model download")
        return False

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    target_dir = os.path.join(base_dir, "ml", "saved_models")
    os.makedirs(target_dir, exist_ok=True)

    downloaded_any = False
    for filename in MODEL_FILES:
        local_path = os.path.join(target_dir, filename)
        if os.path.exists(local_path):
            continue
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=target_dir,
                local_dir_use_symlinks=False,
                token=token,
            )
            downloaded_any = True
            logger.info(f"Downloaded model file: {filename}")
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")

    return downloaded_any
