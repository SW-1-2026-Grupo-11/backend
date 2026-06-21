from django.contrib import admin
from .models import Reporte


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("id", "sesion", "nivel_riesgo", "nota", "decision", "fecha_creacion")
    list_filter = ("nivel_riesgo", "decision")
    search_fields = ("sesion__id", "resumen_general")
