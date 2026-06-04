from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def enviar_email_invitacion(
    self,
    nombre_invitado: str,
    email_invitado: str,
    link_invitacion: str,
    titulo_entrevista: str,
    descripcion: str,
    evaluador_nombre: str,
    fecha_programada: str,
    duracion_minutos: int,
):
    """
    Envía email de invitación a un candidato con su link único.
    
    Reintentos: 3 veces con 60 segundos de espera entre intentos.
    """
    try:
        asunto = f"📅 Invitación a Evaluación: {titulo_entrevista}"
        
        mensaje = f"""
Hola {nombre_invitado},

¡Has sido invitado a participar en una evaluación en la plataforma EvalSecure!

📋 DETALLES DE LA EVALUACIÓN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Evaluación: {titulo_entrevista}
Descripción: {descripcion}
Evaluador: {evaluador_nombre}
Fecha y Hora: {fecha_programada}
Duración estimada: {duracion_minutos} minutos

🔗 TU LINK DE ACCESO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{link_invitacion}

⚠️ IMPORTANTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Este link es personal y único para ti
• No compartas tu link con otras personas
• La sesión será monitoreada y grabada
• Asegúrate de tener una conexión a internet estable
• Ingresa 5 minutos antes de la hora programada

Si tienes problemas para acceder, contacta al equipo de soporte.

Saludos,
El equipo de EvalSecure
"""

        email_desde = settings.DEFAULT_FROM_EMAIL
        
        # Envío del email
        send_mail(
            subject=asunto,
            message=mensaje,
            from_email=email_desde,
            recipient_list=[email_invitado],
            fail_silently=False,
        )
        
        logger.info(f"✓ Email enviado exitosamente a {email_invitado} - Evaluación: {titulo_entrevista}")
        return {
            "status": "success",
            "email": email_invitado,
            "mensaje": f"Email enviado a {email_invitado}",
        }
        
    except Exception as exc:
        logger.error(
            f"✗ Error enviando email a {email_invitado}: {str(exc)}\n"
            f"Reintento {self.request.retries}/{self.max_retries}"
        )
        
        # Reintentar si no ha alcanzado el máximo
        raise self.retry(exc=exc)


@shared_task
def enviar_emails_invitaciones_masivas(
    entrevista_id: int,
    invitados: list,
    titulo_entrevista: str,
    descripcion: str,
    evaluador_nombre: str,
    fecha_programada: str,
    duracion_minutos: int,
):
    """
    Encola múltiples tareas de envío de email (una por cada invitado).
    
    Ideal para cuando hay múltiples invitados en una entrevista.
    """
    try:
        emails_encolados = []
        
        for invitado in invitados:
            try:
                # Encolar cada tarea sin bloquear
                enviar_email_invitacion.delay(
                    nombre_invitado=invitado["nombre"],
                    email_invitado=invitado["email"],
                    link_invitacion=invitado["link_invitacion"],
                    titulo_entrevista=titulo_entrevista,
                    descripcion=descripcion,
                    evaluador_nombre=evaluador_nombre,
                    fecha_programada=fecha_programada,
                    duracion_minutos=duracion_minutos,
                )
                
                emails_encolados.append({
                    "email": invitado["email"],
                    "estado": "encolado",
                })
                
            except Exception as e:
                logger.error(f"Error encolando email para {invitado['email']}: {str(e)}")
                emails_encolados.append({
                    "email": invitado["email"],
                    "estado": "error",
                    "error": str(e),
                })
        
        logger.info(
            f"✓ Tareas de email encoladas para entrevista {entrevista_id}: "
            f"{len([e for e in emails_encolados if e['estado'] == 'encolado'])} exitosas, "
            f"{len([e for e in emails_encolados if e['estado'] == 'error'])} con error"
        )
        
        return {
            "entrevista_id": entrevista_id,
            "total_invitados": len(invitados),
            "emails_encolados": emails_encolados,
        }
        
    except Exception as exc:
        logger.error(f"Error crítico en envío masivo de emails: {str(exc)}")
        return {
            "entrevista_id": entrevista_id,
            "status": "error",
            "error": str(exc),
        }
