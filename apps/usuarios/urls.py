from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import FCMTokenView, UsuarioViewSet

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuarios")

urlpatterns = [
    path("fcm-token/", FCMTokenView.as_view(), name="fcm-token"),
    *router.urls,
]
