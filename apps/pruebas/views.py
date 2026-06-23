from rest_framework.viewsets import ModelViewSet

from .models import Opcion, Pregunta, Prueba, Seccion
from .serializers import (
    OpcionSerializer,
    PreguntaSerializer,
    PruebaSerializer,
    SeccionSerializer,
)


class PruebaViewSet(ModelViewSet):
    queryset = Prueba.objects.all()
    serializer_class = PruebaSerializer

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)


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

    def perform_create(self, serializer):
        pregunta = serializer.save()
        if pregunta.formato == Pregunta.Formato.VERDADERO_FALSO:
            Opcion.objects.create(pregunta=pregunta, texto="Verdadero", orden=1)
            Opcion.objects.create(pregunta=pregunta, texto="Falso", orden=2)


class OpcionViewSet(ModelViewSet):
    queryset = Opcion.objects.all()
    serializer_class = OpcionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        pregunta_id = self.request.query_params.get("pregunta")
        if pregunta_id:
            qs = qs.filter(pregunta_id=pregunta_id)
        return qs
