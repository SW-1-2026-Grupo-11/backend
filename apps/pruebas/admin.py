from django.contrib import admin

from .models import Opcion, Pregunta, Prueba, PruebaEntrevista, Seccion


class PreguntaInline(admin.TabularInline):
    model = Pregunta
    extra = 1


class OpcionInline(admin.TabularInline):
    model = Opcion
    extra = 2


@admin.register(Prueba)
class PruebaAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "titulo",
        "creada_por",
        "tipo",
        "area",
        "nivel",
        "estado",
    )
    list_filter = ("tipo", "area", "nivel", "estado")
    search_fields = ("titulo", "descripcion", "creada_por__first_name", "creada_por__email")


@admin.register(Seccion)
class SeccionAdmin(admin.ModelAdmin):
    list_display = ("id", "prueba", "titulo", "orden", "peso_porcentual")
    list_filter = ("prueba",)
    search_fields = ("titulo", "prueba__titulo")
    inlines = [PreguntaInline]


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ("id", "seccion", "formato", "puntaje", "orden")
    list_filter = ("formato",)
    search_fields = ("enunciado",)
    inlines = [OpcionInline]


@admin.register(Opcion)
class OpcionAdmin(admin.ModelAdmin):
    list_display = ("id", "pregunta", "texto", "es_correcta", "orden")
    list_filter = ("es_correcta",)
    search_fields = ("texto",)


@admin.register(PruebaEntrevista)
class PruebaEntrevistaAdmin(admin.ModelAdmin):
    list_display = ("id", "entrevista", "prueba", "asignada_por", "estado")
    list_filter = ("estado",)
    search_fields = (
        "entrevista__titulo",
        "prueba__titulo",
        "asignada_por__first_name",
        "asignada_por__email",
    )
