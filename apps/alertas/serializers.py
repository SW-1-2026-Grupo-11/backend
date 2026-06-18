from rest_framework import serializers
from .models import Alerta


class AlertaSerializer(serializers.ModelSerializer):
    # El micro los manda como strings; ya NO se usan para mockear con .first().
    id_entrevista = serializers.CharField(write_only=True, required=False)
    id_participante = serializers.CharField(write_only=True, required=False)
    # Quién es el candidato, derivado de la sesión (1 candidato por sesión).
    participante_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Alerta
        fields = "__all__"
        read_only_fields = ["fecha_creacion", "entrevista", "sesion"]

    def get_participante_nombre(self, obj):
        inv = obj.sesion.invitacion if obj.sesion_id else None
        return inv.nombre if inv else None

    def create(self, validated_data):
        # Los ids string del micro ya no se usan para resolver nada.
        validated_data.pop("id_entrevista", None)
        validated_data.pop("id_participante", None)

        # La SESIÓN es el ancla. El micro manda el session_id dentro de
        # evidencia_json; resolvemos la sesión real y derivamos la entrevista.
        from apps.sesiones.models import Sesion

        evidencia = validated_data.get("evidencia_json") or {}
        session_id = evidencia.get("session_id") if isinstance(evidencia, dict) else None
        sesion = Sesion.objects.filter(pk=session_id).first() if session_id else None

        validated_data["sesion"] = sesion
        validated_data["entrevista"] = sesion.entrevista if sesion else None

        return Alerta.objects.create(**validated_data)
