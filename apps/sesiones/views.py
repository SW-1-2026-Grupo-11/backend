from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet

from apps.entrevistas.models import Entrevista, Invitado
from apps.usuarios.models import Usuario

from .models import Sesion
from .serializers import CrearSesionSerializer, SesionSerializer, SesionDetalleSerializer


class CrearObtenerSesionView(APIView):
    def post(self, request):
        serializer = CrearSesionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        entrevista_id = serializer.validated_data["entrevista_id"]
        creada_por_id = serializer.validated_data["creada_por"]

        try:
            entrevista = Entrevista.objects.get(pk=entrevista_id)
        except Entrevista.DoesNotExist:
            return Response({"detail": "Entrevista no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        try:
            usuario = Usuario.objects.get(pk=creada_por_id)
        except Usuario.DoesNotExist:
            return Response({"detail": "Usuario no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        sesion_activa = Sesion.objects.filter(
            entrevista=entrevista, estado__in=[Sesion.Estado.ACTIVA, Sesion.Estado.INICIADA]
        ).first()

        if sesion_activa:
            return Response(SesionSerializer(sesion_activa).data, status=status.HTTP_200_OK)

        sesion = Sesion.objects.create(entrevista=entrevista, creada_por=usuario)
        return Response(SesionSerializer(sesion).data, status=status.HTTP_201_CREATED)

    def get(self, request, entrevista_id):
        try:
            entrevista = Entrevista.objects.get(pk=entrevista_id)
        except Entrevista.DoesNotExist:
            return Response({"detail": "Entrevista no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        sesion = Sesion.objects.filter(
            entrevista=entrevista, estado__in=[Sesion.Estado.ACTIVA, Sesion.Estado.INICIADA]
        ).first()

        if not sesion:
            return Response({"detail": "No hay sesión activa para esta entrevista."}, status=status.HTTP_404_NOT_FOUND)

        return Response(SesionSerializer(sesion).data, status=status.HTTP_200_OK)


class FinalizarSesionView(APIView):
    def patch(self, request, sesion_id):
        try:
            sesion = Sesion.objects.get(pk=sesion_id)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        from django.utils import timezone
        sesion.estado = Sesion.Estado.FINALIZADA
        sesion.fecha_fin = timezone.now()
        sesion.save()

        return Response(SesionSerializer(sesion).data, status=status.HTTP_200_OK)


class SesionViewSet(ModelViewSet):
    """ViewSet para gestionar sesiones con endpoints adicionales"""
    queryset = Sesion.objects.all()
    serializer_class = SesionSerializer

    @action(detail=True, methods=["get"], url_path="detalle")
    def detalle_preparacion(self, request, pk=None):
        """
        Obtiene datos completos de la sesión para la sala de preparación.
        
        Incluye:
        - datos de la sesión
        - datos de la entrevista
        - evaluador responsable
        - lista de invitados con links
        
        GET /api/sesiones/{sesion_id}/detalle/
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response(
                {"detail": "Sesión no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SesionDetalleSerializer(sesion)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="actualizar-estado")
    def actualizar_estado(self, request, pk=None):
        """
        Actualiza el estado de la sesión (activa -> iniciada -> finalizada).
        
        PATCH /api/sesiones/{sesion_id}/actualizar-estado/
        
        Request:
        {
            "estado": "iniciada"  # o "finalizada"
        }
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response(
                {"detail": "Sesión no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        nuevo_estado = request.data.get("estado")
        if nuevo_estado not in dict(Sesion.Estado.choices).keys():
            return Response(
                {"detail": f"Estado inválido. Opciones: {list(dict(Sesion.Estado.choices).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sesion.estado = nuevo_estado
        if nuevo_estado == Sesion.Estado.FINALIZADA:
            from django.utils import timezone
            sesion.fecha_fin = timezone.now()

        sesion.save()
        return Response(SesionDetalleSerializer(sesion).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path="observaciones")
    def actualizar_observaciones(self, request, pk=None):
        """
        Actualiza las observaciones internas de la sesión.
        
        PATCH /api/sesiones/{sesion_id}/observaciones/
        
        Request:
        {
            "observaciones_internas": "texto de observaciones"
        }
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response(
                {"detail": "Sesión no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        observaciones = request.data.get("observaciones_internas", "")
        sesion.observaciones_internas = observaciones
        sesion.save()

        return Response(SesionDetalleSerializer(sesion).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="agregar-invitado")
    def agregar_invitado(self, request, pk=None):
        """
        Agrega un nuevo invitado a la sesión después de su creación.
        
        POST /api/sesiones/{sesion_id}/agregar-invitado/
        
        Request:
        {
            "nombre": "Juan Pérez",
            "email": "juan@gmail.com"
        }
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response(
                {"detail": "Sesión no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        nombre = request.data.get("nombre")
        email = request.data.get("email")

        if not nombre or not email:
            return Response(
                {"detail": "Se requieren 'nombre' y 'email'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar que el invitado no exista ya
        if Invitado.objects.filter(entrevista=sesion.entrevista, email=email).exists():
            return Response(
                {"detail": f"El invitado con email {email} ya existe en esta entrevista."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generar JWT para el nuevo invitado
        from rest_framework_simplejwt.tokens import RefreshToken
        
        refresh = RefreshToken()
        refresh["invitado_id"] = None
        refresh["entrevista_id"] = sesion.entrevista.id
        refresh["nombre"] = nombre
        refresh["email"] = email
        refresh["moderator"] = False

        token_str = str(refresh.access_token)
        base_url = request.build_absolute_uri("/").rstrip("/")
        link_invitacion = f"{base_url}/join?token={token_str}"

        # Resolver/crear la identidad reutilizable del candidato (Módulo 1/3)
        from apps.candidatos.models import Candidato
        candidato = Candidato.objects.obtener_o_crear(email=email, nombre=nombre)

        invitado = Invitado.objects.create(
            entrevista=sesion.entrevista,
            candidato=candidato,
            nombre=nombre,
            email=email,
            rol="invitado",
            link_token=token_str,
            link_invitacion=link_invitacion,
            estado="pendiente",
        )

        return Response(
            {
                "id": invitado.id,
                "nombre": invitado.nombre,
                "email": invitado.email,
                "estado": invitado.estado,
                "link_invitacion": invitado.link_invitacion,
            },
            status=status.HTTP_201_CREATED,
        )
