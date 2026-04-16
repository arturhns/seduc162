from django.db import models


class Escola(models.Model):
    codigo_inep = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=150)
    numero_turnos = models.PositiveSmallIntegerField(default=1)
    tipo_merenda = models.PositiveSmallIntegerField(default=0)
    tipo_limpeza = models.PositiveSmallIntegerField(default=0)
    professores_dedicados = models.PositiveSmallIntegerField(default=0)
    ultimo_calculo_modulo = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "escolas"
        indexes = [models.Index(fields=["ultimo_calculo_modulo"], name="idx_ultimo_calculo")]

    def __str__(self) -> str:
        return f"{self.codigo_inep} - {self.nome}"
