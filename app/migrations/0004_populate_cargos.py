from django.db import migrations

# IDs alinhados a app.models.cargo.Cargo (TIPO_DIRETOR … TIPO_ASE).
CARGOS = [
    (1, "Diretor", "Diretor", 0), # TIPO_DIRETOR
    (2, "Vice-Diretor", "Vice-Diretor", 0), # TIPO_VICE_DIRETOR
    (3, "Coordenador de Gestão Pedagógica", "CGP", 0), # TIPO_CGP
    (4, "Coordenador de Gestão Pedagógica em Tempo Integral", "CGPG", 0), # TIPO_CGPG
    (5, "Agente de Organização Escolar", "AOE", 1), # TIPO_AOE
    (6, "Agente de Serviços Escolares", "ASE", 1), # TIPO_ASE
]

CARGO_IDS = [pk for pk, _, _, _ in CARGOS]


def populate_cargos(apps, schema_editor):
    Cargo = apps.get_model("app", "Cargo")
    for pk, nome, abreviacao, tipo in CARGOS:
        Cargo.objects.exclude(id=pk).filter(nome=nome).delete()
        Cargo.objects.update_or_create(
            id=pk,
            defaults={"nome": nome, "abreviacao": abreviacao, "tipo": tipo},
        )


def reverse_cargos(apps, schema_editor):
    Cargo = apps.get_model("app", "Cargo")
    Cargo.objects.filter(id__in=CARGO_IDS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0003_populate_modalidades"),
    ]

    operations = [
        migrations.RunPython(populate_cargos, reverse_cargos),
    ]
