from rest_framework import serializers

from .models import Candidato


class CandidatoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidato
        fields = [
            "id",
            "nombre",
            "email",
            "documento",
            "telefono",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "fecha_creacion", "fecha_actualizacion"]
