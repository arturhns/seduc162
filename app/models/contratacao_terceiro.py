from django.db import models


class ContratacaoTerceiro(models.Model):
    calculo_modulo = models.ForeignKey("app.CalculoModulo", on_delete=models.CASCADE)
    tipo = models.PositiveSmallIntegerField()
    situacao = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "contratacoes_terceiros"
        constraints = [
            models.UniqueConstraint(fields=["calculo_modulo", "tipo"], name="uk_contratacao"),
        ]
