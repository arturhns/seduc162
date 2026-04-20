from django.db import models


class Designacao(models.Model):
    calculo_modulo = models.ForeignKey("app.CalculoModulo", on_delete=models.PROTECT)
    cargo = models.ForeignKey("app.Cargo", on_delete=models.PROTECT)
    agente = models.ForeignKey("app.AgenteEscolar", on_delete=models.PROTECT)
    data_designacao = models.DateField()
    status = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "designacoes"
