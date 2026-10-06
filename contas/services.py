from decimal import Decimal
from django.db import transaction
from django.db.models import F
from .models import Conta, Transacao


class SaldoInsuficiente(Exception):
    pass


@transaction.atomic
def transferir(origem_id, destino_id, valor: Decimal, idempotency_key=None):
    # 1. Idempotência: se essa requisição já foi processada, devolve o resultado anterior
    if idempotency_key:
        existente = Transacao.objects.filter(idempotency_key=idempotency_key).first()
        if existente:
            return existente, False

    # 2. Trava as duas contas (ordenadas por id para evitar deadlock)
    contas = {
        c.id: c
        for c in Conta.objects.select_for_update()
        .filter(id__in=[origem_id, destino_id])
        .order_by("id")
    }
    if len(contas) != 2:
        raise Conta.DoesNotExist()

    origem = contas[origem_id]
    if origem.saldo < valor:
        raise SaldoInsuficiente()

    # 3. Atualiza no banco de forma atômica
    Conta.objects.filter(id=origem_id).update(saldo=F("saldo") - valor)
    Conta.objects.filter(id=destino_id).update(saldo=F("saldo") + valor)

    transacao = Transacao.objects.create(
        origem_id=origem_id, destino_id=destino_id,
        valor=valor, idempotency_key=idempotency_key,
    )
    return transacao, True