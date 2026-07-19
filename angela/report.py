"""
angela/report.py
Estruturas de dados imutáveis que Angela produz ao final de cada
investigação. Servem de contrato entre Angela ↔ AURA ↔ UI.

Toda análise termina em `InvestigationReport`. Toda modificação
proposta é um `Patch` que ainda precisa de aprovação humana.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Optional, Any
import json


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    LOW = "low"          # <50% — hipótese fraca
    MEDIUM = "medium"    # 50–80% — evidência parcial
    HIGH = "high"        # 80–95% — evidência sólida
    VERY_HIGH = "very_high"  # >95% — reproduzido/testado


@dataclass
class Hypothesis:
    """Uma hipótese sobre causa raiz."""
    description: str
    evidence: List[str] = field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM
    rejected: bool = False
    rejection_reason: str = ""


@dataclass
class TestResult:
    name: str
    passed: bool
    output: str = ""
    duration_ms: int = 0


@dataclass
class Patch:
    """Alteração proposta. Nunca aplicada sem confirmação humana."""
    file: str
    description: str
    diff: str = ""           # unified diff textual
    new_content: str = ""    # conteúdo integral do arquivo (Angela lê o arquivo inteiro)
    reason: str = ""
    preserves_compat: bool = True
    reversible: bool = True


@dataclass
class InvestigationReport:
    """Contrato de saída de qualquer investigação da Angela."""
    request: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    files_read: List[str] = field(default_factory=list)
    architecture_notes: List[str] = field(default_factory=list)
    logs_reviewed: List[str] = field(default_factory=list)

    hypotheses: List[Hypothesis] = field(default_factory=list)
    root_cause: str = ""
    root_cause_confidence: Confidence = Confidence.MEDIUM

    proposed_patches: List[Patch] = field(default_factory=list)
    tests_run: List[TestResult] = field(default_factory=list)

    impact: str = ""
    severity: Severity = Severity.INFO
    summary: str = ""

    # Quando Angela não consegue investigar (backend indisponível, etc)
    error: Optional[str] = None

    def is_actionable(self) -> bool:
        return bool(self.proposed_patches) and self.error is None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Enums → strings serializáveis
        d["root_cause_confidence"] = self.root_cause_confidence.value
        d["severity"] = self.severity.value
        for h in d["hypotheses"]:
            h["confidence"] = (
                h["confidence"].value if hasattr(h["confidence"], "value") else h["confidence"]
            )
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    # Renderização textual amigável para o painel da AURA/Angela
    def to_markdown(self) -> str:
        lines = [
            f"### 🛠 Relatório da Angela",
            f"**Solicitação:** {self.request}",
            f"**Severidade:** {self.severity.value.upper()}  •  "
            f"**Confiança:** {self.root_cause_confidence.value}",
            "",
        ]
        if self.error:
            lines.append(f"> ⚠️ Investigação interrompida: {self.error}")
            return "\n".join(lines)

        if self.summary:
            lines += ["**Resumo:**", self.summary, ""]
        if self.root_cause:
            lines += ["**Causa raiz:**", self.root_cause, ""]
        if self.files_read:
            lines += ["**Arquivos analisados:**"]
            lines += [f"- `{f}`" for f in self.files_read]
            lines.append("")
        if self.hypotheses:
            lines.append("**Hipóteses:**")
            for h in self.hypotheses:
                mark = "✗" if h.rejected else "•"
                lines.append(f"{mark} ({h.confidence.value}) {h.description}")
                for e in h.evidence:
                    lines.append(f"    - evidência: {e}")
            lines.append("")
        if self.tests_run:
            lines.append("**Testes executados:**")
            for t in self.tests_run:
                status = "✓" if t.passed else "✗"
                lines.append(f"{status} {t.name} ({t.duration_ms}ms)")
            lines.append("")
        if self.proposed_patches:
            lines.append(f"**Patches propostos ({len(self.proposed_patches)}):**")
            for p in self.proposed_patches:
                lines.append(f"- `{p.file}` — {p.description}")
            lines.append("")
            lines.append("_Nenhum patch será aplicado sem sua confirmação._")
        elif not self.error:
            lines.append("_Nenhuma alteração de código necessária._")
        return "\n".join(lines)
