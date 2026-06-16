from django.contrib import admin

from .models import Candidato


@admin.register(Candidato)
class CandidatoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "email", "documento", "telefono", "fecha_creacion")
    search_fields = ("nombre", "email", "documento")
    ordering = ("nombre",)
