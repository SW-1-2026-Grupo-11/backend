from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        ADMIN = "admin", "Administrador"
        RECLUTADOR = "reclutador", "Reclutador"
        EVALUADOR = "evaluador", "Evaluador"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    telefono = models.CharField(max_length=30, blank=True, null=True)
    rol = models.CharField(max_length=30, choices=Rol.choices, default=Rol.EVALUADOR)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    fcm_token = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Token de Firebase Cloud Messaging del dispositivo móvil (push).",
    )

    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.get_full_name()} ({self.username}) - {self.get_rol_display()}"
