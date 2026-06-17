import uuid

from django.db import models


class Sesion(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "activa", "Activa (preparación)"
        INICIADA = "iniciada", "Iniciada (en curso)"
        FINALIZADA = "finalizada", "Finalizada"

    entrevista = models.ForeignKey(
        "entrevistas.Entrevista",
        on_delete=models.CASCADE,
        related_name="sesiones",
    )
    creada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="sesiones_creadas",
    )
    room_name = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invitacion = models.ForeignKey(
        "entrevistas.Invitado",
        on_delete=models.SET_NULL,
        related_name="sesiones",
        blank=True,
        null=True,
        help_text="Invitación del candidato (1 sesión por invitación). Capa 3.",
    )
    identidad_verificada = models.BooleanField(
        default=False,
        help_text="True cuando el candidato pasa la verificación de identidad.",
    )
    grabacion_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        help_text="URL de la grabación de la sesión (webhook de Jitsi).",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVA,
    )
    observaciones_internas = models.TextField(
        blank=True,
        null=True,
        help_text="Observaciones internas del evaluador",
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_inicio"]
        verbose_name = "Sesión"
        verbose_name_plural = "Sesiones"

    def __str__(self):
        return f"Sesión {self.room_name} - {self.entrevista}"


class Respuesta(models.Model):
    """Respuesta de un candidato a una pregunta dentro de su sesión (Capa 3)."""

    sesion = models.ForeignKey(
        "sesiones.Sesion",
        on_delete=models.CASCADE,
        related_name="respuestas",
    )
    pregunta = models.ForeignKey(
        "pruebas.Pregunta",
        on_delete=models.PROTECT,
        related_name="respuestas",
    )
    contenido_texto = models.TextField(
        blank=True,
        null=True,
        help_text="Respuesta del candidato: texto, opción elegida o código.",
    )
    contenido_url = models.URLField(
        max_length=2000,
        blank=True,
        null=True,
        help_text="Si el candidato sube un archivo.",
    )
    casos_pasados = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Para código: cuántos casos de prueba pasó (Judge0).",
    )
    tiempo_segundos = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Tiempo (seg) entre ver la pregunta y responder.",
    )
    enviado_en = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        ordering = ["sesion", "pregunta"]
        unique_together = ("sesion", "pregunta")
        verbose_name = "Respuesta"
        verbose_name_plural = "Respuestas"

    def __str__(self):
        return f"Respuesta sesión {self.sesion_id} - pregunta {self.pregunta_id}"
