from __future__ import annotations

import csv
import io
import unicodedata
from typing import Any

from django.db.models import OuterRef, Subquery
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from app.forms.relatorio_designacao import RelatorioDesignacaoFiltroForm
from app.models import Designacao, PeriodoProcessamento, CalculoModulo


def _periodos_iniciados_qs():
    hoje = timezone.now().date()
    return PeriodoProcessamento.objects.filter(data_inicio__lte=hoje).order_by("-data_inicio")


def _periodo_padrao() -> PeriodoProcessamento | None:
    ativo = PeriodoProcessamento.get_periodo_ativo()
    if ativo is not None:
        return ativo
    return _periodos_iniciados_qs().first()


def _designacoes_queryset(periodo: PeriodoProcessamento):
    return (
        Designacao.objects.filter(calculo_modulo__periodo=periodo)
        .select_related("calculo_modulo", "calculo_modulo__escola", "agente", "cargo")
        .order_by("calculo_modulo__escola__nome", "-data_designacao", "-pk")
    )


def _ascii_pdf_safe(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    nkfd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nkfd if not unicodedata.combining(c)).encode(
        "ascii", "ignore"
    ).decode("ascii")


class PeriodoRelatorioAutocompleteView(View):
    """Autocomplete (lazy) de períodos já iniciados (mínimo 2 caracteres na busca)."""

    def get(self, request, *args, **kwargs):
        q = (request.GET.get("q") or "").strip().lower()
        if len(q) < 2:
            return JsonResponse({"results": []})

        results = []
        for p in _periodos_iniciados_qs().iterator():
            label = (
                f"{p.data_inicio.strftime('%d/%m/%Y')} a "
                f"{p.data_fim.strftime('%d/%m/%Y')}"
            )
            if q in label.lower():
                results.append({"id": p.pk, "label": label})
            if len(results) >= 20:
                break
        return JsonResponse({"results": results})


class RelatorioDesignacaoView(ListView):
    """Relatório paginado de designações por período."""

    template_name = "relatorios/designacao.html"
    context_object_name = "designacoes"
    paginate_by = 15

    def get(self, request, *args, **kwargs):
        self._periodo = self._resolver_periodo(request)
        return super().get(request, *args, **kwargs)

    def _resolver_periodo(self, request) -> PeriodoProcessamento | None:
        raw = (request.GET.get("periodo") or "").strip()
        padrao = _periodo_padrao()
        if not raw:
            return padrao
        form = RelatorioDesignacaoFiltroForm({"periodo": raw})
        if form.is_valid():
            return form.cleaned_data["periodo"]
        return padrao

    def get_queryset(self):
        if self._periodo is None:
            return Designacao.objects.none()
        return _designacoes_queryset(self._periodo)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self._periodo
        label = ""
        if p is not None:
            label = (
                f"{p.data_inicio.strftime('%d/%m/%Y')} a "
                f"{p.data_fim.strftime('%d/%m/%Y')}"
            )
        ctx.update(
            {
                "periodo": p,
                "periodo_label": label,
                "periodo_eh_ativo": bool(p and p.esta_ativo),
            }
        )
        return ctx


class RelatorioDesignacaoExportCsvView(View):
    def get(self, request, *args, **kwargs):
        periodo = self._periodo(request)
        if periodo is None:
            return HttpResponse("Nenhum periodo valido.", status=400, content_type="text/plain; charset=utf-8")

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "Escola",
                "Data calculo modulo",
                "Calculo ativo no periodo",
                "Nome agente",
                "Matricula funcional",
                "Cargo",
                "Status designacao",
                "Data designacao",
            ]
        )
        for d in _designacoes_queryset(periodo).iterator():
            w.writerow(
                [
                    d.calculo_modulo.escola.nome,
                    d.calculo_modulo.data_calculo.strftime("%d/%m/%Y %H:%M"),
                    "Sim" if d.calculo_modulo.ultimo_calculo else "Não",
                    d.agente.nome_completo,
                    d.agente.matricula_funcional,
                    d.cargo.nome,
                    "Ativo" if int(d.status) == 1 else "Cessado",
                    d.data_designacao.strftime("%d/%m/%Y"),
                ]
            )
        response = HttpResponse(
            "\ufeff" + buf.getvalue(),
            content_type="text/csv; charset=utf-8",
        )
        fname = f"relatorio_designacao_{periodo.pk}.csv"
        response["Content-Disposition"] = f'attachment; filename="{fname}"'
        return response

    def _periodo(self, request) -> PeriodoProcessamento | None:
        form = RelatorioDesignacaoFiltroForm(request.GET)
        return form.cleaned_data["periodo"] if form.is_valid() else None


class RelatorioDesignacaoExportPdfView(View):
    def get(self, request, *args, **kwargs):
        periodo = self._periodo(request)
        if periodo is None:
            return HttpResponse("Nenhum periodo valido.", status=400, content_type="text/plain; charset=utf-8")

        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import landscape, A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except ImportError:
            return HttpResponse(
                "Biblioteca reportlab não instalada.",
                status=500,
                content_type="text/plain; charset=utf-8",
            )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=_ascii_pdf_safe(f"Relatório de Designações {periodo.pk}"),
        )
        styles = getSampleStyleSheet()
        story = []
        story.append(
            Paragraph(
                _ascii_pdf_safe(
                    f"Relatório de Designações - Período {periodo.data_inicio} a {periodo.data_fim}"
                ),
                styles["Title"],
            )
        )
        story.append(Spacer(1, 6 * mm))

        header = [
            "Escola",
            "Cálculo (data)",
            "Ativo no período?",
            "Agente",
            "Matrícula Funcional",
            "Cargo",
            "Status",
            "Data de Designação",
        ]
        data = [header]
        for d in _designacoes_queryset(periodo).iterator():
            data.append(
                [
                    _ascii_pdf_safe(d.calculo_modulo.escola.nome),
                    _ascii_pdf_safe(d.calculo_modulo.data_calculo.strftime("%d/%m/%Y %H:%M")),
                    "Sim" if d.calculo_modulo.ultimo_calculo else "Não",
                    _ascii_pdf_safe(d.agente.nome_completo),
                    _ascii_pdf_safe(d.agente.matricula_funcional),
                    _ascii_pdf_safe(d.cargo.nome),
                    "Ativo" if int(d.status) == 1 else "Cessado",
                    _ascii_pdf_safe(d.data_designacao.strftime("%d/%m/%Y")),
                ]
            )

        tbl = Table(data, repeatRows=1, hAlign="LEFT")
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
                ]
            )
        )
        story.append(tbl)
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="relatorio_designacao_{periodo.pk}.pdf"'
        return response

    def _periodo(self, request) -> PeriodoProcessamento | None:
        form = RelatorioDesignacaoFiltroForm(request.GET)
        return form.cleaned_data["periodo"] if form.is_valid() else None
