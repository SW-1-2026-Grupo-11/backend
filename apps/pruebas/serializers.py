from rest_framework import serializers

from .models import Opcion, Pregunta, Prueba, Seccion


class PruebaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prueba
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


# ─── Serializers para el CANDIDATO (Capa 3c) ────────────────────────────────────
# Exponen el contenido de la prueba para rendirla SIN filtrar datos de calificación:
# nada de es_correcta, rubrica ni casos_prueba.


class OpcionCandidatoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Opcion
        fields = ["id", "texto", "orden"]


class PreguntaCandidatoSerializer(serializers.ModelSerializer):
    opciones = OpcionCandidatoSerializer(many=True, read_only=True)

    class Meta:
        model = Pregunta
        fields = ["id", "enunciado", "formato", "puntaje", "orden", "lenguaje", "opciones"]


class SeccionCandidatoSerializer(serializers.ModelSerializer):
    preguntas = PreguntaCandidatoSerializer(many=True, read_only=True)

    class Meta:
        model = Seccion
        fields = ["id", "titulo", "tipo", "descripcion", "orden", "peso_porcentual", "preguntas"]


class PruebaCandidatoSerializer(serializers.ModelSerializer):
    secciones = SeccionCandidatoSerializer(many=True, read_only=True)

    class Meta:
        model = Prueba
        fields = ["id", "titulo", "descripcion", "duracion_minutos", "secciones"]
