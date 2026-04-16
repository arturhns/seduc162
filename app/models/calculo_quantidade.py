from django.db import models


class CalculoQuantidade(models.Model):
    calculo_modulo = models.ForeignKey("app.CalculoModulo", on_delete=models.CASCADE)
    cargo = models.ForeignKey("app.Cargo", on_delete=models.PROTECT)
    quantidade = models.IntegerField()

    class Meta:
        db_table = "calculo_quantidades"
