import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIH Underground Coal Mine Subsidence Monitoring System"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Server & CORS
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    CORS_ORIGINS: list[str] = ["*"]
    
    # Serial / UART Gateway Connection
    SERIAL_PORT: str = os.getenv("SERIAL_PORT", "COM5")
    BAUD_RATE: int = int(os.getenv("BAUD_RATE", 115200))
    SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "false").lower() == "true"
    
    # Database
    DATABASE_URL: str = os.getenv("DB_URL", "sqlite:///./subsidence.db")
    
    # ML Artifacts
    ML_MODEL_PATH: str = os.getenv("ML_MODEL_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "ml_engine", "artifacts", "subsidence_model.joblib"))
    ML_ENCODER_PATH: str = os.getenv("ML_ENCODER_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "ml_engine", "artifacts", "label_encoder.joblib"))
    FORECASTER_PTH_PATH: str = os.getenv("FORECASTER_PTH_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "ml_engine", "artifacts", "displacement_forecaster.pth"))
    FORECASTER_SCALER_PATH: str = os.getenv("FORECASTER_SCALER_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "ml_engine", "artifacts", "forecaster_scaler.joblib"))
    COLLAPSE_THRESHOLD_MM: float = float(os.getenv("COLLAPSE_THRESHOLD_MM", 400.0))
    
    # Critical Geotechnical Alert Thresholds
    CRITICAL_STRAIN_UE: float = 750.0
    CRITICAL_DISP_MM: float = 20.0
    CRITICAL_TILT_DEG: float = 2.5
    CRITICAL_VIB_AMP: float = 0.80

settings = Settings()
