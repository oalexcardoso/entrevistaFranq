from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ContaViewSet, TransacaoViewSet, TransferenciaView

router = DefaultRouter()
router.register("contas", ContaViewSet)
router.register("transacoes", TransacaoViewSet)

urlpatterns = [
    path("transferencias/", TransferenciaView.as_view()),
] + router.urls