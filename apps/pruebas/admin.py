from django.contrib import admin

from .models import Prueba, PruebaEntrevista


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
