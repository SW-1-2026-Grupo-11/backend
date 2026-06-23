from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction, IntegrityError
from datetime import timedelta
import logging

from .models import Entrevista, Invitado
from .serializers import EntrevistaSerializer, ProgramarEntrevistaSerializer, InvitadoSerializer
from .tasks import enviar_emails_invitaciones_masivas, enviar_push_entrevista_asignada
from apps.usuarios.models import Usuario
from apps.candidatos.models import Candidato
from apps.pruebas.models import Prueba

logger = logging.getLogger(__name__)


class EntrevistaViewSet(ModelViewSet):
    queryset = Entrevista.objects.all()
    serializer_class = EntrevistaSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["titulo", "descripcion"]
    ordering_fields = ["fecha_programada", "fecha_creacion", "titulo"]

    @action(detail=False, methods=["post"], url_path="programar")
    @transaction.atomic
    def programar_entrevista(self, request):
        """
        Programa una entrevista con invitados y envía emails automáticamente.
        
        Endpoint: POST /api/entrevistas/entrevistas/programar/
        
        Datos esperados:
        {
            "titulo": "Entrevista evaluador",
            "descripcion": "Entrevista técnica",
            "evaluador_id": 1,
            "fecha_programada": "2026-05-20T14:30:00Z",
            "duracion_minutos": 60,
            "invitados": [
                {"nombre": "Carlos Pérez", "email": "carlos@gmail.com"},
                {"nombre": "Sofía García", "email": "sofia@gmail.com"}
            ]
        }
        
        Response (201):
        {
            "entrevista": {...},
            "invitados": [...],
            "link_supervisor": "http://...",
            "emails_encolados": True,
            "mensaje": "..."
        }
        """
        serializer = ProgramarEntrevistaSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Obtener datos validados
        titulo = serializer.validated_data.get("titulo")
        descripcion = serializer.validated_data.get("descripcion", "")
        fecha_programada = serializer.validated_data.get("fecha_programada")
        # Override OPCIONAL: None = hereda la duración de la prueba (se resuelve abajo).
        duracion_minutos = serializer.validated_data.get("duracion_minutos")
        invitados_data = serializer.validated_data.get("invitados", [])
        evaluador_id = serializer.validated_data.get("evaluador_id")
        prueba_id = serializer.validated_data.get("prueba_id")

        # Obtener usuario que crea la entrevista (del request o parámetro)
        usuario = request.user if request.user.is_authenticated else None
        if not usuario:
            return Response(
                {"detail": "Usuario no autenticado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Obtener evaluador si se proporciona
        evaluador = None
        if evaluador_id:
            try:
                evaluador = Usuario.objects.get(pk=evaluador_id)
            except Usuario.DoesNotExist:
                return Response(
                    {"detail": "Evaluador no encontrado."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Obtener la prueba (plantilla del banco) si se proporciona
        prueba = None
        if prueba_id:
            try:
                prueba = Prueba.objects.get(pk=prueba_id)
            except Prueba.DoesNotExist:
                return Response(
                    {"detail": "Prueba no encontrada."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Duración efectiva (para exp de links y email): override o, si no, la de la
        # prueba. La convocatoria se guarda con duracion_minutos=None si se heredó.
        duracion_efectiva = duracion_minutos or (prueba.duracion_minutos if prueba else 60)

        # exp de los links atado a la cita (fecha + duración + 2h); solo extiende
        # más allá del default (24h) si la entrevista es lejana.
        exp_extra = None
        if fecha_programada:
            fin = fecha_programada + timedelta(minutes=duracion_efectiva + 120)
            delta = fin - timezone.now()
            if delta > timedelta(hours=24):
                exp_extra = delta

        # Emails repetidos chocarían el unique_together(entrevista, email).
        _emails = [i.get("email") for i in invitados_data]
        if len(_emails) != len(set(_emails)):
            return Response(
                {"detail": "Hay emails repetidos en la lista de invitados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Crear la entrevista
            entrevista = Entrevista.objects.create(
                titulo=titulo,
                descripcion=descripcion,
                creada_por=usuario,
                evaluador=evaluador,
                prueba=prueba,
                estado=Entrevista.Estado.PROGRAMADA,
                fecha_programada=fecha_programada,
                duracion_minutos=duracion_minutos,
            )

            # NOTA (Capa 3): la sesión NO se crea aquí. Nace cuando el candidato
            # ingresa (POST /api/sesiones/ingresar/). Aquí solo se programa la
            # convocatoria y se generan las invitaciones.

            # Crear invitados con links JWT personalizados
            invitados_creados = []
            invitados_para_email = []
            base_url = settings.FRONTEND_URL.rstrip("/")

            for invitado_data in invitados_data:
                nombre = invitado_data.get("nombre")
                email = invitado_data.get("email")

                # Resolver/crear la identidad reutilizable del candidato (Módulo 1/3)
                candidato = Candidato.objects.obtener_o_crear(email=email, nombre=nombre)

                # Crear la invitación primero para tener su id real en el JWT
                invitado = Invitado.objects.create(
                    entrevista=entrevista,
                    candidato=candidato,
                    nombre=nombre,
                    email=email,
                    rol="invitado",
                    link_token="",
                    link_invitacion="",
                    estado="pendiente",
                )

                # Generar JWT del invitado (con su id real; la sesión nace al entrar)
                refresh = RefreshToken()
                refresh["invitado_id"] = invitado.id
                refresh["entrevista_id"] = entrevista.id
                refresh["nombre"] = nombre
                refresh["email"] = email
                refresh["moderator"] = False  # invitado no es moderador

                access = refresh.access_token
                if exp_extra:
                    access.set_exp(lifetime=exp_extra)
                token_str = str(access)
                link_invitacion = f"{base_url}/join?token={token_str}"

                invitado.link_token = token_str
                invitado.link_invitacion = link_invitacion
                invitado.save(update_fields=["link_token", "link_invitacion"])

                invitados_creados.append(
                    {
                        "id": invitado.id,
                        "nombre": invitado.nombre,
                        "email": invitado.email,
                        "link_invitacion": invitado.link_invitacion,
                    }
                )

                # Preparar datos para envío de email
                invitados_para_email.append(
                    {
                        "nombre": nombre,
                        "email": email,
                        "link_invitacion": link_invitacion,
                    }
                )

            # Generar link para el supervisor/evaluador
            refresh_supervisor = RefreshToken()
            refresh_supervisor["usuario_id"] = usuario.id
            refresh_supervisor["entrevista_id"] = entrevista.id
            refresh_supervisor["nombre"] = usuario.get_full_name() or usuario.username
            refresh_supervisor["email"] = usuario.email
            refresh_supervisor["moderator"] = True  # supervisor es moderador

            access_sup = refresh_supervisor.access_token
            if exp_extra:
                access_sup.set_exp(lifetime=exp_extra)
            token_supervisor = str(access_sup)
            link_supervisor = f"{base_url}/join?token={token_supervisor}"

            # Convertir fecha_programada a string si es necesario
            fecha_str = (
                fecha_programada.isoformat()
                if hasattr(fecha_programada, "isoformat")
                else str(fecha_programada)
            )

            # Encolar tareas de envío de email (asincrónico con Celery)
            emails_encolados = False
            try:
                if invitados_para_email:
                    # Encolar DESPUÉS del commit: evita que el worker de Celery
                    # lea datos que la transacción todavía no confirmó.
                    transaction.on_commit(
                        lambda: enviar_emails_invitaciones_masivas.delay(
                            entrevista_id=entrevista.id,
                            invitados=invitados_para_email,
                            titulo_entrevista=titulo,
                            descripcion=descripcion,
                            evaluador_nombre=evaluador.get_full_name() if evaluador else usuario.get_full_name(),
                            fecha_programada=fecha_str,
                            duracion_minutos=duracion_efectiva,
                        )
                    )
                    emails_encolados = True
                    logger.info(
                        f"✓ Emails encolados para entrevista {entrevista.id}: "
                        f"{len(invitados_para_email)} invitados"
                    )
            except Exception as e:
                logger.error(f"Error encolando emails para entrevista {entrevista.id}: {str(e)}")
                # No fallar la creación de entrevista si hay error en emails

            # Avisar al evaluador asignado (push), igual que los emails: tras el commit.
            if evaluador:
                transaction.on_commit(
                    lambda: enviar_push_entrevista_asignada.delay(
                        evaluador_id=evaluador.id,
                        titulo_entrevista=titulo,
                        fecha_programada=fecha_str,
                    )
                )

            return Response(
                {
                    "entrevista": EntrevistaSerializer(entrevista).data,
                    "invitados": invitados_creados,
                    "link_supervisor": link_supervisor,
                    "emails_encolados": emails_encolados,
                    "mensaje": (
                        f"Entrevista programada exitosamente con {len(invitados_creados)} "
                        f"invitados. Emails en envío..." if emails_encolados
                        else f"Entrevista programada con {len(invitados_creados)} invitados. "
                        f"(Emails sin configurar)"
                    ),
                },
                status=status.HTTP_201_CREATED,
            )

        except IntegrityError:
            transaction.set_rollback(True)
            return Response(
                {"detail": "Conflicto al crear invitados (posible email duplicado)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            transaction.set_rollback(True)
            logger.error(f"Error creando entrevista: {str(e)}")
            return Response(
                {"detail": f"Error al crear la entrevista: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"], url_path="cancelar")
    def cancelar(self, request, pk=None):
        """
        Cancela la convocatoria (decisión manual del reclutador). Es la única
        transición de estado "a mano" que tiene sentido — el resto se deriva del
        tiempo. Una vez cancelada, los candidatos no pueden ingresar.

        POST /api/entrevistas/entrevistas/{id}/cancelar/
        """
        entrevista = self.get_object()
        if entrevista.estado != Entrevista.Estado.CANCELADA:
            entrevista.estado = Entrevista.Estado.CANCELADA
            entrevista.save(update_fields=["estado", "fecha_actualizacion"])
            logger.info(f"✓ Convocatoria {entrevista.id} cancelada")
        return Response(EntrevistaSerializer(entrevista).data, status=status.HTTP_200_OK)


class InvitadoViewSet(ModelViewSet):
    """ViewSet para gestionar invitados de entrevistas"""
    queryset = Invitado.objects.all()
    serializer_class = InvitadoSerializer
    pagination_class = None  # devolver TODOS los invitados (no paginar de a 20)

    def get_queryset(self):
        qs = Invitado.objects.all()
        entrevista_id = self.request.query_params.get("entrevista")
        if entrevista_id:
            qs = qs.filter(entrevista_id=entrevista_id)
        return qs
    
    def destroy(self, request, *args, **kwargs):
        """
        Elimina un invitado de la entrevista.
        
        DELETE /api/invitados/{id}/
        
        Nota: Si el invitado ya ingresó a la sesión, se puede eliminar
        pero la sesión continúa para otros participantes.
        """
        try:
            invitado = self.get_object()
            entrevista_id = invitado.entrevista.id
            nombre = invitado.nombre
            email = invitado.email
            
            invitado.delete()
            
            logger.info(f"✓ Invitado eliminado: {nombre} ({email}) de entrevista {entrevista_id}")
            
            return Response(
                {
                    "detail": f"Invitado {nombre} ha sido eliminado de la entrevista.",
                    "id": kwargs.get("pk"),
                },
                status=status.HTTP_200_OK,
            )
        except Invitado.DoesNotExist:
            return Response(
                {"detail": "Invitado no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error eliminando invitado: {str(e)}")
            return Response(
                {"detail": f"Error al eliminar invitado: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
    
    @action(detail=True, methods=["patch"], url_path="marcar-aceptado")
    def marcar_aceptado(self, request, pk=None):
        """
        Marca un invitado como aceptado (cuando ingresa a la sesión).
        
        PATCH /api/invitados/{id}/marcar-aceptado/
        
        Response (200):
        {
            "id": 1,
            "nombre": "Carlos",
            "email": "carlos@gmail.com",
            "estado": "aceptado",
            "fecha_aceptacion": "2026-05-13T14:35:00Z"
        }
        """
        try:
            invitado = self.get_object()
            
            # Marcar como aceptado
            invitado.estado = "aceptado"
            invitado.fecha_aceptacion = timezone.now()
            invitado.save()
            
            logger.info(
                f"✓ Invitado marcado como aceptado: {invitado.nombre} "
                f"({invitado.email}) en entrevista {invitado.entrevista.id}"
            )
            
            serializer = self.get_serializer(invitado)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Invitado.DoesNotExist:
            return Response(
                {"detail": "Invitado no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Error marcando invitado como aceptado: {str(e)}")
            return Response(
                {"detail": f"Error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
