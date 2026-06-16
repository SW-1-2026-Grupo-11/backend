from rest_framework import serializers

from .models import Opcion, Pregunta, Prueba, PruebaEntrevista, Seccion


class PruebaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prueba
        fields = "__all__"


class PruebaEntrevistaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PruebaEntrevista
        fields = "__all__"


class OpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Opcion
        fields = ["id", "pregunta", "texto", "es_correcta", "orden"]
        read_only_fields = ["id"]


class PreguntaSerializer(serializers.ModelSerializer):
    opciones = OpcionSerializer(many=True, read_only=True)

    class Meta:
        model = Pregunta
        fields = [
            "id",
            "seccion",
            "enunciado",
            "formato",
            "puntaje",
            "orden",
            "rubrica",
            "lenguaje",
            "casos_prueba",
            "opciones",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "fecha_creacion", "fecha_actualizacion"]


class SeccionSerializer(serializers.ModelSerializer):
    preguntas = PreguntaSerializer(many=True, read_only=True)

    class Meta:
        model = Seccion
        fields = [
            "id",
            "prueba",
            "titulo",
            "descripcion",
            "orden",
            "peso_porcentual",
            "preguntas",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "fecha_creacion", "fecha_actualizacion"]
