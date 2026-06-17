from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils import timezone

from apps.entrevistas.models import Entrevista, Invitado
from apps.usuarios.models import Usuario
from apps.pruebas.models import Pregunta

from .models import Sesion, Respuesta
from .serializers import (
    CrearSesionSerializer,
    SesionSerializer,
    SesionDetalleSerializer,
    RespuestaSerializer,
)


def _bearer_token(request):
    """Extrae el JWT del header Authorization: Bearer <token>, si viene."""
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def _decode_invitado_token(token_str):
    """
    Decodifica y VERIFICA (firma + expiración) el JWT del invitado/supervisor.
    Devuelve el AccessToken o None si es inválido. Solo aceptamos tokens
    firmados por nuestro backend, así que el candidato no puede falsificarlo.
    """
    if not token_str:
        return None
    try:
        return AccessToken(token_str)
    except TokenError:
        return None


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

    @action(detail=False, methods=["post"], url_path="ingresar", permission_classes=[AllowAny])
    def ingresar(self, request):
        """
        El candidato ENTRA a su evaluación → aquí NACE su sesión (Regla de capa 3:
        la sesión se crea cuando el candidato ingresa, NO al programar).

        Idempotente: 1 sesión por invitación. Si ya entró, devuelve la misma sesión.

        POST /api/sesiones/ingresar/
        Body: { "token": "<jwt del link de invitación>" }
        """
        token_str = request.data.get("token") or _bearer_token(request)
        token = _decode_invitado_token(token_str)
        if token is None:
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        entrevista_id = token.get("entrevista_id")
        invitado_id = token.get("invitado_id")
        email = token.get("email")

        # Resolver la invitación: por id (tokens nuevos) o por (entrevista, email) (robustez)
        invitado = None
        if invitado_id:
            invitado = Invitado.objects.filter(pk=invitado_id).first()
        if invitado is None and entrevista_id and email:
            invitado = Invitado.objects.filter(
                entrevista_id=entrevista_id, email=email
            ).first()
        if invitado is None:
            return Response(
                {"detail": "Invitación no encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )

        entrevista = invitado.entrevista

        # 1 sesión por invitación (idempotente al refrescar o reentrar)
        sesion = Sesion.objects.filter(invitacion=invitado).first()
        creada = False
        if sesion is None:
            sesion = Sesion.objects.create(
                entrevista=entrevista,
                creada_por=entrevista.creada_por,
                invitacion=invitado,
                estado=Sesion.Estado.INICIADA,
            )
            creada = True

        # Marcar la invitación como aceptada al entrar
        if invitado.estado == "pendiente":
            invitado.estado = "aceptado"
            invitado.fecha_aceptacion = timezone.now()
            invitado.save(update_fields=["estado", "fecha_aceptacion", "fecha_actualizacion"])

        return Response(
            SesionSerializer(sesion).data,
            status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="responder", permission_classes=[AllowAny])
    def responder(self, request, pk=None):
        """
        El candidato envía (o actualiza) la respuesta a una pregunta de su sesión.

        POST /api/sesiones/{sesion_id}/responder/
        Body: {
            "token": "<jwt>",
            "pregunta_id": 1,
            "contenido_texto": "...",      # texto / opción elegida / código
            "contenido_url": "...",        # opcional (archivo subido)
            "casos_pasados": 3,            # opcional (código)
            "tiempo_segundos": 42          # opcional
        }
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        token = _decode_invitado_token(request.data.get("token") or _bearer_token(request))
        if token is None:
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # El token debe corresponder a la invitación dueña de la sesión
        inv = sesion.invitacion
        if inv is not None:
            invitado_id = token.get("invitado_id")
            email = token.get("email")
            corresponde = (invitado_id and inv.id == invitado_id) or (
                email and inv.email == email
            )
            if not corresponde:
                return Response(
                    {"detail": "El token no corresponde a esta sesión."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        pregunta_id = request.data.get("pregunta_id")
        if not pregunta_id:
            return Response({"detail": "Falta pregunta_id."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            pregunta = Pregunta.objects.get(pk=pregunta_id)
        except Pregunta.DoesNotExist:
            return Response({"detail": "Pregunta no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        respuesta, _creada = Respuesta.objects.update_or_create(
            sesion=sesion,
            pregunta=pregunta,
            defaults={
                "contenido_texto": request.data.get("contenido_texto"),
                "contenido_url": request.data.get("contenido_url"),
                "casos_pasados": request.data.get("casos_pasados"),
                "tiempo_segundos": request.data.get("tiempo_segundos"),
            },
        )
        return Response(RespuestaSerializer(respuesta).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="respuestas")
    def respuestas(self, request, pk=None):
        """
        Lista las respuestas de una sesión (para que el evaluador las revise).

        GET /api/sesiones/{sesion_id}/respuestas/
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        qs = sesion.respuestas.select_related("pregunta").all()
        return Response(RespuestaSerializer(qs, many=True).data, status=status.HTTP_200_OK)
