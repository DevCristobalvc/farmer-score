"""
Módulo de análisis de reuniones.
Contiene la lógica para procesar transcripciones y generar JSON estructurado.
"""

import json
import requests
from typing import Dict

import config


def load_system_prompt() -> str:
    """Carga el system prompt desde el archivo de configuración."""
    prompt_path = config.PROMPTS_DIR / "system_prompt.txt"

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"ERROR: No se encontró {prompt_path}\n" "Asegúrate de que existe prompts/system_prompt.txt"
        )

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def analyze_transcription(transcription: str, verbose: bool = True) -> Dict:
    """
    Analiza una transcripción y devuelve datos estructurados.

    Args:
        transcription: Texto de la transcripción de la reunión
        verbose: Si True, muestra la respuesta cruda del modelo

    Returns:
        Dict con los datos estructurados de la reunión

    Raises:
        Exception: Si hay errores en la API o el parsing
    """
    system_prompt = load_system_prompt()
    url = f"{config.BASE_URL}/chat/completions"

    # Truncar transcripción si es muy larga
    max_chars = 2500
    transcription_trimmed = transcription[:max_chars] if len(transcription) > max_chars else transcription

    payload = {
        "model": config.MODEL,
        "temperature": 0.3,
        "max_tokens": 800,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": transcription_trimmed}],
    }

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.API_KEY}"}

    # Realizar petición a la API
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=config.TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise Exception(f"TIMEOUT: La API tardó más de {config.TIMEOUT} segundos")
    except requests.exceptions.RequestException as e:
        raise Exception(f"ERROR EN LA PETICIÓN: {e}")

    # Mostrar respuesta cruda si verbose=True
    if verbose:
        print("\nRAW RESPONSE FROM MODEL:\n")
        print(response.text)
        print("\n-------- END RAW RESPONSE --------\n")

    # Parsear respuesta
    try:
        response_json = response.json()
    except Exception:
        raise Exception(f"La API devolvió algo que no es JSON válido.\n{response.text}")

    # Validar respuesta
    if "error" in response_json:
        error_msg = response_json.get("error", {}).get("message", "Error desconocido")
        raise Exception(f"Error de la API: {error_msg}")

    if "choices" not in response_json or not response_json["choices"]:
        raise Exception(f"La API no devolvió 'choices': {response_json}")

    # Extraer contenido
    choice = response_json["choices"][0]
    finish_reason = choice.get("finish_reason", "")

    if finish_reason == "length":
        print("ADVERTENCIA: Respuesta truncada. Considera aumentar MAX_TOKENS.")

    raw_output = choice["message"]["content"].strip()

    if not raw_output:
        raise Exception("El modelo devolvió contenido vacío")

    # Parsear JSON
    try:
        structured_data = json.loads(raw_output)
    except Exception as e:
        print("ERROR PARSEANDO JSON")
        print(f"Contenido:\n{raw_output}")
        raise Exception(f"No se pudo parsear el JSON: {e}")

    return structured_data
