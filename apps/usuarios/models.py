from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        SUPERVISOR = "supervisor", "Supervisor"
        INVITADO = "invitado", "Invitado"

    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    telefono = models.CharField(max_length=30, blank=True, null=True)
    rol = models.CharField(max_length=30, choices=Rol.choices, default=Rol.SUPERVISOR)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)

    REQUIRED_FIELDS = ["email", "first_name", "last_name"]

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return f"{self.get_full_name()} ({self.username}) - {self.get_rol_display()}"
