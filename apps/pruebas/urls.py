from rest_framework.routers import DefaultRouter

from .views import (
    OpcionViewSet,
    PreguntaViewSet,
    PruebaViewSet,
    SeccionViewSet,
)

router = DefaultRouter()
router.register("pruebas", PruebaViewSet, basename="pruebas")
router.register("secciones", SeccionViewSet, basename="secciones")
router.register("preguntas", PreguntaViewSet, basename="preguntas")
router.register("opciones", OpcionViewSet, basename="opciones")

urlpatterns = router.urls
