"""
Cliente del LLM local (Ollama).

Django/Celery le hablan a Ollama por HTTP (servicio `ollama` del docker-compose).
Modelo por defecto: qwen3:8b. Para todas las tareas usamos:
  - `format="json"`  → fuerza salida JSON parseable (no texto suelto).
  - `think`          → qwen3 tiene "modo pensamiento" activable:
       * thinking=False (rápido) → generar preguntas / demo en vivo.
       * thinking=True  (preciso, más lento) → corregir abiertas (async).

Nada acá rompe el flujo: si Ollama no responde, se levanta `IAError` y el
llamador decide el fallback (p.ej. el informe usa los textos por reglas).
"""
from __future__ import annotations

import json
import logging

from django.conf import settings

logger = logging.getLogger("apps.ia")


class IAError(RuntimeError):
    """El LLM no respondió o devolvió algo inutilizable."""


def _url() -> str:
    base = getattr(settings, "OLLAMA_URL", "http://ollama:11434").rstrip("/")
    return f"{base}/api/chat"


def chat(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = True,
    thinking: bool = False,
    temperature: float = 0.2,
    timeout: int = 300,
) -> str:
    """
    Manda un prompt al LLM y devuelve el contenido (texto) de la respuesta.
    Levanta IAError ante cualquier fallo (red, HTTP, payload inesperado).
    """
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": getattr(settings, "OLLAMA_MODEL", "qwen3:8b"),
        "messages": messages,
        "stream": False,
        "think": thinking,
        "options": {"temperature": temperature},
    }
    if json_mode:
        payload["format"] = "json"

    # Import perezoso: el backend carga aunque la imagen no tenga `requests` aún;
    # solo falla (controlado) al USAR la IA.
    import requests

    try:
        resp = requests.post(_url(), json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise IAError(f"No se pudo contactar a Ollama: {exc}") from exc
    except ValueError as exc:
        raise IAError(f"Respuesta de Ollama no es JSON: {exc}") from exc

    content = (data.get("message") or {}).get("content")
    if not content:
        raise IAError("Ollama devolvió una respuesta vacía.")
    return content


def chat_json(prompt: str, **kwargs) -> dict:
    """
    Igual que chat() pero parsea el contenido como JSON y lo devuelve como dict.
    Fuerza json_mode=True. Levanta IAError si el contenido no es JSON válido.
    """
    kwargs["json_mode"] = True
    raw = chat(prompt, **kwargs)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("LLM devolvió JSON inválido: %s | raw=%.300s", exc, raw)
        raise IAError("El LLM no devolvió JSON válido.") from exc
    if not isinstance(parsed, dict):
        raise IAError("El LLM devolvió JSON que no es un objeto.")
    return parsed
