import uuid
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import redirect, render
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Conta, Transacao
from .serializers import ContaSerializer, TransacaoSerializer, TransferenciaSerializer
from .services import (
    transferir, SaldoInsuficiente, MesmaConta, ContaNaoPertenceAoUsuario,
    criar_usuario_com_conta, UsuarioJaExiste,
)
from .integracoes import obter_cotacao_dolar, CotacaoIndisponivel


class ContaViewSet(viewsets.ModelViewSet):
    queryset = Conta.objects.all().order_by("id")
    serializer_class = ContaSerializer


class TransacaoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Transacao.objects.select_related("origem", "destino").order_by("-criada_em")
    serializer_class = TransacaoSerializer


class TransferenciaView(APIView):
    def post(self, request):
        serializer = TransferenciaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = request.user if request.user.is_authenticated else None
        try:
            transacao, criada = transferir(
                **serializer.validated_data,
                idempotency_key=request.headers.get("Idempotency-Key"),
                usuario=usuario,
            )
        except SaldoInsuficiente:
            return Response({"erro": "Saldo insuficiente"}, status=422)
        except MesmaConta:
            return Response({"erro": "Origem e destino devem ser diferentes"}, status=422)
        except ContaNaoPertenceAoUsuario:
            return Response({"erro": "Essa conta de origem não é sua"}, status=403)
        except Conta.DoesNotExist:
            return Response({"erro": "Conta não encontrada"}, status=404)

        return Response(TransacaoSerializer(transacao).data, status=201 if criada else 200)


class CotacaoDolarView(APIView):
    def get(self, request):
        try:
            cotacao = obter_cotacao_dolar()
        except CotacaoIndisponivel as exc:
            return Response({"erro": str(exc)}, status=503)
        return Response(cotacao)


@login_required
def transferir_view(request):
    if request.method == "POST":
        serializer = TransferenciaSerializer(data=request.POST)
        if serializer.is_valid():
            try:
                transacao, criada = transferir(
                    **serializer.validated_data,
                    idempotency_key=request.POST.get("idempotency_key"),
                    usuario=request.user,
                )
                if criada:
                    messages.success(
                        request,
                        f"Transferência de R$ {transacao.valor} enviada com sucesso.",
                    )
                else:
                    messages.info(request, "Essa transferência já havia sido processada.")
                return redirect("transferir")
            except SaldoInsuficiente:
                messages.error(request, "Saldo insuficiente.")
            except MesmaConta:
                messages.error(request, "Origem e destino devem ser diferentes.")
            except ContaNaoPertenceAoUsuario:
                messages.error(request, "Essa conta de origem não é sua.")
            except Conta.DoesNotExist:
                messages.error(request, "Conta de origem ou destino não encontrada.")
        else:
            for erros in serializer.errors.values():
                for erro in erros:
                    messages.error(request, erro)

    minhas_contas = Conta.objects.filter(dono=request.user).order_by("titular")
    contas = Conta.objects.all().order_by("titular")
    ultimas = Transacao.objects.select_related("origem", "destino").order_by("-criada_em")[:10]
    try:
        cotacao_dolar = obter_cotacao_dolar()
    except CotacaoIndisponivel:
        cotacao_dolar = None

    return render(request, "contas/transferir.html", {
        "minhas_contas": minhas_contas,
        "contas": contas,
        "ultimas": ultimas,
        "idempotency_key": uuid.uuid4(),
        "cotacao_dolar": cotacao_dolar,
    })


@login_required
def criar_conta_view(request):
    if request.method == "POST":
        serializer = ContaSerializer(data=request.POST)
        if serializer.is_valid():
            conta = serializer.save(dono=request.user)
            messages.success(request, f"Conta de {conta.titular} criada com sucesso.")
            return redirect("criar_conta")
        for erros in serializer.errors.values():
            for erro in erros:
                messages.error(request, erro)

    contas = Conta.objects.all().order_by("titular")
    return render(request, "contas/criar_conta.html", {"contas": contas})


def cadastro_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        titular = request.POST.get("titular", "").strip()
        saldo_bruto = request.POST.get("saldo") or "0"

        if not username or not password or not titular:
            messages.error(request, "Usuário, senha e titular da conta são obrigatórios.")
            return render(request, "contas/cadastro.html")

        try:
            saldo_inicial = Decimal(saldo_bruto)
        except InvalidOperation:
            messages.error(request, "Saldo inicial inválido.")
        else:
            try:
                criar_usuario_com_conta(username, password, titular, saldo_inicial)
            except UsuarioJaExiste:
                messages.error(request, "Esse nome de usuário já existe.")
            except DjangoValidationError as exc:
                for erro in exc.messages:
                    messages.error(request, erro)
            else:
                messages.success(request, "Cadastro feito com sucesso! Já pode entrar.")
                return redirect("login")

    return render(request, "contas/cadastro.html")