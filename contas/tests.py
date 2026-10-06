import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from .models import Conta, Transacao

URL = "/api/transferencias/"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def contas(db):
    return (Conta.objects.create(titular="Ana", saldo=100),
            Conta.objects.create(titular="Bia", saldo=0))


def test_transferencia_ok(api, contas):
    ana, bia = contas
    r = api.post(URL, {"origem_id": ana.id, "destino_id": bia.id, "valor": "30.00"}, format="json")
    assert r.status_code == 201
    ana.refresh_from_db(); bia.refresh_from_db()
    assert ana.saldo == Decimal("70.00")
    assert bia.saldo == Decimal("30.00")


def test_saldo_insuficiente_nao_altera_nada(api, contas):
    ana, bia = contas
    r = api.post(URL, {"origem_id": ana.id, "destino_id": bia.id, "valor": "500.00"}, format="json")
    assert r.status_code == 422
    ana.refresh_from_db()
    assert ana.saldo == Decimal("100.00")


def test_idempotencia(api, contas):
    ana, bia = contas
    payload = {"origem_id": ana.id, "destino_id": bia.id, "valor": "10.00"}
    r1 = api.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY="abc")
    r2 = api.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY="abc")
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert Transacao.objects.count() == 1


def test_listagem_sem_n_mais_1(api, contas, django_assert_max_num_queries):
    ana, bia = contas
    for _ in range(20):
        Transacao.objects.create(origem=ana, destino=bia, valor=1)
    with django_assert_max_num_queries(3):
        api.get("/api/transacoes/")