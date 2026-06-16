from django.db import models


class CandidatoManager(models.Manager):
    def obtener_o_crear(self, email, nombre="", **extra):
        """
        Busca un candidato por email o lo crea si no existe.

        Punto único para resolver la identidad del candidato. Lo usarán otros
        flujos (p. ej. las invitaciones) para no duplicar candidatos al cargar
        emails. La lógica del candidato vive acá, en su propia app.
        """
        candidato, _creado = self.get_or_create(
            email=email,
            defaults={"nombre": nombre, **extra},
        )
        return candidato


class Candidato(models.Model):
    """
    Persona evaluada. Identidad única y reutilizable (un candidato puede
    participar en varias convocatorias con el tiempo).

    A diferencia de Usuario, NO tiene cuenta ni contraseña: no inicia sesión.
    Accede a su evaluación mediante un token único (ver app de invitaciones).
    """

    nombre = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    documento = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Documento de identidad (para la verificación de identidad)",
    )
    telefono = models.CharField(max_length=30, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = CandidatoManager()

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Candidato"
        verbose_name_plural = "Candidatos"

    def __str__(self):
        return f"{self.nombre} ({self.email})"
