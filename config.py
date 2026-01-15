"""
Configuración centralizada del proyecto.
Carga variables de entorno y constantes.
"""

import os
from pathlib import Path

# Directorios del proyecto
BASE_DIR = Path(__file__).parent
PROMPTS_DIR = BASE_DIR / "prompts"

# Configuración de la API (se cargan desde Airflow Variables)
API_KEY = os.getenv("API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "https://rappi.litellm-prod.ai/v1")
MODEL = os.getenv("MODEL", "gpt-4o-mini")

# Parámetros del modelo
TEMPERATURE = 0.3
MAX_TOKENS = 800
TIMEOUT = 30
