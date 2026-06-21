from django.db import models


class Reporte(models.Model):
    """
    Informe final de una sesión (Módulo 6). 1:1 con la Sesión — es el documento
    que junta la NOTA (qué respondió), el RIESGO (calculado de las alertas del
    proctoring) y la DECISIÓN FIRMADA del evaluador. "La IA asiste, el humano decide".
    """

    class Decision(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de decisión"
        APTO = "apto", "Apto"
        NO_APTO = "no_apto", "No apto"

    class NivelRiesgo(models.TextChoices):
        BAJO = "bajo", "Bajo"
        MEDIO = "medio", "Medio"
        ALTO = "alto", "Alto"

    sesion = models.OneToOneField(
        "sesiones.Sesion",
        on_delete=models.CASCADE,
        related_name="reporte",
        blank=True,
        null=True,
        help_text="Informe 1:1 de la sesión (el hub de toda la evaluación).",
    )

    # ── Datos automáticos (se recalculan al generar) ──────────────────────────
    nota = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Snapshot de la nota de la sesión al generar el informe (puede ser null si aún no se calificó).",
    )
    nivel_riesgo = models.CharField(
        max_length=20,
        choices=NivelRiesgo.choices,
        default=NivelRiesgo.BAJO,
        help_text="Riesgo CALCULADO de las alertas del proctoring (no se recibe del front).",
    )
    total_alertas = models.PositiveIntegerField(default=0)
    puntaje_atencion = models.IntegerField(default=100)
    puntaje_sospecha = models.IntegerField(default=0)
    resumen_general = models.TextField(blank=True, null=True)
    resumen_participante = models.TextField(blank=True, null=True)
    recomendaciones = models.TextField(blank=True, null=True)

    # ── Decisión del evaluador (lo manual — "el humano decide") ───────────────
    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDIENTE,
    )
    firmado_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        related_name="reportes_firmados",
        blank=True,
        null=True,
    )
    fecha_firma = models.DateTimeField(blank=True, null=True)
    observaciones_evaluador = models.TextField(blank=True, null=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Reporte"
        verbose_name_plural = "Reportes"

    def __str__(self):
        return f"Informe sesión {self.sesion_id} ({self.nivel_riesgo})"
