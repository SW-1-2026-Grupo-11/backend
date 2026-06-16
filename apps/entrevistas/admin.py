from django.contrib import admin

from .models import Entrevista, Invitado, Etapa


@admin.register(Entrevista)
class EntrevistaAdmin(admin.ModelAdmin):
    list_display = ("id", "titulo", "creada_por", "evaluador", "area_entrevista", "tipo_prueba", "estado", "fecha_programada", "duracion_minutos")
    list_filter = ("estado", "tipo_prueba", "area_entrevista")
    search_fields = ("titulo", "descripcion", "creada_por__first_name", "creada_por__email", "area_entrevista")
    fieldsets = (
        ("Información Básica", {
            "fields": ("titulo", "descripcion", "estado")
        }),
        ("Participantes", {
            "fields": ("creada_por", "evaluador")
        }),
        ("Configuración", {
            "fields": ("fecha_programada", "duracion_minutos")
        }),
        ("Metadata (Punto 6)", {
            "fields": ("area_entrevista", "tipo_prueba", "porcentaje_teorica", "porcentaje_practica"),
            "description": "Información adicional sobre la entrevista para IA"
        }),
        ("Timestamps", {
            "fields": ("fecha_creacion", "fecha_actualizacion"),
            "classes": ("collapse",)
        }),
    )
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")


@admin.register(Invitado)
class InvitadoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "email", "entrevista", "estado", "fecha_invitacion")
    list_filter = ("estado", "fecha_invitacion")
    search_fields = ("nombre", "email", "entrevista__titulo")
    readonly_fields = ("link_token", "link_invitacion", "fecha_invitacion", "fecha_aceptacion")


@admin.register(Etapa)
class EtapaAdmin(admin.ModelAdmin):
    """Admin para gestionar etapas de entrevistas (Punto 6)"""
    list_display = ("id", "entrevista", "orden", "titulo", "estado", "duracion_estimada_minutos", "fecha_inicio", "fecha_fin")
    list_filter = ("estado", "entrevista", "fecha_creacion")
    search_fields = ("titulo", "descripcion", "entrevista__titulo")
    fieldsets = (
        ("Información de Etapa", {
            "fields": ("entrevista", "titulo", "descripcion", "orden")
        }),
        ("Configuración", {
            "fields": ("duracion_estimada_minutos", "estado")
        }),
        ("Seguimiento", {
            "fields": ("fecha_inicio", "fecha_fin")
        }),
        ("Timestamps", {
            "fields": ("fecha_creacion", "fecha_actualizacion"),
            "classes": ("collapse",)
        }),
    )
    readonly_fields = ("fecha_creacion", "fecha_actualizacion")
