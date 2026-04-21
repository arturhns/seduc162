from __future__ import annotations

from collections import defaultdict

from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch, Q, Subquery, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View

from app.forms.designacao import ContratacaoDesignacaoForm
from app.models import (
    AgenteEscolar,
    CalculoModulo,
    CalculoQuantidade,
    Cargo,
    ContratacaoTerceiro,
    Designacao,
    Escola,
    EscolaModalidade,
    Modalidade,
    PeriodoProcessamento,
)
from app.services.designacao_status import calculo_status_designacao


def _ids_ultimos_calculos_periodo_ativo(periodo_ativo: PeriodoProcessamento | None) -> list[int]:
    """Um id de CalculoModulo por escola: o cálculo vigente (`ultimo_calculo`) no período ativo."""
    if periodo_ativo is None:
        return []
    return list(
        CalculoModulo.objects.filter(
            periodo=periodo_ativo, ultimo_calculo=True
        ).values_list("pk", flat=True)
    )


def _agentes_com_designacao_ativa_periodo(
    periodo_ativo: PeriodoProcessamento | None,
) -> set[int]:
    ids_calc = _ids_ultimos_calculos_periodo_ativo(periodo_ativo)
    if not ids_calc:
        return set()
    return set(
        Designacao.objects.filter(
            status=1,
            calculo_modulo_id__in=ids_calc,
        ).values_list("agente_id", flat=True),
    )


def _designacoes_ultimo_por_ultimo_status(
    ultimo: CalculoModulo,
) -> list[Designacao]:
    """
    Por (cargo, agente), mantém apenas o registro mais recente (maior id),
    refletindo o último status no cálculo atual.
    """
    rows = list(
        Designacao.objects.filter(calculo_modulo=ultimo)
        .select_related("agente", "cargo")
        .order_by("-id")
    )
    seen: set[tuple[int, int]] = set()
    out: list[Designacao] = []
    for d in rows:
        key = (int(d.cargo_id), int(d.agente_id))
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    out.sort(key=lambda x: (int(x.cargo_id), (x.agente.nome_completo or "").lower()))
    return out


def _designacoes_anteriores_ativas_por_cargo(
    escola: Escola,
    ultimo: CalculoModulo,
    cargo_ids: list[int],
) -> dict[int, list[Designacao]]:
    # Cálculo imediatamente anterior ao vigente no mesmo período (histórico de designação).
    calculo_anterior_qs = (
        CalculoModulo.objects.filter(
            escola_id=escola.pk,
            periodo_id=ultimo.periodo_id,
        )
        .exclude(pk=ultimo.pk)
        .order_by("-data_calculo", "-id")
        .values("id")[:1]
    )

    anteriores_qs = (
        Designacao.objects.filter(
            calculo_modulo_id=Subquery(calculo_anterior_qs),  #
            status=1,
            cargo_id__in=cargo_ids,
            cargo__tipo=Cargo.TIPO_GESTAO,
        )
        .select_related("agente", "cargo", "calculo_modulo")
        .order_by("cargo_id", "-calculo_modulo__data_calculo", "-id")
    )

    por_cargo: dict[int, list[Designacao]] = defaultdict(list)
    visto_agente_por_cargo: dict[int, set[int]] = defaultdict(set)
    for d in anteriores_qs:
        cid = int(d.cargo_id)
        aid = int(d.agente_id)
        if aid in visto_agente_por_cargo[cid]:
            continue
        visto_agente_por_cargo[cid].add(aid)
        por_cargo[cid].append(d)
    return por_cargo


class DesignacaoAgenteSearchView(View):
    """Autocomplete (lazy): agentes ativos elegíveis para nova designação."""

    def get(self, request, *args, **kwargs):
        escola = get_object_or_404(Escola, pk=kwargs["escola_id"])
        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        ultimo = (
            CalculoModulo.get_ultimo_calculo_periodo(escola, periodo_ativo)
            if periodo_ativo
            else None
        )
        if periodo_ativo is None or ultimo is None:
            return JsonResponse({"results": []})

        q = (request.GET.get("q") or "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})

        excluir_raw = (request.GET.get("excluir") or "").strip()
        excluir: set[int] = set()
        for part in excluir_raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                excluir.add(int(part))
            except ValueError:
                continue

        bloqueados = _agentes_com_designacao_ativa_periodo(periodo_ativo)
        ja_no_calculo_escola = set(
            Designacao.objects.filter(
                calculo_modulo=ultimo,
                calculo_modulo__escola_id=escola.pk,
                status=1,
            ).values_list("agente_id", flat=True)
        )
        excluir_ids = bloqueados | ja_no_calculo_escola | excluir

        qs = (
            AgenteEscolar.objects.filter(status=AgenteEscolar.Status.ATIVO)
            .exclude(pk__in=excluir_ids)
            .filter(
                Q(nome_completo__icontains=q) | Q(matricula_funcional__icontains=q)
            )
            .order_by("nome_completo")[:20]
        )
        results = [
            {
                "id": a.pk,
                "label": f"{a.nome_completo} ({a.matricula_funcional})",
            }
            for a in qs
        ]
        return JsonResponse({"results": results})


class DesignacaoView(View):
    template_name = "designacao/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.escola = get_object_or_404(
            Escola.objects.prefetch_related(
                Prefetch(
                    "escolamodalidade_set",
                    queryset=EscolaModalidade.objects.select_related("modalidade"),
                )
            ),
            pk=kwargs["escola_id"],
        )
        self.periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        self.ultimo_calculo = None
        if self.periodo_ativo:
            self.ultimo_calculo = CalculoModulo.get_ultimo_calculo_periodo(
                self.escola, self.periodo_ativo
            )
        return super().dispatch(request, *args, **kwargs)

    def _calculo_permite_alterar_designacao(self, calculo: CalculoModulo) -> bool:
        if self.periodo_ativo is None:
            return False
        if int(calculo.periodo_id) != int(self.periodo_ativo.pk):
            return False
        ref = CalculoModulo.get_ultimo_calculo_periodo(self.escola, self.periodo_ativo)
        return ref is not None and int(ref.pk) == int(calculo.pk)

    def get(self, request, *args, **kwargs):
        if self.periodo_ativo is None or self.ultimo_calculo is None:
            return TemplateResponse(
                request,
                self.template_name,
                self._contexto_sem_calculo(),
            )

        ctx = self._contexto_formulario()
        return TemplateResponse(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        if self.periodo_ativo is None or self.ultimo_calculo is None:
            messages.error(
                request,
                "Não é possível salvar sem período ativo e cálculo de módulo processado.",
            )
            return redirect("designacao:form", escola_id=self.escola.pk)

        form = ContratacaoDesignacaoForm(request.POST)
        if not form.is_valid():
            ctx = self._contexto_formulario(form=form)
            return TemplateResponse(request, self.template_name, ctx)

        self._sync_contratacoes(form)
        self._persistir_status_designacao_calculo()

        cessar_pk = (request.POST.get("cessar") or "").strip()
        if cessar_pk:
            try:
                pk = int(cessar_pk)
            except (TypeError, ValueError):
                pk = 0
            cessou = self._cessar_designacao(pk)
            if cessou:
                self._persistir_status_designacao_calculo()
                messages.success(request, "Designação cessada.")
            return redirect("designacao:form", escola_id=self.escola.pk)

        if request.POST.get("acao") == "salvar":
            if not self._calculo_permite_alterar_designacao(self.ultimo_calculo):
                messages.error(
                    request,
                    "Não é possível alterar designações: cálculo fora do período ativo "
                    "ou existe módulo mais recente para esta escola no período.",
                )
                return redirect("designacao:form", escola_id=self.escola.pk)
            try:
                self._criar_novas_designacoes()
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("designacao:form", escola_id=self.escola.pk)
            self._persistir_status_designacao_calculo()
            messages.success(request, "Designação salva com sucesso.")

        return redirect("designacao:form", escola_id=self.escola.pk)

    def _cessar_designacao(self, designacao_id: int) -> bool:
        if not designacao_id:
            return False
        des = (
            Designacao.objects.filter(
                pk=designacao_id,
                calculo_modulo__escola_id=self.escola.pk,
                status=1,
            )
            .select_related("calculo_modulo")
            .first()
        )
        if des is None:
            messages.warning(self.request, "Designação não encontrada ou já cessada.")
            return False
        if not self._calculo_permite_alterar_designacao(des.calculo_modulo):
            messages.warning(
                self.request,
                "Não é possível cessar: o cálculo não é o mais recente no período ativo "
                "ou está fora do período ativo.",
            )
            return False
        Designacao.objects.filter(pk=des.pk).update(status=0)
        return True

    def _persistir_status_designacao_calculo(self) -> None:
        calc = self.ultimo_calculo
        if calc is None:
            return
        status_designacao = calculo_status_designacao(calc)
        if int(calc.status_designacao) != status_designacao:
            CalculoModulo.objects.filter(pk=calc.pk).update(status_designacao=status_designacao)
            calc.status_designacao = status_designacao

    def _sync_contratacoes(self, form: ContratacaoDesignacaoForm) -> None:
        situ_aoe = int(form.cleaned_data["situacao_aoe"])
        situ_ase = int(form.cleaned_data["situacao_ase"])
        with transaction.atomic():
            for tipo, situ in (
                (Cargo.TIPO_AOE, situ_aoe),
                (Cargo.TIPO_ASE, situ_ase),
            ):
                obj, _ = ContratacaoTerceiro.objects.get_or_create(
                    calculo_modulo=self.ultimo_calculo,
                    tipo=tipo,
                    defaults={"situacao": situ},
                )
                if int(obj.situacao) != situ:
                    obj.situacao = situ
                    obj.save(update_fields=["situacao"])

    def _criar_novas_designacoes(self) -> None:
        quantidades = list(
            CalculoQuantidade.objects.filter(
                calculo_modulo=self.ultimo_calculo,
                cargo__tipo=Cargo.TIPO_GESTAO,
            ).select_related("cargo")
        )

        ativos_ultimo = defaultdict(int)
        for d in Designacao.objects.filter(
            calculo_modulo=self.ultimo_calculo, status=1
        ).only("cargo_id"):
            ativos_ultimo[int(d.cargo_id)] += 1

        bloqueados_periodo = _agentes_com_designacao_ativa_periodo(self.periodo_ativo)

        novos: list[tuple[int, int]] = []
        for q in quantidades:
            if int(q.cargo.tipo) != Cargo.TIPO_GESTAO:
                continue
            need = int(q.quantidade)
            if need <= 0:
                continue
            field = f"novo_agente_{q.cargo_id}"
            raw_ids: list[int] = []
            for part in self.request.POST.getlist(field):
                s = (part or "").strip()
                if not s:
                    continue
                try:
                    raw_ids.append(int(s))
                except ValueError:
                    continue
            if not raw_ids:
                continue
            if len(raw_ids) != len(set(raw_ids)):
                raise ValueError("Não é permitido repetir o mesmo agente no mesmo cargo.")
            cid = int(q.cargo_id)
            for agente_id in raw_ids:
                if not AgenteEscolar.objects.filter(
                    pk=agente_id, status=AgenteEscolar.Status.ATIVO
                ).exists():
                    raise ValueError("Agente inválido ou inativo.")
                if agente_id in bloqueados_periodo:
                    raise ValueError(
                        "Um ou mais agentes selecionados já possuem designação ativa "
                        "em outra escola (ou nesta) no período ativo."
                    )
                if ativos_ultimo[cid] >= need:
                    raise ValueError(
                        f"A quantidade de designações ativas para o cargo "
                        f"{q.cargo.nome} já atingiu o necessário neste cálculo."
                    )
                novos.append((cid, agente_id))
                ativos_ultimo[cid] += 1
                bloqueados_periodo.add(agente_id)

        hoje = timezone.localdate()
        with transaction.atomic():
            for cargo_id, agente_id in novos:
                Designacao.objects.create(
                    calculo_modulo=self.ultimo_calculo,
                    cargo_id=cargo_id,
                    agente_id=agente_id,
                    data_designacao=hoje,
                    status=1,
                )

    def _contexto_sem_calculo(self) -> dict:
        return {
            "escola": self.escola,
            "periodo_ativo": self.periodo_ativo,
            "ultimo_calculo": self.ultimo_calculo,
            "sem_calculo": True,
            "modalidades_escola_nomes": self._nomes_modalidades(),
            "linhas": [],
            "form": None,
        }

    def _nomes_modalidades(self) -> list[str]:
        return sorted(
            {
                (em.modalidade.nome or "").strip()
                for em in self.escola.escolamodalidade_set.all()
                if (em.modalidade.nome or "").strip()
            }
        )

    def _contexto_formulario(self, form: ContratacaoDesignacaoForm | None = None):
        ultimo = self.ultimo_calculo
        assert ultimo is not None

        quantidades = list(
            CalculoQuantidade.objects.filter(
                calculo_modulo=ultimo, cargo__tipo=Cargo.TIPO_GESTAO
            )
            .select_related("cargo")
            .order_by("cargo_id")
        )

        des_ultimo_dedup = _designacoes_ultimo_por_ultimo_status(ultimo)
        por_cargo_ultimo: dict[int, list[Designacao]] = defaultdict(list)
        for d in des_ultimo_dedup:
            por_cargo_ultimo[int(d.cargo_id)].append(d)

        cargo_ids = [int(q.cargo_id) for q in quantidades]
        por_cargo_anterior = _designacoes_anteriores_ativas_por_cargo(
            self.escola, ultimo, cargo_ids
        )

        contr = {
            c.tipo: c
            for c in ContratacaoTerceiro.objects.filter(calculo_modulo=ultimo)
        }
        aoe = contr.get(Cargo.TIPO_AOE)
        ase = contr.get(Cargo.TIPO_ASE)
        initial = {
            "situacao_aoe": int(aoe.situacao) if aoe else 0,
            "situacao_ase": int(ase.situacao) if ase else 0,
        }
        if form is None:
            form = ContratacaoDesignacaoForm(initial=initial)

        linhas = []
        for q in quantidades:
            cid = int(q.cargo_id)
            need = int(q.quantidade)
            ativos = sum(
                1
                for d in Designacao.objects.filter(
                    calculo_modulo=ultimo, cargo_id=cid, status=1
                ).only("id")
            )
            vagas = max(0, need - ativos)
            linhas.append(
                {
                    "quantidade": q,
                    "designacoes_ultimo": por_cargo_ultimo.get(cid, []),
                    "designacoes_anteriores": por_cargo_anterior.get(cid, []),
                    "pode_designar": need > 0,
                    "vagas_restantes": vagas,
                }
            )

        return {
            "escola": self.escola,
            "periodo_ativo": self.periodo_ativo,
            "ultimo_calculo": ultimo,
            "sem_calculo": False,
            "modalidades_escola_nomes": self._nomes_modalidades(),
            "linhas": linhas,
            "form": form,
        }
