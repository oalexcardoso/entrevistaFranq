from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Conta, Transacao
from .serializers import ContaSerializer, TransacaoSerializer, TransferenciaSerializer
from .services import transferir, SaldoInsuficiente


class ContaViewSet(viewsets.ModelViewSet):
    queryset = Conta.objects.all().order_by("id")
    serializer_class = ContaSerializer


class TransacaoViewSet(viewsets.ReadOnlyModelViewSet):
    # select_related evita N+1: busca origem e destino no mesmo JOIN
    queryset = Transacao.objects.select_related("origem", "destino").order_by("-criada_em")
    serializer_class = TransacaoSerializer


class TransferenciaView(APIView):
    def post(self, request):
        serializer = TransferenciaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transacao, criada = transferir(
                **serializer.validated_data,
                idempotency_key=request.headers.get("Idempotency-Key"),
            )
        except SaldoInsuficiente:
            return Response({"erro": "Saldo insuficiente"}, status=422)
        except Conta.DoesNotExist:
            return Response({"erro": "Conta não encontrada"}, status=404)

        return Response(TransacaoSerializer(transacao).data, status=201 if criada else 200)