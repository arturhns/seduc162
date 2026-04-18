from django.db import migrations

# IDs alinhados a app.models.modalidade.Modalidade (TIPO_*).
MODALIDADES = [
    (1, "Regular"),  # TIPO_REGULAR
    (2, "PEI"),  # TIPO_PEI
    (3, "CASA"),  # TIPO_CASA
    (4, "Sistema Prisional"),  # TIPO_SISTEMA_PRISIONAL
    (5, "CEL"),  # TIPO_CEL
    (6, "EEI"),  # TIPO_EEI
    (7, "CEEJA"),  # TIPO_CEEJA
]

MODALIDADE_IDS = [pk for pk, _ in MODALIDADES]


def populate_modalidades(apps, schema_editor):
    Modalidade = apps.get_model("app", "Modalidade")
    for pk, nome in MODALIDADES:
        # Evita violação de unique(nome) se o mesmo nome existir em outro id.
        Modalidade.objects.exclude(id=pk).filter(nome=nome).delete()
        Modalidade.objects.update_or_create(id=pk, defaults={"nome": nome})


def reverse_modalidades(apps, schema_editor):
    Modalidade = apps.get_model("app", "Modalidade")
    Modalidade.objects.filter(id__in=MODALIDADE_IDS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_agente_escolar_status_choices"),
    ]

    operations = [
        migrations.RunPython(populate_modalidades, reverse_modalidades),
    ]
