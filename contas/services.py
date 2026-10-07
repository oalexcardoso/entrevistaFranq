from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import F
from .models import Conta, Transacao

User = get_user_model()


class SaldoInsuficiente(Exception):
    pass


class MesmaConta(Exception):
    pass


class ContaNaoPertenceAoUsuario(Exception):
    pass


class UsuarioJaExiste(Exception):
    pass


@transaction.atomic
def criar_usuario_com_conta(username, password, titular, saldo_inicial):
    if User.objects.filter(username=username).exists():
        raise UsuarioJaExiste()

    validate_password(password)  

    usuario = User.objects.create_user(username=username, password=password)
    conta = Conta.objects.create(dono=usuario, titular=titular, saldo=saldo_inicial)
    return usuario, conta


@transaction.atomic
def transferir(origem_id, destino_id, valor: Decimal, idempotency_key=None, usuario=None):
    if origem_id == destino_id:
        raise MesmaConta()

    # Idempotencia
    if idempotency_key:
        existente = Transacao.objects.filter(idempotency_key=idempotency_key).first()
        if existente:
            return existente, False

    # Trava as duas contas
    contas = {
        c.id: c
        for c in Conta.objects.select_for_update().filter(id__in=[origem_id, destino_id]).order_by("id")
    }
    if len(contas) != 2:
        raise Conta.DoesNotExist()

    origem = contas[origem_id]

    # Só o dono da conta de origem pode mandar dinheiro dela
    if usuario is not None and origem.dono_id is not None and origem.dono_id != usuario.id:
        raise ContaNaoPertenceAoUsuario()

    if origem.saldo < valor:
        raise SaldoInsuficiente()

    Conta.objects.filter(id=origem_id).update(saldo=F("saldo") - valor)
    Conta.objects.filter(id=destino_id).update(saldo=F("saldo") + valor)

    transacao = Transacao.objects.create(
        origem_id=origem_id, destino_id=destino_id,
        valor=valor, idempotency_key=idempotency_key,
    )
    return transacao, True