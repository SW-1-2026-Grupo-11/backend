from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .models import Usuario
from .serializers import UsuarioSerializer


class UsuarioViewSet(ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering_fields = ["first_name", "last_name", "email", "date_joined"]


class FCMTokenView(APIView):
    """
    Registra/actualiza el token FCM del usuario autenticado para push notifications.

    POST /api/usuarios/fcm-token/
    Body: {"token": "<fcm_token>"}
    """

    def post(self, request):
        fcm_token = request.data.get("token")
        if not fcm_token:
            return Response({"detail": "El campo 'token' es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.fcm_token = fcm_token
        request.user.save(update_fields=["fcm_token"])
        return Response({"detail": "Token FCM registrado."}, status=status.HTTP_200_OK)
