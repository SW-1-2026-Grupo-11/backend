from django.db import models

class Alerta(models.Model):
    entrevista = models.ForeignKey(
        "entrevistas.Entrevista",
        on_delete=models.CASCADE,
        related_name="alertas",
    )
    sesion = models.ForeignKey(
        "sesiones.Sesion",
        on_delete=models.CASCADE,
        related_name="alertas",
        blank=True,
        null=True,
        help_text="Sesión donde se generó la alerta (Capa 3).",
    )
    participante = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="alertas",
    )
    tipo_alerta = models.CharField(max_length=100)
    severidad = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    evidencia_json = models.JSONField(blank=True, null=True)
    origen = models.CharField(max_length=100)
    timestamp_alerta = models.DateTimeField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    objects = models.Manager()

    def __str__(self):
        return f"{self.tipo_alerta} - {self.severidad} ({self.fecha_creacion})"
