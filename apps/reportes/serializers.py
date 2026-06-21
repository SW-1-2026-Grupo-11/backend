from rest_framework import serializers

from apps.reportes.models import Reporte


class ReporteSerializer(serializers.ModelSerializer):
    # Datos derivados de la sesión para que el front no tenga que cruzar.
    candidato_nombre = serializers.SerializerMethodField()
    entrevista_id = serializers.IntegerField(source="sesion.entrevista_id", read_only=True)
    estado_sesion = serializers.CharField(source="sesion.estado", read_only=True)
    motivo_cierre = serializers.CharField(source="sesion.motivo_cierre", read_only=True, allow_null=True)
    firmado_por_nombre = serializers.CharField(
        source="firmado_por.get_full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = Reporte
        fields = [
            "id",
            "sesion",
            "candidato_nombre",
            "entrevista_id",
            "estado_sesion",
            "motivo_cierre",
            "nota",
            "nivel_riesgo",
            "total_alertas",
            "puntaje_atencion",
            "puntaje_sospecha",
            "resumen_general",
            "resumen_participante",
            "recomendaciones",
            "decision",
            "firmado_por",
            "firmado_por_nombre",
            "fecha_firma",
            "observaciones_evaluador",
            "fecha_creacion",
            "fecha_actualizacion",
        ]
        read_only_fields = [
            "id",
            "nota",
            "nivel_riesgo",
            "total_alertas",
            "puntaje_atencion",
            "puntaje_sospecha",
            "resumen_general",
            "resumen_participante",
            "recomendaciones",
            "firmado_por",
            "fecha_firma",
            "fecha_creacion",
            "fecha_actualizacion",
        ]

    def get_candidato_nombre(self, obj):
        inv = obj.sesion.invitacion if obj.sesion_id else None
        return inv.nombre if inv else None
