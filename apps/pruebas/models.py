from django.db import models


class Prueba(models.Model):
    class Tipo(models.TextChoices):
        TEORICA = "teorica", "Teórica"
        TECNICA = "tecnica", "Técnica"
        MIXTA = "mixta", "Mixta"

    class Area(models.TextChoices):
        PROGRAMACION = "programacion", "Programación"
        NEGOCIO = "negocio", "Negocio"
        JURIDICA = "juridica", "Jurídica"

    class Nivel(models.TextChoices):
        BASICO = "basico", "Básico"
        INTERMEDIO = "intermedio", "Intermedio"
        AVANZADO = "avanzado", "Avanzado"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ACTIVA = "activa", "Activa"
        INACTIVA = "inactiva", "Inactiva"
        ARCHIVADA = "archivada", "Archivada"

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    creada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="pruebas_creadas",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    area = models.CharField(max_length=30, choices=Area.choices)
    nivel = models.CharField(max_length=30, choices=Nivel.choices)
    duracion_minutos = models.PositiveIntegerField()
    puntaje_maximo = models.PositiveIntegerField(default=100)
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ["titulo"]
        verbose_name = "Prueba"
        verbose_name_plural = "Pruebas"

    def __str__(self):
        return self.titulo


class Seccion(models.Model):
    """
    Sección de una prueba. Agrupa preguntas y lleva el peso porcentual con el que
    esa sección entra en la nota final.

    Patrón "siempre al menos una sección": una prueba simple usa una sola sección
    ("General", 100%); una estructurada usa varias (ej: Teoría 40% / Práctica 60%).
    Así el cálculo de nota es uniforme, haya una o muchas.
    """

    prueba = models.ForeignKey(
        "pruebas.Prueba",
        on_delete=models.CASCADE,
        related_name="secciones",
    )
    titulo = models.CharField(max_length=150, default="General")
    descripcion = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=1)
    peso_porcentual = models.PositiveIntegerField(
        default=100,
        help_text="Peso de la sección en la nota final (0-100).",
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ["prueba", "orden"]
        unique_together = ("prueba", "orden")
        verbose_name = "Sección"
        verbose_name_plural = "Secciones"

    def __str__(self):
        return f"{self.prueba.titulo} - {self.titulo} ({self.peso_porcentual}%)"


class Pregunta(models.Model):
    """
    Pregunta dentro de una sección. El `formato` define cómo se responde y se
    califica; los campos específicos se usan según el formato:
      - opcion_multiple / verdadero_falso -> ver modelo Opcion (relación 'opciones')
      - abierta -> 'rubrica' (JSON, la usa la IA para calificar)
      - codigo  -> 'lenguaje' + 'casos_prueba' (JSON)
    """

    class Formato(models.TextChoices):
        OPCION_MULTIPLE = "opcion_multiple", "Opción múltiple"
        VERDADERO_FALSO = "verdadero_falso", "Verdadero / Falso"
        ABIERTA = "abierta", "Respuesta abierta"
        CODIGO = "codigo", "Código"

    seccion = models.ForeignKey(
        "pruebas.Seccion",
        on_delete=models.CASCADE,
        related_name="preguntas",
    )
    enunciado = models.TextField()
    formato = models.CharField(max_length=30, choices=Formato.choices)
    puntaje = models.PositiveIntegerField(default=1)
    orden = models.PositiveIntegerField(default=1)

    # Datos específicos según el formato
    rubrica = models.JSONField(
        blank=True,
        null=True,
        help_text="Criterios para calificar preguntas abiertas (usado por la IA).",
    )
    lenguaje = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Lenguaje para preguntas de código (ej: python).",
    )
    casos_prueba = models.JSONField(
        blank=True,
        null=True,
        help_text="Casos para código: [{'entrada': ..., 'salida_esperada': ...}].",
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ["seccion", "orden"]
        unique_together = ("seccion", "orden")
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"

    def __str__(self):
        return f"[{self.get_formato_display()}] {self.enunciado[:50]}"


class Opcion(models.Model):
    """Opción de una pregunta de opción múltiple o verdadero/falso."""

    pregunta = models.ForeignKey(
        "pruebas.Pregunta",
        on_delete=models.CASCADE,
        related_name="opciones",
    )
    texto = models.CharField(max_length=500)
    es_correcta = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=1)

    objects = models.Manager()

    class Meta:
        ordering = ["pregunta", "orden"]
        verbose_name = "Opción"
        verbose_name_plural = "Opciones"

    def __str__(self):
        marca = " (correcta)" if self.es_correcta else ""
        return f"{self.texto[:40]}{marca}"


class PruebaEntrevista(models.Model):
    class Estado(models.TextChoices):
        ASIGNADA = "asignada", "Asignada"
        INACTIVA = "inactiva", "Inactiva"
        CANCELADA = "cancelada", "Cancelada"

    entrevista = models.ForeignKey(
        "entrevistas.Entrevista",
        on_delete=models.CASCADE,
        related_name="pruebas_asignadas",
    )
    prueba = models.ForeignKey(
        "pruebas.Prueba",
        on_delete=models.PROTECT,
        related_name="entrevistas_asignadas",
    )
    asignada_por = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.PROTECT,
        related_name="pruebas_entrevista_asignadas",
    )
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.ASIGNADA,
    )
    observaciones = models.TextField(blank=True, null=True)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        ordering = ["-fecha_asignacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["entrevista", "prueba"],
                name="prueba_unica_por_entrevista",
            )
        ]
        verbose_name = "Prueba de entrevista"
        verbose_name_plural = "Pruebas de entrevista"

    def __str__(self):
        return f"{self.entrevista} - {self.prueba}"
