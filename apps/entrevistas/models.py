from django.db import models


class Entrevista(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PROGRAMADA = "programada", "Programada"
        EN_PROCESO = "en_proceso", "En proceso"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    creada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="entrevistas_creadas",
    )
    evaluador = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="entrevistas_evaluadas",
        blank=True,
        null=True,
    )
    prueba = models.ForeignKey(
        "pruebas.Prueba",
        on_delete=models.SET_NULL,
        related_name="convocatorias",
        blank=True,
        null=True,
        help_text="Prueba (plantilla del banco) que se rinde en esta convocatoria.",
    )
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    fecha_programada = models.DateTimeField(blank=True, null=True)
    duracion_minutos = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text=(
            "Override OPCIONAL de la duración. Si está vacío, se usa la duración "
            "de la prueba (fuente de verdad). Solo se llena para dar más/menos "
            "tiempo a esta convocatoria en particular."
        ),
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        verbose_name = "Entrevista"
        verbose_name_plural = "Entrevistas"

    def __str__(self):
        return self.titulo


class Invitado(models.Model):
    entrevista = models.ForeignKey(
        Entrevista,
        on_delete=models.CASCADE,
        related_name="invitados",
    )
    candidato = models.ForeignKey(
        "candidatos.Candidato",
        on_delete=models.SET_NULL,
        related_name="invitaciones",
        blank=True,
        null=True,
        help_text="Identidad reutilizable del candidato (Módulo 1/3)",
    )
    nombre = models.CharField(max_length=100)
    email = models.EmailField()
    rol = models.CharField(
        max_length=30,
        default="invitado",
        choices=[("invitado", "Invitado")],
    )
    link_token = models.CharField(max_length=500, blank=True, null=True, help_text="JWT token para generar link")
    link_invitacion = models.URLField(max_length=2000, blank=True, null=True, help_text="URL completa de invitación")
    estado = models.CharField(
        max_length=30,
        default="pendiente",
        choices=[
            ("pendiente", "Pendiente"),
            ("aceptado", "Aceptado"),
            ("rechazado", "Rechazado"),
            ("completado", "Completado"),
        ],
    )
    fecha_invitacion = models.DateTimeField(auto_now_add=True)
    fecha_aceptacion = models.DateTimeField(blank=True, null=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha_invitacion"]
        verbose_name = "Invitado"
        verbose_name_plural = "Invitados"
        unique_together = ("entrevista", "email")

    def __str__(self):
        return f"{self.nombre} ({self.email}) - {self.entrevista.titulo}"
