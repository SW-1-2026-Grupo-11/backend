"""
Prompts (plantillas) para los 3 usos del LLM local. Cada builder devuelve
`(system, prompt)`. Todos piden salida JSON estricta para parsear sin ambigüedad.

Idioma de salida: español. Tono: evaluador profesional de reclutamiento.
"""
from __future__ import annotations

import json

# ─────────────────────────────────────────────────────────────────────────────
# 1) CORREGIR RESPUESTA ABIERTA
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_CORREGIR = (
    "Eres un evaluador técnico de procesos de selección. Calificas respuestas "
    "abiertas de candidatos de forma justa, objetiva y conservadora. Te apoyas en "
    "la rúbrica cuando existe. NUNCA inventas información que el candidato no escribió. "
    "Respondes SOLO con un objeto JSON, sin texto adicional."
)


def corregir_abierta(enunciado: str, rubrica, respuesta: str, puntaje_max: float) -> tuple[str, str]:
    rubrica_txt = (
        json.dumps(rubrica, ensure_ascii=False)
        if rubrica
        else "No se proporcionó rúbrica; evalúa por corrección, completitud y claridad."
    )
    prompt = (
        f"PREGUNTA:\n{enunciado}\n\n"
        f"RÚBRICA / CRITERIOS:\n{rubrica_txt}\n\n"
        f"RESPUESTA DEL CANDIDATO:\n{respuesta or '(sin respuesta)'}\n\n"
        f"Asigna un puntaje entre 0 y {puntaje_max} (puede tener decimales) y una "
        "justificación breve (1-3 frases) en español.\n"
        "Si la respuesta está vacía o no aborda la pregunta, el puntaje es 0.\n\n"
        "Devuelve EXACTAMENTE este JSON:\n"
        '{"puntaje": <number>, "feedback": "<string>"}'
    )
    return _SYSTEM_CORREGIR, prompt


# ─────────────────────────────────────────────────────────────────────────────
# 2) GENERAR PREGUNTAS
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_GENERAR = (
    "Eres un diseñador de evaluaciones técnicas para procesos de selección. "
    "Generas preguntas claras, sin ambigüedades y del nivel pedido. "
    "Respondes SOLO con un objeto JSON, sin texto adicional."
)


def generar_preguntas(
    area: str, nivel: str, cantidad: int, formato: str, tema: str | None = None
) -> tuple[str, str]:
    tema_txt = f" sobre el tema: {tema}" if tema else ""
    if formato == "opcion_multiple":
        forma = (
            'Cada pregunta debe traer 4 opciones, UNA correcta. Formato de cada item:\n'
            '{"enunciado": "...", "formato": "opcion_multiple", '
            '"opciones": [{"texto": "...", "es_correcta": true}, {"texto": "...", "es_correcta": false}, ...]}'
        )
    elif formato == "verdadero_falso":
        forma = (
            'Cada pregunta es una afirmación con respuesta verdadero/falso. Formato de cada item:\n'
            '{"enunciado": "...", "formato": "verdadero_falso", '
            '"opciones": [{"texto": "Verdadero", "es_correcta": true}, {"texto": "Falso", "es_correcta": false}]}'
        )
    elif formato == "codigo":
        forma = (
            'Cada pregunta pide escribir código. Formato de cada item:\n'
            '{"enunciado": "...", "formato": "codigo", "lenguaje": "python"}'
        )
    else:  # abierta
        forma = (
            'Cada pregunta es de respuesta abierta, con una rúbrica de criterios. Formato de cada item:\n'
            '{"enunciado": "...", "formato": "abierta", '
            '"rubrica": {"criterios": ["...", "..."]}}'
        )

    prompt = (
        f"Genera {cantidad} pregunta(s) de área '{area}', nivel '{nivel}'{tema_txt}.\n\n"
        f"{forma}\n\n"
        "Devuelve EXACTAMENTE este JSON:\n"
        '{"preguntas": [ <item>, <item>, ... ]}'
    )
    return _SYSTEM_GENERAR, prompt


# ─────────────────────────────────────────────────────────────────────────────
# 3) RESUMIR INFORME (M6)
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_RESUMIR = (
    "Eres un analista de integridad académica/laboral. Redactas informes claros y "
    "profesionales a partir de datos de proctoring y calificación, SIN exagerar ni "
    "acusar: la IA asiste, el humano decide. Respondes SOLO con un objeto JSON."
)


def resumir_informe(datos: dict) -> tuple[str, str]:
    prompt = (
        "Con estos datos de la sesión de evaluación, redacta el informe en español.\n\n"
        f"DATOS:\n{json.dumps(datos, ensure_ascii=False, indent=2)}\n\n"
        "Devuelve EXACTAMENTE este JSON con 3 textos (cada uno 2-4 frases):\n"
        '{"resumen_general": "<visión global de la sesión y el riesgo>", '
        '"resumen_participante": "<comportamiento y desempeño del candidato>", '
        '"recomendaciones": "<sugerencia para el evaluador, sin decidir por él>"}'
    )
    return _SYSTEM_RESUMIR, prompt
