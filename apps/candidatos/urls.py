from rest_framework.routers import DefaultRouter

from .views import CandidatoViewSet

router = DefaultRouter()
router.register("candidatos", CandidatoViewSet, basename="candidatos")

urlpatterns = router.urls
