from django.conf import settings
from django.db import models

class Conta(models.Model):
    dono = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name="contas",
    )
    titular = models.CharField(max_length=100)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.titular} (R$ {self.saldo})"

class Transacao(models.Model):
    origem = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="enviadas")
    destino = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name="recebidas")
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    idempotency_key = models.CharField(max_length=64, unique=True, null=True, blank=True)
    criada_em = models.DateTimeField(auto_now_add=True)