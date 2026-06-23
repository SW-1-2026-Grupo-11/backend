import json
import logging

import firebase_admin
from django.conf import settings
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)


def _get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    if not settings.FIREBASE_CREDENTIALS_JSON:
        logger.warning("FIREBASE_CREDENTIALS_JSON no configurado; push deshabilitado.")
        return None

    creds_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
    return firebase_admin.initialize_app(credentials.Certificate(creds_dict))


def enviar_push(fcm_token: str, titulo: str, cuerpo: str) -> bool:
    """Envía una notificación push a un dispositivo. False si falla (token inválido, no configurado, etc.)."""
    if not fcm_token:
        return False

    app = _get_firebase_app()
    if app is None:
        return False

    try:
        mensaje = messaging.Message(
            notification=messaging.Notification(title=titulo, body=cuerpo),
            token=fcm_token,
        )
        messaging.send(mensaje, app=app)
        return True
    except Exception as e:
        logger.error(f"Error enviando push a token {fcm_token[:20]}...: {e}")
        return False
