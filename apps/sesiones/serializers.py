from rest_framework import serializers

from .models import Sesion, Respuesta


class RespuestaSerializer(serializers.ModelSerializer):
    """Respuesta de un candidato a una pregunta dentro de su sesión (Capa 3)."""

    pregunta_enunciado = serializers.CharField(source="pregunta.enunciado", read_only=True)
    pregunta_formato = serializers.CharField(source="pregunta.formato", read_only=True)
    pregunta_puntaje = serializers.IntegerField(source="pregunta.puntaje", read_only=True)
    puntaje_final = serializers.SerializerMethodField()
    respuesta_legible = serializers.SerializerMethodField()

    class Meta:
        model = Respuesta
        fields = [
            "id",
            "sesion",
            "pregunta",
            "pregunta_enunciado",
            "pregunta_formato",
            "pregunta_puntaje",
            "contenido_texto",
            "respuesta_legible",
            "contenido_url",
            "casos_pasados",
            "tiempo_segundos",
            "puntaje_ia",
            "puntaje_humano",
            "feedback_ia",
            "puntaje_final",
            "enviado_en",
        ]
        read_only_fields = [
            "id",
            "sesion",
            "enviado_en",
            "puntaje_ia",
            "puntaje_humano",
            "feedback_ia",
        ]

    def get_puntaje_final(self, obj):
        """Lo que vale la respuesta: el puntaje humano si existe, si no el de la IA."""
        valor = obj.puntaje_humano if obj.puntaje_humano is not None else obj.puntaje_ia
        return float(valor) if valor is not None else None

    def get_respuesta_legible(self, obj):
        """Texto legible: si el candidato eligió una opción, su texto; si no, el contenido."""
        contenido = obj.contenido_texto or ""
        if contenido.isdigit():
            opcion = obj.pregunta.opciones.filter(pk=int(contenido)).first()
            if opcion is not None:
                return opcion.texto
        return obj.contenido_texto


class SesionSerializer(serializers.ModelSerializer):
    room_name = serializers.UUIDField(read_only=True)

    class Meta:
        model = Sesion
        fields = [
            "id",
            "entrevista",
            "creada_por",
            "room_name",
            "estado",
            "nota_final",
            "estado_correccion",
            "observaciones_internas",
            "fecha_inicio",
            "fecha_fin",
            "fecha_actualizacion",
        ]
        read_only_fields = ["id", "room_name", "fecha_inicio", "fecha_actualizacion"]


class CrearSesionSerializer(serializers.Serializer):
    entrevista_id = serializers.IntegerField()
    creada_por = serializers.IntegerField()


class SesionDetalleSerializer(serializers.ModelSerializer):
    """Serializer con datos completos: sesión, entrevista e invitados"""
    room_name = serializers.UUIDField(read_only=True)
    
    # Datos de la entrevista
    titulo_entrevista = serializers.CharField(source="entrevista.titulo", read_only=True)
    descripcion_entrevista = serializers.CharField(source="entrevista.descripcion", read_only=True)
    evaluador_nombre = serializers.CharField(source="entrevista.evaluador.get_full_name", read_only=True)
    evaluador_email = serializers.CharField(source="entrevista.evaluador.email", read_only=True)
    duracion_minutos = serializers.IntegerField(source="entrevista.duracion_minutos", read_only=True)
    fecha_programada = serializers.DateTimeField(source="entrevista.fecha_programada", read_only=True)
    
    # Invitados
    invitados = serializers.SerializerMethodField()

    class Meta:
        model = Sesion
        fields = [
            "id",
            "room_name",
            "estado",
            "nota_final",
            "estado_correccion",
            "titulo_entrevista",
            "descripcion_entrevista",
            "evaluador_nombre",
            "evaluador_email",
            "duracion_minutos",
            "fecha_programada",
            "fecha_inicio",
            "fecha_fin",
            "observaciones_internas",
            "invitados",
        ]
        read_only_fields = [
            "id",
            "room_name",
            "titulo_entrevista",
            "descripcion_entrevista",
            "evaluador_nombre",
            "evaluador_email",
            "duracion_minutos",
            "fecha_programada",
            "fecha_inicio",
            "fecha_fin",
            "invitados",
        ]

    def get_invitados(self, obj):
        """Obtiene lista de invitados de la entrevista"""
        invitados = obj.entrevista.invitados.all()
        return [
            {
                "id": inv.id,
                "nombre": inv.nombre,
                "email": inv.email,
                "estado": inv.estado,
                "link_invitacion": inv.link_invitacion,
            }
            for inv in invitados
        ]
