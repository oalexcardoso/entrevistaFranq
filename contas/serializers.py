from decimal import Decimal
from rest_framework import serializers
from .models import Conta, Transacao


class ContaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conta
        fields = ["id", "titular", "saldo", "criada_em"]
        read_only_fields = ["criada_em"]


class TransacaoSerializer(serializers.ModelSerializer):
    origem_titular = serializers.CharField(source="origem.titular", read_only=True)
    destino_titular = serializers.CharField(source="destino.titular", read_only=True)

    class Meta:
        model = Transacao
        fields = ["id", "origem", "origem_titular", "destino", "destino_titular",
                  "valor", "criada_em"]


class TransferenciaSerializer(serializers.Serializer):
    origem_id = serializers.IntegerField()
    destino_id = serializers.IntegerField()
    valor = serializers.DecimalField(max_digits=12, decimal_places=2,
                                     min_value=Decimal("0.01"))

    def validate(self, data):
        if data["origem_id"] == data["destino_id"]:
            raise serializers.ValidationError("Origem e destino devem ser diferentes.")
        return data