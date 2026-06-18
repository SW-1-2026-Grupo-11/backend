from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings

from .models import Alerta
from .serializers import AlertaSerializer


class AlertaViewSet(viewsets.ModelViewSet):
    serializer_class = AlertaSerializer

    def get_queryset(self):
        qs = Alerta.objects.all().order_by("-fecha_creacion")
        # Filtro opcional por sesión o convocatoria (para el panel/informe).
        sesion = self.request.query_params.get("sesion")
        entrevista = self.request.query_params.get("entrevista")
        if sesion:
            qs = qs.filter(sesion_id=sesion)
        if entrevista:
            qs = qs.filter(entrevista_id=entrevista)
        return qs

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        # El micro (ai-service) manda la API key en el header X-API-Key.
        api_key = request.headers.get("X-API-Key")
        expected = getattr(settings, "DJANGO_API_KEY", "dev-api-key")
        if not api_key or api_key != expected:
            return Response(
                {"detail": "Invalid or missing API Key"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return super().create(request, *args, **kwargs)
