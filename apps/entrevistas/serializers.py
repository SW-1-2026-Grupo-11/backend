from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Entrevista, Invitado

# este es el serializer de la app entrevistas


def _estado_efectivo(entrevista):
    """
    Estado REAL de la convocatoria. Los estados manuales (borrador/cancelada)
    mandan; el resto se DERIVA del tiempo (programada → en_proceso → finalizada).
    Así el front muestra la verdad sin un selector libre que ponga estados a dedo.
    """
    manual = (Entrevista.Estado.BORRADOR, Entrevista.Estado.CANCELADA)
    if entrevista.estado in manual:
        return entrevista.estado
    fp = entrevista.fecha_programada
    if fp is None:
        return entrevista.estado
    ahora = timezone.now()
    dur = entrevista.duracion_minutos
    if not dur and entrevista.prueba is not None:
        dur = entrevista.prueba.duracion_minutos
    dur = dur or 60
    gracia = getattr(settings, "GRACIA_INICIO_MIN", 15)
    fin = fp + timedelta(minutes=dur + gracia)
    if ahora < fp:
        return Entrevista.Estado.PROGRAMADA
    if ahora <= fin:
        return Entrevista.Estado.EN_PROCESO
    return Entrevista.Estado.FINALIZADA


class InvitadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitado
        fields = ["id", "candidato", "nombre", "email", "rol", "estado", "link_invitacion", "fecha_invitacion", "fecha_aceptacion"]
        read_only_fields = ["id", "candidato", "fecha_invitacion", "fecha_aceptacion", "link_invitacion"]


class EntrevistaSerializer(serializers.ModelSerializer):
    invitados = InvitadoSerializer(many=True, read_only=True)
    creada_por_nombre = serializers.CharField(source="creada_por.get_full_name", read_only=True)
    evaluador_nombre = serializers.CharField(source="evaluador.get_full_name", read_only=True, allow_null=True)
    prueba_nombre = serializers.CharField(source="prueba.titulo", read_only=True, allow_null=True)
    # Estado derivado del tiempo (lo que el front debe mostrar). El campo `estado`
    # crudo queda solo para las transiciones manuales (borrador/cancelada).
    estado_efectivo = serializers.SerializerMethodField()

    class Meta:
        model = Entrevista
        fields = [
            "id",
            "titulo",
            "descripcion",
            "creada_por",
            "creada_por_nombre",
            "evaluador",
            "evaluador_nombre",
            "prueba",
            "prueba_nombre",
            "estado",
            "estado_efectivo",
            "fecha_programada",
            "duracion_minutos",
            "invitados",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "fecha_creacion", "fecha_actualizacion"]

    def get_estado_efectivo(self, obj):
        return _estado_efectivo(obj)


class ProgramarEntrevistaSerializer(serializers.Serializer):
    """Serializer para programar entrevista con invitados"""
    titulo = serializers.CharField(max_length=150)
    descripcion = serializers.CharField(required=False, allow_blank=True)
    evaluador_id = serializers.IntegerField(required=False)
    prueba_id = serializers.IntegerField(required=False)
    fecha_programada = serializers.DateTimeField()
    # OPCIONAL: si no se envía, la convocatoria hereda la duración de la prueba.
    duracion_minutos = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    invitados = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
            allow_empty=False,
        ),
        required=False,
    )

    def validate_invitados(self, value):
        """Validar que cada invitado tenga nombre y email"""
        for invitado in value:
            if "nombre" not in invitado or "email" not in invitado:
                raise serializers.ValidationError(
                    "Cada invitado debe tener 'nombre' y 'email'."
                )
        return value
