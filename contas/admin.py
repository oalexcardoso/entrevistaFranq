from django.contrib import admin
from .models import Conta, Transacao

admin.site.register(Conta)
admin.site.register(Transacao)