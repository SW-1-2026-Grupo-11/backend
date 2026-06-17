from rest_framework import serializers
from .models import Entrevista, Invitado

# este es el serializer de la app entrevistas


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
            "fecha_programada",
            "duracion_minutos",
            "invitados",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "fecha_creacion", "fecha_actualizacion"]


class ProgramarEntrevistaSerializer(serializers.Serializer):
    """Serializer para programar entrevista con invitados"""
    titulo = serializers.CharField(max_length=150)
    descripcion = serializers.CharField(required=False, allow_blank=True)
    evaluador_id = serializers.IntegerField(required=False)
    prueba_id = serializers.IntegerField(required=False)
    fecha_programada = serializers.DateTimeField()
    duracion_minutos = serializers.IntegerField(default=60, min_value=1)
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
