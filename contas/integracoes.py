from datetime import date, timedelta
from decimal import Decimal

import requests

PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
)


class CotacaoIndisponivel(Exception):
    pass


def obter_cotacao_dolar():
    """Busca a cotação PTAX (Banco Central) mais recente disponível.

    A PTAX só é publicada em dias úteis, então consultamos uma janela de 7 dias
    e usamos a última cotação da janela — isso cobre fins de semana e feriados
    sem precisar de uma lista de feriados.
    """
    hoje = date.today()
    inicio = hoje - timedelta(days=7)
    params = {
        "@dataInicial": f"'{inicio.strftime('%m-%d-%Y')}'",
        "@dataFinalCotacao": f"'{hoje.strftime('%m-%d-%Y')}'",
        "$format": "json",
    }

    try:
        resposta = requests.get(PTAX_URL, params=params, timeout=5)
        resposta.raise_for_status()
    except requests.RequestException as exc:
        raise CotacaoIndisponivel("Falha ao consultar o Banco Central") from exc

    valores = resposta.json().get("value", [])
    if not valores:
        raise CotacaoIndisponivel("Nenhuma cotação publicada nos últimos 7 dias")

    cotacao = valores[-1]
    return {
        "compra": Decimal(str(cotacao["cotacaoCompra"])),
        "venda": Decimal(str(cotacao["cotacaoVenda"])),
        "data_hora": cotacao["dataHoraCotacao"],
    }
