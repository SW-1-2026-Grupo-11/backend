from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


def api_root(request):
    return JsonResponse(
        {
            "message": "Backend de entrevistas laborales funcionando correctamente",
            "api": {
                "usuarios": "/api/usuarios/",
                "candidatos": "/api/candidatos/",
                "entrevistas": "/api/entrevistas/",
                "pruebas": "/api/pruebas/",
                "admin": "/admin/",
            },
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/usuarios/", include("apps.usuarios.urls")),
    path("api/candidatos/", include("apps.candidatos.urls")),
    path("api/entrevistas/", include("apps.entrevistas.urls")),
    path("api/pruebas/", include("apps.pruebas.urls")),
    path("api/sesiones/", include("apps.sesiones.urls")),
    path("api/alertas/", include("apps.alertas.urls")),
    path("api/reportes/", include("apps.reportes.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
