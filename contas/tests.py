import pytest
from decimal import Decimal
from unittest.mock import patch
from rest_framework.test import APIClient
from .models import Conta, Transacao
from .integracoes import CotacaoIndisponivel

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

def test_transferencia_para_mesma_conta_e_rejeitada(api, contas):
    ana, _bia = contas
    r = api.post(URL, {"origem_id": ana.id, "destino_id": ana.id, "valor": "10.00"}, format="json")
    assert r.status_code == 422
    ana.refresh_from_db()
    assert ana.saldo == Decimal("100.00")
    assert Transacao.objects.count() == 0

def test_idempotencia(api, contas):
    ana, bia = contas
    payload = {"origem_id": ana.id, "destino_id": bia.id, "valor": "10.00"}
    r1 = api.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY="abc")
    r2 = api.post(URL, payload, format="json", HTTP_IDEMPOTENCY_KEY="abc")
    assert (r1.status_code, r2.status_code) == (201, 200)
    assert Transacao.objects.count() == 1

def test_formulario_web_tambem_e_idempotente(client, contas, django_user_model):
    ana, bia = contas
    usuario = django_user_model.objects.create_user("teste_form", password="senha123")
    client.force_login(usuario)

    payload = {
        "origem_id": ana.id, "destino_id": bia.id, "valor": "5.00",
        "idempotency_key": "token-do-hidden-input",
    }
    client.post("/transferir/", payload)
    client.post("/transferir/", payload) # simulando reenvio

    assert Transacao.objects.count() == 1
    ana.refresh_from_db()
    assert ana.saldo == Decimal("95.00")

def test_cotacao_dolar_ok(api):
    cotacao_falsa = {"compra": Decimal("5.00"), "venda": Decimal("5.01"), "data_hora": "2026-10-06 13:00:00"}
    with patch("contas.views.obter_cotacao_dolar", return_value=cotacao_falsa):
        r = api.get("/api/cotacao-dolar/")
    assert r.status_code == 200
    assert r.data["compra"] == Decimal("5.00")

def test_cotacao_dolar_indisponivel_retorna_503(api):
    with patch("contas.views.obter_cotacao_dolar", side_effect=CotacaoIndisponivel("fora do ar")):
        r = api.get("/api/cotacao-dolar/")
    assert r.status_code == 503

def test_cadastro_cria_usuario_e_conta_vinculada(client, django_user_model):
    r = client.post("/cadastro/", {
        "username": "novo_user", "password": "SenhaForteX1",
        "titular": "Conta do Novo", "saldo": "50.00",
    })
    assert r.status_code == 302
    usuario = django_user_model.objects.get(username="novo_user")
    conta = Conta.objects.get(titular="Conta do Novo")
    assert conta.dono_id == usuario.id
    assert conta.saldo == Decimal("50.00")


def test_cadastro_rejeita_usuario_duplicado(client, django_user_model):
    django_user_model.objects.create_user("repetido", password="SenhaForteX1")
    r = client.post("/cadastro/", {
        "username": "repetido", "password": "OutraSenhaX2",
        "titular": "Conta X", "saldo": "0",
    })
    assert r.status_code == 200 
    assert not Conta.objects.filter(titular="Conta X").exists()


def test_cadastro_rejeita_senha_fraca(client, django_user_model):
    r = client.post("/cadastro/", {
        "username": "fraco", "password": "123",
        "titular": "Conta Y", "saldo": "0",
    })
    assert r.status_code == 200
    assert not django_user_model.objects.filter(username="fraco").exists()


def test_so_o_dono_pode_transferir_da_propria_conta(client, django_user_model):
    dono = django_user_model.objects.create_user("dono", password="SenhaForteX1")
    outro = django_user_model.objects.create_user("outro", password="SenhaForteX1")
    conta_dono = Conta.objects.create(titular="Conta do Dono", saldo=100, dono=dono)
    conta_outro = Conta.objects.create(titular="Conta do Outro", saldo=100, dono=outro)

    client.force_login(outro)
    r = client.post("/transferir/", {
        "origem_id": conta_dono.id, "destino_id": conta_outro.id, "valor": "10.00",
        "idempotency_key": "tentativa-indevida",
    })
    assert r.status_code == 200 
    conta_dono.refresh_from_db()
    assert conta_dono.saldo == Decimal("100.00")
    assert Transacao.objects.count() == 0


def test_dono_consegue_transferir_da_propria_conta_pra_qualquer_destino(client, django_user_model):
    dono = django_user_model.objects.create_user("dono2", password="SenhaForteX1")
    outro = django_user_model.objects.create_user("outro2", password="SenhaForteX1")
    conta_dono = Conta.objects.create(titular="Conta do Dono 2", saldo=100, dono=dono)
    conta_outro = Conta.objects.create(titular="Conta do Outro 2", saldo=0, dono=outro)

    client.force_login(dono)
    r = client.post("/transferir/", {
        "origem_id": conta_dono.id, "destino_id": conta_outro.id, "valor": "10.00",
        "idempotency_key": "transferencia-valida",
    })
    assert r.status_code == 302
    conta_dono.refresh_from_db(); conta_outro.refresh_from_db()
    assert conta_dono.saldo == Decimal("90.00")
    assert conta_outro.saldo == Decimal("10.00")


def test_api_tambem_rejeita_origem_de_outro_dono_quando_autenticado(contas, django_user_model):
    from rest_framework.test import APIClient
    dono = django_user_model.objects.create_user("dono_api", password="SenhaForteX1")
    ana, bia = contas
    ana.dono = dono
    ana.save(update_fields=["dono"])

    api_anonimo = APIClient()
    r = api_anonimo.post(URL, {"origem_id": ana.id, "destino_id": bia.id, "valor": "5.00"}, format="json")
    assert r.status_code == 201 

    outro = django_user_model.objects.create_user("outro_api", password="SenhaForteX1")
    api_logado = APIClient()
    api_logado.force_authenticate(user=outro)
    r2 = api_logado.post(URL, {"origem_id": ana.id, "destino_id": bia.id, "valor": "5.00"}, format="json")
    assert r2.status_code == 403


def test_listagem_sem_n_mais_1(api, contas, django_assert_max_num_queries):
    ana, bia = contas
    for _ in range(20):
        Transacao.objects.create(origem=ana, destino=bia, valor=1)
    with django_assert_max_num_queries(3):
        api.get("/api/transacoes/")