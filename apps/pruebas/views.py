from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.ia import prompts
from apps.ia.client import IAError, chat_json

from .models import Opcion, Pregunta, Prueba, Seccion
from .serializers import (
    OpcionSerializer,
    PreguntaSerializer,
    PruebaSerializer,
    SeccionSerializer,
)

_FORMATOS_VALIDOS = {f.value for f in Pregunta.Formato}


class PruebaViewSet(ModelViewSet):
    queryset = Prueba.objects.all()
    serializer_class = PruebaSerializer

    @action(detail=False, methods=["post"], url_path="generar-preguntas")
    def generar_preguntas(self, request):
        """
        Genera BORRADORES de preguntas con el LLM local (no las guarda: el
        reclutador las revisa y confirma desde el front más adelante).

        POST /api/pruebas/pruebas/generar-preguntas/
        Body: {
            "area": "programacion", "nivel": "intermedio",
            "cantidad": 5, "formato": "opcion_multiple",
            "tema": "estructuras de datos"   # opcional
        }
        → { "preguntas": [ {enunciado, formato, opciones?/rubrica?/lenguaje?}, ... ] }
        """
        area = (request.data.get("area") or "").strip()
        nivel = (request.data.get("nivel") or "").strip()
        formato = (request.data.get("formato") or "opcion_multiple").strip()
        tema = (request.data.get("tema") or "").strip() or None
        try:
            cantidad = int(request.data.get("cantidad", 5))
        except (TypeError, ValueError):
            return Response(
                {"detail": "'cantidad' debe ser un número."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not area or not nivel:
            return Response(
                {"detail": "Se requieren 'area' y 'nivel'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if formato not in _FORMATOS_VALIDOS:
            return Response(
                {"detail": f"'formato' inválido. Opciones: {sorted(_FORMATOS_VALIDOS)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cantidad = max(1, min(cantidad, 20))  # tope defensivo

        system, prompt = prompts.generar_preguntas(area, nivel, cantidad, formato, tema)
        try:
            data = chat_json(prompt, system=system, thinking=False, temperature=0.6, timeout=240)
        except IAError as exc:
            return Response(
                {"detail": f"El servicio de IA no está disponible: {exc}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        preguntas = data.get("preguntas")
        if not isinstance(preguntas, list):
            return Response(
                {"detail": "El LLM no devolvió una lista de preguntas."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"preguntas": preguntas}, status=status.HTTP_200_OK)


class SeccionViewSet(ModelViewSet):
    queryset = Seccion.objects.all()
    serializer_class = SeccionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        prueba_id = self.request.query_params.get("prueba")
        if prueba_id:
            qs = qs.filter(prueba_id=prueba_id)
        return qs


class PreguntaViewSet(ModelViewSet):
    queryset = Pregunta.objects.all()
    serializer_class = PreguntaSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        seccion_id = self.request.query_params.get("seccion")
        if seccion_id:
            qs = qs.filter(seccion_id=seccion_id)
        return qs


class OpcionViewSet(ModelViewSet):
    queryset = Opcion.objects.all()
    serializer_class = OpcionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        pregunta_id = self.request.query_params.get("pregunta")
        if pregunta_id:
            qs = qs.filter(pregunta_id=pregunta_id)
        return qs
