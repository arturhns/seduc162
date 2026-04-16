from django.db import models


class EscolaModalidade(models.Model):
    escola = models.ForeignKey("app.Escola", on_delete=models.CASCADE)
    modalidade = models.ForeignKey("app.Modalidade", on_delete=models.PROTECT)

    class Meta:
        db_table = "escola_modalidades"
        constraints = [
            models.UniqueConstraint(fields=["escola", "modalidade"], name="uk_escola_modalidade"),
        ]
