from django.db import models


class PeriodoProcessamento(models.Model):
    data_inicio = models.DateField()
    data_fim = models.DateField()
    ativo = models.PositiveSmallIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "periodos_processamento"

    def __str__(self) -> str:
        return f"{self.data_inicio} a {self.data_fim}"
