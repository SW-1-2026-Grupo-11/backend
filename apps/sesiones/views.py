import logging
import time
from datetime import timedelta

import jwt as pyjwt
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.utils import timezone
from django.conf import settings

from apps.entrevistas.models import Invitado
from apps.pruebas.models import Pregunta, Opcion
from apps.pruebas.serializers import PruebaCandidatoSerializer

from .models import Sesion, Respuesta, RegistroAuditoria
from .serializers import (
    SesionSerializer,
    SesionDetalleSerializer,
    RespuestaSerializer,
    RegistroAuditoriaSerializer,
)


logger = logging.getLogger(__name__)


def registrar(accion, actor="sistema", usuario=None, sesion=None, entidad=None, entidad_id=None, detalle=None):
    """Registra un evento de auditoría (Capa 4c). Nunca rompe el flujo si algo falla."""
    try:
        RegistroAuditoria.objects.create(
            accion=accion,
            actor=actor,
            usuario=usuario,
            sesion=sesion,
            entidad=entidad,
            entidad_id=entidad_id,
            detalle=detalle,
        )
    except Exception:
        logger.exception("No se pudo registrar auditoría: %s", accion)


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


def _token_para_sesion(token, sesion):
    """
    True si el token del invitado corresponde a la invitación dueña de la sesión.
    Si la sesión no tiene invitación (datos viejos), no hay nada que validar → permite.
    """
    inv = sesion.invitacion
    if inv is None:
        return True
    invitado_id = token.get("invitado_id")
    email = token.get("email")
    return bool((invitado_id and inv.id == invitado_id) or (email and inv.email == email))


def _calificar_objetivas(sesion):
    """
    Califica AUTOMÁTICAMENTE las respuestas objetivas (opción múltiple / V-F con
    opciones): setea puntaje_ia comparando la opción elegida con es_correcta.
    Las abiertas (IA) y de código (Judge0) se dejan sin tocar. Devuelve cuántas calificó.
    """
    objetivas = ("opcion_multiple", "verdadero_falso")
    n = 0
    for r in sesion.respuestas.select_related("pregunta").all():
        preg = r.pregunta
        if preg.formato not in objetivas:
            continue
        contenido = (r.contenido_texto or "").strip()
        if not contenido.isdigit():
            continue  # no es id de opción (ej: V/F escrito) → no auto-calificable
        opcion = Opcion.objects.filter(pregunta=preg, pk=int(contenido)).first()
        if opcion is None:
            continue
        r.puntaje_ia = preg.puntaje if opcion.es_correcta else 0
        r.save(update_fields=["puntaje_ia"])
        n += 1
    return n


def _recalcular_nota(sesion):
    """
    Recalcula la nota final 0-100 ponderada por sección y el estado de corrección.
    Puntaje efectivo de cada respuesta = humano si existe, si no el de IA.
    Una pregunta sin responder cuenta como 0.
    """
    prueba = sesion.entrevista.prueba
    respuestas = {r.pregunta_id: r for r in sesion.respuestas.all()}

    nota_acum = 0.0
    peso_acum = 0
    if prueba is not None:
        for seccion in prueba.secciones.all():
            preguntas = list(seccion.preguntas.all())
            max_sec = sum(p.puntaje for p in preguntas)
            if max_sec == 0:
                continue
            obt = 0.0
            for p in preguntas:
                r = respuestas.get(p.id)
                if r is not None:
                    pf = r.puntaje_humano if r.puntaje_humano is not None else r.puntaje_ia
                    if pf is not None:
                        obt += float(pf)
            nota_acum += (obt / max_sec) * seccion.peso_porcentual
            peso_acum += seccion.peso_porcentual

    sesion.nota_final = round(nota_acum / peso_acum * 100, 2) if peso_acum > 0 else None

    resps = list(respuestas.values())
    con_puntaje = sum(
        1
        for r in resps
        if (r.puntaje_humano if r.puntaje_humano is not None else r.puntaje_ia) is not None
    )
    if resps and con_puntaje == len(resps):
        sesion.estado_correccion = Sesion.Correccion.CORREGIDA
    elif con_puntaje > 0:
        sesion.estado_correccion = Sesion.Correccion.PARCIAL
    else:
        sesion.estado_correccion = Sesion.Correccion.PENDIENTE

    sesion.save(update_fields=["nota_final", "estado_correccion", "fecha_actualizacion"])
    return sesion


def _firmar_jwt_jitsi(room, nombre, email, moderator, exp_ts):
    """
    Firma un JWT para un Jitsi self-hosted (prosody token auth). El mismo secreto
    (JITSI_JWT_APP_SECRET) debe estar en prosody. El flag moderator va en
    context.user (es donde el plugin de Jitsi lo lee), no como claim suelto.
    """
    payload = {
        "iss": settings.JITSI_JWT_APP_ID,
        "aud": settings.JITSI_JWT_APP_ID,
        "sub": settings.JITSI_XMPP_DOMAIN,
        "room": room,
        "exp": int(exp_ts),
        "context": {
            "user": {
                "name": nombre or "",
                "email": email or "",
                "moderator": "true" if moderator else "false",
                # token_affiliation (prosody) lee esto y otorga el rol REAL:
                # owner = moderador (supervisor), member = participante (candidato).
                "affiliation": "owner" if moderator else "member",
            }
        },
    }
    return pyjwt.encode(payload, settings.JITSI_JWT_APP_SECRET, algorithm="HS256")


def _exp_para_invitado(invitado_id):
    """exp del JWT de Jitsi: cubre la cita (fecha + duración) con margen; mínimo 6h."""
    exp_ts = time.time() + 6 * 3600
    inv = Invitado.objects.filter(pk=invitado_id).first() if invitado_id else None
    if inv and inv.entrevista.fecha_programada:
        fin = inv.entrevista.fecha_programada + timedelta(
            minutes=(inv.entrevista.duracion_minutos or 60) + 60
        )
        exp_ts = max(exp_ts, fin.timestamp())
    return exp_ts


class SesionViewSet(ModelViewSet):
    """ViewSet para gestionar sesiones con endpoints adicionales"""
    queryset = Sesion.objects.all()
    serializer_class = SesionSerializer

    def get_queryset(self):
        qs = Sesion.objects.all()
        entrevista_id = self.request.query_params.get("entrevista")
        if entrevista_id:
            qs = qs.filter(entrevista_id=entrevista_id)
        return qs

    @action(detail=True, methods=["get"], url_path="detalle", permission_classes=[AllowAny], authentication_classes=[])
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

        nuevo_estado = request.data.get("nuevo_estado")
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

        observaciones = request.data.get("observaciones", "")
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

    @action(detail=False, methods=["post"], url_path="rendir", permission_classes=[AllowAny], authentication_classes=[])
    def rendir(self, request):
        """
        TODO-EN-UNO para el candidato (Capa 3c, versión simple): con el token,
        crea/recupera su sesión Y devuelve la prueba (sin respuestas correctas),
        en UNA sola respuesta. Así el front hace un único fetch y muestra todo.

        POST /api/sesiones/rendir/   Body: { "token": "<jwt invitado>" }
        → { "sesion": {...}, "prueba": {...} | null }
        """
        token = _decode_invitado_token(request.data.get("token") or _bearer_token(request))
        if token is None:
            return Response({"detail": "Token inválido o expirado."}, status=status.HTTP_401_UNAUTHORIZED)

        entrevista_id = token.get("entrevista_id")
        invitado_id = token.get("invitado_id")
        email = token.get("email")
        invitado = None
        if invitado_id:
            invitado = Invitado.objects.filter(pk=invitado_id).first()
        if invitado is None and entrevista_id and email:
            invitado = Invitado.objects.filter(entrevista_id=entrevista_id, email=email).first()
        if invitado is None:
            return Response({"detail": "Invitación no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        entrevista = invitado.entrevista
        sesion = Sesion.objects.filter(invitacion=invitado).first()
        if sesion is None:
            sesion = Sesion.objects.create(
                entrevista=entrevista,
                creada_por=entrevista.creada_por,
                invitacion=invitado,
                estado=Sesion.Estado.INICIADA,
            )
            registrar(
                "sesion_iniciada",
                actor=f"candidato: {invitado.email}",
                sesion=sesion,
                entidad="sesion",
                entidad_id=sesion.id,
            )
        if invitado.estado == "pendiente":
            invitado.estado = "aceptado"
            invitado.fecha_aceptacion = timezone.now()
            invitado.save(update_fields=["estado", "fecha_aceptacion", "fecha_actualizacion"])

        prueba = entrevista.prueba
        return Response(
            {
                "sesion": SesionSerializer(sesion).data,
                "prueba": PruebaCandidatoSerializer(prueba).data if prueba is not None else None,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="jitsi-token", permission_classes=[AllowAny], authentication_classes=[])
    def jitsi_token(self, request):
        """
        Firma el JWT para entrar a la sala de Jitsi self-hosted. (En la pública
        meet.jit.si no se usa; el front solo lo pide si el dominio es propio.)

        POST /api/sesiones/jitsi-token/
        Body: { "token": "<jwt app>", "watch": <invitado_id> (solo supervisor) }
          - candidato  → sala inv-<su invitado_id>, moderator=false
          - supervisor → sala inv-<watch>,          moderator=true
        → { "jwt": "...", "room": "inv-5", "domain": "<JITSI_DOMAIN>" }
        """
        token = _decode_invitado_token(request.data.get("token") or _bearer_token(request))
        if token is None:
            return Response({"detail": "Token inválido o expirado."}, status=status.HTTP_401_UNAUTHORIZED)

        es_moderador = bool(token.get("moderator"))
        if es_moderador:
            invitado_ref = request.data.get("watch")
            if not invitado_ref:
                return Response(
                    {"detail": "Falta 'watch' (invitado a supervisar)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            invitado_ref = token.get("invitado_id")
            if not invitado_ref:
                return Response({"detail": "Token sin invitado_id."}, status=status.HTTP_400_BAD_REQUEST)

        room = f"inv-{invitado_ref}"
        jwt_str = _firmar_jwt_jitsi(
            room=room,
            nombre=token.get("nombre"),
            email=token.get("email"),
            moderator=es_moderador,
            exp_ts=_exp_para_invitado(invitado_ref),
        )
        return Response(
            {"jwt": jwt_str, "room": room, "domain": settings.JITSI_DOMAIN},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="responder", permission_classes=[AllowAny], authentication_classes=[])
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
        if not _token_para_sesion(token, sesion):
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
        registrar(
            "respuesta_enviada",
            actor=f"candidato: {sesion.invitacion.email}" if sesion.invitacion else "candidato",
            sesion=sesion,
            entidad="respuesta",
            entidad_id=respuesta.id,
            detalle={"pregunta_id": pregunta.id},
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

    @action(detail=True, methods=["post"], url_path="finalizar-candidato", permission_classes=[AllowAny], authentication_classes=[])
    def finalizar_candidato(self, request, pk=None):
        """
        El candidato TERMINA su prueba → sesión finalizada + invitación completada.

        POST /api/sesiones/{sesion_id}/finalizar-candidato/
        Body: { "token": "<jwt invitado>" }
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        token = _decode_invitado_token(request.data.get("token") or _bearer_token(request))
        if token is None:
            return Response({"detail": "Token inválido o expirado."}, status=status.HTTP_401_UNAUTHORIZED)
        if not _token_para_sesion(token, sesion):
            return Response(
                {"detail": "El token no corresponde a esta sesión."},
                status=status.HTTP_403_FORBIDDEN,
            )

        sesion.estado = Sesion.Estado.FINALIZADA
        sesion.fecha_fin = timezone.now()
        sesion.save(update_fields=["estado", "fecha_fin", "fecha_actualizacion"])

        inv = sesion.invitacion
        if inv is not None and inv.estado != "completado":
            inv.estado = "completado"
            inv.save(update_fields=["estado", "fecha_actualizacion"])

        registrar(
            "sesion_finalizada",
            actor=f"candidato: {inv.email}" if inv else "candidato",
            sesion=sesion,
            entidad="sesion",
            entidad_id=sesion.id,
        )
        return Response(SesionSerializer(sesion).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="calificar-auto")
    def calificar_auto(self, request, pk=None):
        """
        Califica automáticamente las preguntas OBJETIVAS de la sesión y recalcula
        la nota. Acción del evaluador (requiere login). Capa 4.

        POST /api/sesiones/{sesion_id}/calificar-auto/
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        calificadas = _calificar_objetivas(sesion)
        _recalcular_nota(sesion)
        registrar(
            "calificacion_automatica",
            actor=getattr(request.user, "username", "evaluador"),
            usuario=request.user if request.user.is_authenticated else None,
            sesion=sesion,
            detalle={"calificadas_auto": calificadas},
        )
        return Response(
            {
                "calificadas_auto": calificadas,
                "nota_final": sesion.nota_final,
                "estado_correccion": sesion.estado_correccion,
                "respuestas": RespuestaSerializer(
                    sesion.respuestas.select_related("pregunta").all(), many=True
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="puntuar")
    def puntuar(self, request, pk=None):
        """
        El evaluador fija el puntaje HUMANO de una respuesta (prevalece sobre la IA)
        y se recalcula la nota. Acción del evaluador (requiere login). Capa 4.

        POST /api/sesiones/{sesion_id}/puntuar/
        Body: { "respuesta_id": 1, "puntaje_humano": 4 }
        """
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        respuesta_id = request.data.get("respuesta_id")
        puntaje = request.data.get("puntaje_humano")
        if respuesta_id is None or puntaje is None:
            return Response(
                {"detail": "Faltan 'respuesta_id' y/o 'puntaje_humano'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            respuesta = sesion.respuestas.select_related("pregunta").get(pk=respuesta_id)
        except Respuesta.DoesNotExist:
            return Response(
                {"detail": "Respuesta no encontrada en esta sesión."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            valor = float(puntaje)
        except (TypeError, ValueError):
            return Response(
                {"detail": "'puntaje_humano' debe ser numérico."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        maximo = float(respuesta.pregunta.puntaje)
        if valor < 0 or valor > maximo:
            return Response(
                {"detail": f"El puntaje debe estar entre 0 y {maximo}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        respuesta.puntaje_humano = valor
        respuesta.save(update_fields=["puntaje_humano"])
        _recalcular_nota(sesion)
        registrar(
            "puntaje_manual",
            actor=getattr(request.user, "username", "evaluador"),
            usuario=request.user if request.user.is_authenticated else None,
            sesion=sesion,
            entidad="respuesta",
            entidad_id=respuesta.id,
            detalle={"puntaje_humano": valor},
        )
        return Response(
            {
                "respuesta": RespuestaSerializer(respuesta).data,
                "nota_final": sesion.nota_final,
                "estado_correccion": sesion.estado_correccion,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="auditoria")
    def auditoria(self, request, pk=None):
        """Rastro de auditoría de la sesión (evaluador logueado). Capa 4c."""
        try:
            sesion = Sesion.objects.get(pk=pk)
        except Sesion.DoesNotExist:
            return Response({"detail": "Sesión no encontrada."}, status=status.HTTP_404_NOT_FOUND)
        qs = sesion.auditoria.all()
        return Response(RegistroAuditoriaSerializer(qs, many=True).data, status=status.HTTP_200_OK)
