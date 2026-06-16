from django.db import models
import uuid


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
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    fecha_programada = models.DateTimeField(blank=True, null=True)
    duracion_minutos = models.PositiveIntegerField(default=60, help_text="Duración de la entrevista en minutos")
    
    # Punto 6: Metadata de la entrevista
    area_entrevista = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Área o departamento (ej: Ingeniería de Software - Backend)"
    )
    
    class TipoPrueba(models.TextChoices):
        TEORICA = "teorica", "Teórica"
        PRACTICA = "practica", "Práctica"
        MIXTA = "mixta", "Mixta"
    
    tipo_prueba = models.CharField(
        max_length=20,
        choices=TipoPrueba.choices,
        blank=True,
        null=True,
        help_text="Tipo de evaluación"
    )
    
    porcentaje_teorica = models.PositiveIntegerField(
        default=0,
        help_text="Porcentaje de preguntas teóricas (0-100). Asignado por IA"
    )
    porcentaje_practica = models.PositiveIntegerField(
        default=0,
        help_text="Porcentaje de ejercicios prácticos (0-100). Asignado por IA"
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


class Etapa(models.Model):
    """
    Punto 6: Etapas o secciones de una entrevista.
    Ejemplos: Introducción, Preguntas Técnicas, Ejercicio Práctico, etc.
    """
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_CURSO = "en_curso", "En curso"
        COMPLETADA = "completada", "Completada"

    entrevista = models.ForeignKey(
        Entrevista,
        on_delete=models.CASCADE,
        related_name="etapas",
        help_text="Entrevista a la que pertenece esta etapa"
    )
    titulo = models.CharField(
        max_length=150,
        help_text="Nombre de la etapa (ej: Introducción, Preguntas Técnicas, Ejercicio Práctico)"
    )
    descripcion = models.TextField(
        blank=True,
        null=True,
        help_text="Descripción detallada de la etapa"
    )
    orden = models.PositiveIntegerField(
        help_text="Orden de aparición (1, 2, 3, ...)"
    )
    duracion_estimada_minutos = models.PositiveIntegerField(
        default=15,
        help_text="Tiempo estimado en minutos para completar esta etapa"
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        help_text="Estado actual de la etapa"
    )
    fecha_inicio = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Cuándo comenzó esta etapa"
    )
    fecha_fin = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Cuándo finalizó esta etapa"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["entrevista", "orden"]
        verbose_name = "Etapa"
        verbose_name_plural = "Etapas"
        unique_together = ("entrevista", "orden")

    def __str__(self):
        return f"{self.entrevista.titulo} - {self.titulo} (Orden: {self.orden})"
