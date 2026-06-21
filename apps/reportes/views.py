from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.reportes.models import Reporte
from apps.reportes.serializers import ReporteSerializer
from apps.sesiones.models import Sesion

# ---------------------------------------------------------------------------
# Cálculo de riesgo (ponderado) — se calcula AQUÍ de las alertas, no se recibe.
# ---------------------------------------------------------------------------

# Tipos de alerta "graves": una sola ya empuja a riesgo alto.
_TIPOS_GRAVES = {"uso_de_celular", "multiples_rostros", "posible_celular_o_lectura"}


def _calcular_riesgo(alertas) -> str:
    """
    Reglas (ponderadas por gravedad, no conteo plano):
      - alto: ≥1 alerta alta de tipo grave (celular/múltiples rostros) o ≥2 altas.
      - medio: 1 alta suelta, o ≥3 medias.
      - bajo: el resto.
    """
    altas = [a for a in alertas if a.severidad == "alta"]
    medias = [a for a in alertas if a.severidad == "media"]
    altas_graves = [a for a in altas if a.tipo_alerta in _TIPOS_GRAVES]

    if altas_graves or len(altas) >= 2:
        return Reporte.NivelRiesgo.ALTO
    if len(altas) == 1 or len(medias) >= 3:
        return Reporte.NivelRiesgo.MEDIO
    return Reporte.NivelRiesgo.BAJO


def _puntaje_sospecha(alertas) -> int:
    """Puntaje 0-100: cada alta pesa 25, cada media 10 (tope 100)."""
    altas = sum(1 for a in alertas if a.severidad == "alta")
    medias = sum(1 for a in alertas if a.severidad == "media")
    return min(100, altas * 25 + medias * 10)


# ---------------------------------------------------------------------------
# Textos por reglas (motor reutilizado del diseño anterior — está bien hecho)
# ---------------------------------------------------------------------------

_TIPO_LABELS = {
    "uso_de_celular": "uso de celular",
    "sin_rostro": "ausencia de rostro",
    "multiples_rostros": "múltiples rostros detectados",
    "mirada_fuera_pantalla": "mirada fuera de pantalla",
    "posible_celular_o_lectura": "posible lectura o celular fuera de cámara",
    "cambio_ventana": "cambio de ventana/pestaña",
    "camara_apagada": "cámara apagada",
    "camara_no_disponible": "sin cámara disponible",
    "pantalla_compartida": "pantalla compartida",
    "participante_salio": "participante se desconectó",
}


def _label(tipo: str) -> str:
    return _TIPO_LABELS.get(tipo, tipo.replace("_", " "))


def _generar_textos_dinamicos(alertas_sesion, nivel_riesgo: str) -> tuple[str, str, str]:
    """Genera resúmenes y recomendaciones dinámicas basadas en las alertas reales."""
    total = len(alertas_sesion)

    # -- resumen_general --
    if total == 0:
        resumen_general = (
            "La sesión transcurrió sin incidencias. El sistema de proctoring no detectó "
            "ninguna alerta durante la evaluación."
        )
    else:
        conteos: dict[str, int] = {}
        for a in alertas_sesion:
            conteos[a.tipo_alerta] = conteos.get(a.tipo_alerta, 0) + 1
        detalles = ", ".join(
            f"{cnt} alerta(s) de {_label(tipo)}" for tipo, cnt in sorted(conteos.items())
        )
        resumen_general = (
            f"El sistema de proctoring detectó {total} alerta(s) durante la sesión: {detalles}. "
            f"El nivel de riesgo evaluado es: {nivel_riesgo.upper()}."
        )

    # -- resumen_participante --
    altas = [a for a in alertas_sesion if a.severidad == "alta"]
    medias = [a for a in alertas_sesion if a.severidad == "media"]

    if total == 0:
        resumen_participante = (
            "El candidato mantuvo un comportamiento adecuado durante toda la sesión sin generar alertas."
        )
    elif nivel_riesgo == Reporte.NivelRiesgo.BAJO:
        resumen_participante = (
            f"El candidato tuvo un buen desempeño con {total} alerta(s) menor(es). "
            "No se observaron patrones preocupantes de comportamiento."
        )
    elif nivel_riesgo == Reporte.NivelRiesgo.MEDIO:
        resumen_participante = (
            f"El candidato presentó un comportamiento aceptable, aunque se registraron "
            f"{len(altas)} alerta(s) de severidad alta y {len(medias)} de severidad media. "
            "Se recomienda revisar las evidencias antes de tomar una decisión."
        )
    else:
        tipos_altas = ", ".join({_label(a.tipo_alerta) for a in altas}) if altas else "varias categorías"
        resumen_participante = (
            f"El candidato generó {total} alerta(s) durante la sesión, de las cuales "
            f"{len(altas)} son de severidad alta relacionadas con: {tipos_altas}. "
            "El patrón de comportamiento sugiere riesgo elevado de irregularidades."
        )

    # -- recomendaciones --
    if total == 0:
        recomendaciones = (
            "El candidato puede avanzar al siguiente paso del proceso sin observaciones adicionales."
        )
    elif nivel_riesgo == Reporte.NivelRiesgo.BAJO:
        recomendaciones = (
            "Se puede aprobar al candidato. Las alertas detectadas son de baja severidad y no "
            "representan un riesgo significativo."
        )
    elif nivel_riesgo == Reporte.NivelRiesgo.MEDIO:
        recomendaciones = (
            "Revisar manualmente las alertas registradas antes de aprobar al candidato. "
            "Considerar una segunda evaluación si persisten las dudas."
        )
    else:
        recomendaciones = (
            "Se recomienda rechazar al candidato o solicitar una evaluación de validación supervisada. "
            "Las alertas de alta severidad indican posibles irregularidades que comprometen la integridad."
        )

    return resumen_general, resumen_participante, recomendaciones


class ReporteViewSet(viewsets.ModelViewSet):
    queryset = Reporte.objects.select_related(
        "sesion", "sesion__invitacion", "firmado_por"
    ).all()
    serializer_class = ReporteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        sesion_id = self.request.query_params.get("sesion")
        entrevista_id = self.request.query_params.get("entrevista")
        if sesion_id:
            qs = qs.filter(sesion_id=sesion_id)
        if entrevista_id:
            qs = qs.filter(sesion__entrevista_id=entrevista_id)
        return qs

    @action(detail=False, methods=["post"], url_path="generar")
    def generar(self, request):
        """
        Genera (o regenera) el informe de UNA sesión. Idempotente: 1 informe por
        sesión. Los datos automáticos (nota/riesgo/texto) se RECALCULAN; la
        decisión y firma del evaluador se CONSERVAN.

        POST /api/reportes/generar/   Body: { "sesion_id": 1 }
        """
        sesion_id = request.data.get("sesion_id")
        sesion = (
            Sesion.objects.select_related("invitacion", "entrevista")
            .filter(pk=sesion_id)
            .first()
        )
        if sesion is None:
            return Response(
                {"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND
            )

        alertas = list(sesion.alertas.all())
        riesgo = _calcular_riesgo(alertas)
        resumen_general, resumen_participante, recomendaciones = _generar_textos_dinamicos(
            alertas, riesgo
        )
        sospecha = _puntaje_sospecha(alertas)

        reporte, _creado = Reporte.objects.get_or_create(sesion=sesion)
        reporte.nota = sesion.nota_final
        reporte.nivel_riesgo = riesgo
        reporte.total_alertas = len(alertas)
        reporte.puntaje_sospecha = sospecha
        reporte.puntaje_atencion = 100 - sospecha
        reporte.resumen_general = resumen_general
        reporte.resumen_participante = resumen_participante
        reporte.recomendaciones = recomendaciones
        # decision / firmado_por / fecha_firma / observaciones_evaluador: NO se tocan.
        reporte.save()

        return Response(
            ReporteSerializer(reporte).data,
            status=status.HTTP_201_CREATED if _creado else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["patch"], url_path="decidir")
    def decidir(self, request, pk=None):
        """
        El evaluador firma su DECISIÓN (apto / no_apto). "La IA asiste, el humano decide".

        PATCH /api/reportes/{id}/decidir/
        Body: { "decision": "apto"|"no_apto", "observaciones": "..." (opcional) }
        """
        reporte = self.get_object()
        decision = request.data.get("decision")
        validas = (Reporte.Decision.APTO, Reporte.Decision.NO_APTO)
        if decision not in validas:
            return Response(
                {"detail": f"Decisión inválida. Debe ser una de: {', '.join(validas)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reporte.decision = decision
        if "observaciones" in request.data:
            reporte.observaciones_evaluador = request.data.get("observaciones")
        reporte.firmado_por = request.user if request.user.is_authenticated else None
        reporte.fecha_firma = timezone.now()
        reporte.save(
            update_fields=[
                "decision",
                "observaciones_evaluador",
                "firmado_por",
                "fecha_firma",
                "fecha_actualizacion",
            ]
        )
        return Response(ReporteSerializer(reporte).data, status=status.HTTP_200_OK)
