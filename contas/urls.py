from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ContaViewSet, TransacaoViewSet, TransferenciaView, CotacaoDolarView,
    transferir_view, criar_conta_view, cadastro_view,
)

router = DefaultRouter()
router.register("contas", ContaViewSet)
router.register("transacoes", TransacaoViewSet)

urlpatterns = [
    path("transferencias/", TransferenciaView.as_view()),
    path("cotacao-dolar/", CotacaoDolarView.as_view()),
] + router.urls

paginas_urlpatterns = [
    path("transferir/", transferir_view, name="transferir"),
    path("contas/criar/", criar_conta_view, name="criar_conta"),
    path("cadastro/", cadastro_view, name="cadastro"),
]