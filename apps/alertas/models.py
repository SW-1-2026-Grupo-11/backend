from django.db import models


class Alerta(models.Model):
    # La SESIÓN es el ancla del proctoring (1 candidato por sesión).
    # El candidato es sesion.invitacion → ya no hace falta un FK a Usuario.
    sesion = models.ForeignKey(
        "sesiones.Sesion",
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
        help_text="Sesión donde se generó la alerta (el hub del proctoring).",
    )
    # Se DERIVA de la sesión (se autocompleta en el serializer). Se conserva
    # nullable para filtrar/consultar por convocatoria sin un join.
    entrevista = models.ForeignKey(
        "entrevistas.Entrevista",
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True,
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
