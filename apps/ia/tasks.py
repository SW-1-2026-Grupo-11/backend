"""
Tareas Celery de IA. Corren en el worker (async) para no bloquear la respuesta
al candidato cuando termina su prueba.

`calificar_sesion`: al finalizar una sesión se encola esta tarea, que
  1) califica las OBJETIVAS (opción múltiple / V-F) por comparación,
  2) califica las ABIERTAS con el LLM local (puntaje_ia + feedback_ia),
  3) recalcula la nota final de la sesión.
El evaluador siempre puede ajustar después con puntaje_humano (prevalece).
"""
from __future__ import annotations

import logging

from celery import shared_task

from apps.ia import prompts
from apps.ia.client import IAError, chat_json

logger = logging.getLogger("apps.ia")


def _calificar_abiertas(sesion) -> int:
    """
    Califica con el LLM las respuestas ABIERTAS de la sesión que aún no tienen
    puntaje de IA. Guarda puntaje_ia + feedback_ia. Devuelve cuántas calificó.
    Cada fallo del LLM en una respuesta se loguea y se saltea (no rompe el resto).
    """
    n = 0
    abiertas = sesion.respuestas.select_related("pregunta").filter(
        pregunta__formato="abierta", puntaje_ia__isnull=True
    )
    for r in abiertas:
        preg = r.pregunta
        system, prompt = prompts.corregir_abierta(
            enunciado=preg.enunciado,
            rubrica=preg.rubrica,
            respuesta=r.contenido_texto or "",
            puntaje_max=float(preg.puntaje),
        )
        try:
            # thinking OFF: en CPU el modo "pensamiento" tarda demasiado (>180s);
            # apagado da buena calidad de corrección en ~30s. El humano revisa igual.
            data = chat_json(prompt, system=system, thinking=False, temperature=0.1, timeout=300)
            puntaje = float(data.get("puntaje"))
        except (IAError, TypeError, ValueError) as exc:
            logger.warning("No se pudo calificar respuesta %s: %s", r.id, exc)
            continue
        # Acotar el puntaje al rango válido [0, puntaje de la pregunta].
        puntaje = max(0.0, min(puntaje, float(preg.puntaje)))
        r.puntaje_ia = puntaje
        r.feedback_ia = (data.get("feedback") or "").strip() or None
        r.save(update_fields=["puntaje_ia", "feedback_ia"])
        n += 1
    return n


@shared_task(name="apps.ia.calificar_sesion")
def calificar_sesion(sesion_id: int) -> dict:
    """Califica objetivas + abiertas (IA) y recalcula la nota. Idempotente."""
    # Import perezoso: evita import circular (views importa modelos de varias apps).
    from apps.sesiones.models import Sesion
    from apps.sesiones.views import _calificar_objetivas, _recalcular_nota

    sesion = Sesion.objects.filter(pk=sesion_id).first()
    if sesion is None:
        logger.warning("calificar_sesion: sesión %s no existe", sesion_id)
        return {"sesion_id": sesion_id, "error": "sesion_no_encontrada"}

    objetivas = _calificar_objetivas(sesion)
    abiertas = _calificar_abiertas(sesion)
    _recalcular_nota(sesion)

    logger.info(
        "calificar_sesion %s: objetivas=%s abiertas=%s nota=%s",
        sesion_id, objetivas, abiertas, sesion.nota_final,
    )
    return {
        "sesion_id": sesion_id,
        "objetivas": objetivas,
        "abiertas": abiertas,
        "nota_final": float(sesion.nota_final) if sesion.nota_final is not None else None,
    }
