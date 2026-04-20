"""Regras de status da designação no último cálculo do período."""

from __future__ import annotations

from collections import defaultdict

from app.models import CalculoQuantidade, Cargo, ContratacaoTerceiro, Designacao


def calculo_status_designacao(
    calculo,
    *,
    quantidades: list[CalculoQuantidade] | None = None,
    contratacoes: dict[int, ContratacaoTerceiro] | None = None,
    designacoes_ativas_por_cargo: dict[int, int] | None = None,
    tem_qualquer_designacao: bool | None = None,
) -> int:
    """
    Retorna: 0 pendente, 1 em andamento, 2 concluído.

    Regras (último CalculoModulo do período):
    - Concluído: todos os cargos de gestão (tipo gestão) com quantidade > 0 têm
      contagem de designações ativas (status=1) >= quantidade, sem excesso por
      cargo; AOE e ASE cobertos por ContratacaoTerceiro com situacao=1 (não por
      Designacao — as linhas de CalculoQuantidade desses cargos são ignoradas
      na contagem de designações).
    - Em andamento: não concluído e (excesso de ativos por cargo de gestão, ou
      existe alguma Designacao no cálculo, ou existe ContratacaoTerceiro com
      situacao=1).
    - Pendente: não concluído e não em andamento.
    """
    if calculo is None:
        return 0

    qtds = quantidades
    if qtds is None:
        qtds = list(
            CalculoQuantidade.objects.filter(calculo_modulo=calculo).select_related(
                "cargo"
            )
        )

    contr = contratacoes
    if contr is None:
        contr = {
            c.tipo: c
            for c in ContratacaoTerceiro.objects.filter(calculo_modulo=calculo)
        }

    ativos = designacoes_ativas_por_cargo
    tem_alguma = tem_qualquer_designacao
    if ativos is None or tem_alguma is None:
        ativos = defaultdict(int)
        tem_alguma = False
        for d in Designacao.objects.filter(calculo_modulo=calculo).only(
            "cargo_id", "status"
        ):
            tem_alguma = True
            if int(d.status) == 1:
                ativos[int(d.cargo_id)] += 1

    aoe = contr.get(Cargo.TIPO_AOE)
    ase = contr.get(Cargo.TIPO_ASE)
    contratos_ok = (
        aoe is not None
        and ase is not None
        and int(aoe.situacao) == 1
        and int(ase.situacao) == 1
    )

    cargos_ok = True
    # Excesso: mais designações ativas (status=1) do que a vaga prevista em CalculoQuantidade
    # para o cargo — não conclui e permanece "Em andamento" até regularizar.
    tem_excesso = False
    for cq in qtds:
        if int(cq.cargo.tipo) != int(Cargo.TIPO_GESTAO):
            continue
        need = int(cq.quantidade)
        if need <= 0:
            continue
        cid = int(cq.cargo_id)
        cnt = ativos.get(cid, 0)
        if cnt < need:
            cargos_ok = False
        if cnt > need:
            tem_excesso = True

    if contratos_ok and cargos_ok and not tem_excesso:
        return 2

    tem_contrato_em_andamento = any(int(c.situacao) == 1 for c in contr.values())

    if tem_excesso or tem_alguma or tem_contrato_em_andamento:
        return 1

    return 0
