from django.contrib import admin

from .models import Entrevista, Invitado


@admin.register(Entrevista)
class EntrevistaAdmin(admin.ModelAdmin):
    list_display = ("id", "titulo", "creada_por", "evaluador", "estado", "fecha_programada", "duracion_minutos")
    list_filter = ("estado",)
    search_fields = ("titulo", "descripcion", "creada_por__first_name", "creada_por__email")
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
