from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("id", "username", "first_name", "last_name", "email", "rol", "estado", "is_active")
    list_filter = ("rol", "estado", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos adicionales", {"fields": ("telefono", "rol", "estado")}),
    )
