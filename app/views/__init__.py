from .agente_escolar import (
    AgenteEscolarCreateView,
    AgenteEscolarDeleteView,
    AgenteEscolarDetailView,
    AgenteEscolarListView,
    AgenteEscolarUpdateView,
)
from .escola import (
    EscolaCreateView,
    EscolaDeleteView,
    EscolaDetailView,
    EscolaListView,
    EscolaUpdateView,
)

__all__ = [
    "AgenteEscolarListView",
    "AgenteEscolarCreateView",
    "AgenteEscolarUpdateView",
    "AgenteEscolarDetailView",
    "AgenteEscolarDeleteView",
    "EscolaListView",
    "EscolaCreateView",
    "EscolaUpdateView",
    "EscolaDetailView",
    "EscolaDeleteView",
]
