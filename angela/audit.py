"""
angela/audit.py
Modo Auditoria — análise exaustiva do projeto inteiro.

Angela varre o workspace produzindo métricas objetivas em várias
dimensões (arquitetura, código morto, duplicações, complexidade,
acoplamento, cobertura de testes, documentação, organização).

O relatório é agnóstico de LLM: são heurísticas estáticas que rodam
sem custo e sem depender do OpenClaude. Quando OC estiver conectado,
ele enriquece cada seção com raciocínio de alto nível.
"""

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from angela.platforms.base import EngineeringPlatform


@dataclass
class AuditSection:
    title: str
    findings: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class AuditReport:
    sections: List[AuditSection] = field(default_factory=list)

    def to_markdown(self) -> str:
        out = ["# 🛠 Auditoria completa — Angela\n"]
        for sec in self.sections:
            out.append(f"## {sec.title}")
            if sec.metrics:
                for k, v in sec.metrics.items():
                    out.append(f"- **{k}**: {v}")
            for f in sec.findings:
                out.append(f"- {f}")
            out.append("")
        return "\n".join(out)


class Auditor:
    """Coleção de heurísticas independentes."""

    def __init__(self, platform: EngineeringPlatform):
        self._p = platform

    def audit(self) -> AuditReport:
        report = AuditReport()
        report.sections.append(self._architecture())
        report.sections.append(self._dead_code_and_imports())
        report.sections.append(self._duplications())
        report.sections.append(self._complexity_and_coupling())
        report.sections.append(self._circular_dependencies())
        report.sections.append(self._tests_and_docs())
        report.sections.append(self._organization())
        return report

    # ── coletores ────────────────────────────────────────────────────
    def _python_files(self) -> List[Path]:
        root = Path(self._p.workspace_root())
        out: List[Path] = []
        skip_dirs = {"__pycache__", ".git", ".pytest_cache"}
        for p in root.rglob("*.py"):
            rel_parts = p.relative_to(root).parts
            if skip_dirs & set(rel_parts):
                continue
            # angela/workspace é um SNAPSHOT do próprio projeto (sandbox
            # de trabalho da Angela) — escaneá-lo junto da raiz duplica
            # artificialmente toda métrica (cada arquivo "colide" com sua
            # própria cópia). Não é código de arquitetura, é estado
            # derivado/gerado.
            if len(rel_parts) >= 2 and rel_parts[0] == "angela" and rel_parts[1] == "workspace":
                continue
            out.append(p)
        return out


    def _architecture(self) -> AuditSection:
        sec = AuditSection("Arquitetura")
        root = Path(self._p.workspace_root())
        top_pkgs = [d.name for d in root.iterdir()
                    if d.is_dir() and not d.name.startswith(".")]
        sec.metrics["Módulos de topo"] = len(top_pkgs)
        sec.findings.append(
            f"Módulos detectados: {', '.join(sorted(top_pkgs)) or '(nenhum)'}"
        )
        return sec

    def _dead_code_and_imports(self) -> AuditSection:
        sec = AuditSection("Código morto & imports")
        unused_imports = 0
        for f in self._python_files():
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                sec.findings.append(f"Arquivo com erro de sintaxe: {f.name}")
                continue
            src = f.read_text(encoding="utf-8", errors="replace")
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        # heurística: nome não aparece fora do próprio import
                        if src.count(name) <= 1:
                            unused_imports += 1
        sec.metrics["Imports potencialmente não usados"] = unused_imports
        return sec

    def _duplications(self) -> AuditSection:
        sec = AuditSection("Duplicações")
        # (linha_inicial) -> [(arquivo, linha_inicial), ...] por texto do bloco
        occurrences: Dict[str, List[tuple]] = defaultdict(list)
        for f in self._python_files():
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            for i in range(len(lines) - 5):
                chunk = "\n".join(l.strip() for l in lines[i:i + 6] if l.strip())
                if len(chunk) > 80:
                    occurrences[chunk].append((f.name, i + 1))

        # Um trecho duplicado de N>6 linhas gera várias janelas de 6 linhas
        # sobrepostas (i, i+1, i+2...) — sem fundir, cada uma conta como uma
        # "duplicata" separada e infla o número. Aqui juntamos pares de
        # localizações consecutivas do MESMO par de arquivos num único range.
        pairs: set = set()
        for locs in occurrences.values():
            if len(locs) < 2:
                continue
            for a in range(len(locs)):
                for b in range(a + 1, len(locs)):
                    if locs[a] == locs[b]:
                        continue
                    pairs.add(tuple(sorted((locs[a], locs[b]))))

        merged: List[tuple] = []
        used: set = set()
        for pair in sorted(pairs):
            if pair in used:
                continue
            (fa, la), (fb, lb) = pair
            end_a, end_b = la, lb
            nxt = ((fa, end_a + 1), (fb, end_b + 1))
            while nxt in pairs:
                used.add(nxt)
                end_a += 1
                end_b += 1
                nxt = ((fa, end_a + 1), (fb, end_b + 1))
            used.add(pair)
            merged.append((fa, la, end_a + 5, fb, lb, end_b + 5))

        sec.metrics["Blocos duplicados (regiões fundidas)"] = len(merged)
        for fa, la, ea, fb, lb, eb in merged[:10]:
            span_a = f"{fa}:{la}" if ea <= la + 5 else f"{fa}:{la}-{ea}"
            span_b = f"{fb}:{lb}" if eb <= lb + 5 else f"{fb}:{lb}-{eb}"
            sec.findings.append(f"Bloco duplicado em: {span_a} ~ {span_b}")
        return sec

    def _complexity_and_coupling(self) -> AuditSection:
        sec = AuditSection("Complexidade & acoplamento")
        total_funcs = 0
        long_funcs: List[str] = []
        giant_classes: List[str] = []
        imports_per_file: Dict[str, int] = {}
        for f in self._python_files():
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            imports_per_file[f.name] = sum(
                1 for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom))
            )
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_funcs += 1
                    length = (node.end_lineno or node.lineno) - node.lineno
                    if length > 60:
                        long_funcs.append(f"{f.name}:{node.name} ({length} linhas)")
                elif isinstance(node, ast.ClassDef):
                    length = (node.end_lineno or node.lineno) - node.lineno
                    if length > 150:
                        giant_classes.append(f"{f.name}:{node.name} ({length} linhas)")
        sec.metrics["Funções analisadas"] = total_funcs
        sec.metrics["Funções >60 linhas"] = len(long_funcs)
        sec.metrics["Classes >150 linhas"] = len(giant_classes)
        for lf in long_funcs[:10]:
            sec.findings.append(f"Função longa: {lf}")
        for gc in giant_classes[:10]:
            sec.findings.append(f"Classe grande (considere dividir responsabilidades): {gc}")
        # top-5 arquivos mais acoplados
        top = sorted(imports_per_file.items(),
                     key=lambda x: x[1], reverse=True)[:5]
        for name, n in top:
            sec.findings.append(f"Alto acoplamento: {name} ({n} imports)")
        return sec

    @staticmethod
    def _module_level_imports(node: ast.AST):
        """Percorre a AST sem descer dentro de função/método/lambda —
        só imports que rodam na CARGA do módulo entram aqui. Import
        tardio (dentro de função) é o jeito padrão em Python de evitar
        circularidade real de propósito, não é a mesma coisa."""
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                yield child
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            else:
                yield from Auditor._module_level_imports(child)

    def _import_graph(self) -> Dict[str, set]:
        """Grafo de imports de NÍVEL DE MÓDULO entre pacotes de topo
        (usado por auditoria completa e por detect_cycles() — uma única
        implementação)."""
        root = Path(self._p.workspace_root())
        top_pkgs = {
            d.name for d in root.iterdir()
            if d.is_dir() and not d.name.startswith(".") and d.name != "__pycache__"
        }
        graph: Dict[str, set] = defaultdict(set)
        for f in self._python_files():
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError:
                continue
            rel_parts = f.relative_to(root).parts
            pkg = rel_parts[0] if rel_parts[0] in top_pkgs else None
            if pkg is None:
                continue
            for node in self._module_level_imports(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    target = node.module.split(".")[0]
                    if target in top_pkgs and target != pkg:
                        graph[pkg].add(target)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        cand = alias.name.split(".")[0]
                        if cand in top_pkgs and cand != pkg:
                            graph[pkg].add(cand)
        return graph

    def _circular_dependencies(self) -> AuditSection:
        """
        Detecta ciclos de import entre os pacotes de topo do projeto
        (ex.: automation -> ui -> automation). Granularidade de pacote,
        não de arquivo — é o nível relevante para auditoria de arquitetura.
        """
        sec = AuditSection("Dependências circulares")
        graph = self._import_graph()
        cycles = self._find_cycles(graph)
        sec.metrics["Módulos analisados"] = len(graph) or len(
            {d.name for d in Path(self._p.workspace_root()).iterdir() if d.is_dir()}
        )
        sec.metrics["Ciclos encontrados"] = len(cycles)
        if cycles:
            for c in cycles:
                sec.findings.append("Ciclo: " + " → ".join(c + [c[0]]))
        else:
            sec.findings.append("Nenhuma dependência circular entre módulos de topo.")
        return sec

    @staticmethod
    def _find_cycles(graph: Dict[str, set]) -> List[List[str]]:
        cycles: List[List[str]] = []
        visited: set = set()

        def dfs(node: str, path: List[str], on_path: set) -> None:
            if node in on_path:
                i = path.index(node)
                candidate = path[i:]
                if candidate not in cycles:
                    cycles.append(candidate)
                return
            if node in visited:
                return
            visited.add(node)
            for nxt in sorted(graph.get(node, ())):
                dfs(nxt, path + [nxt], on_path | {node})

        for start in sorted(graph):
            dfs(start, [start], set())
        return cycles

    # ── Ferramentas individuais ──────────────────────────────────────
    # Reaproveitam a mesma lógica das seções da auditoria completa —
    # úteis quando Angela (ou o próprio usuário, via painel) quer uma
    # resposta pontual em vez do relatório inteiro.

    def find_dead_code(self) -> List[str]:
        return self._dead_code_and_imports().findings

    def find_duplicates(self) -> List[str]:
        return self._duplications().findings

    def detect_large_functions(self) -> List[str]:
        return [f for f in self._complexity_and_coupling().findings
                if f.startswith("Função longa")]

    def detect_large_classes(self) -> List[str]:
        return [f for f in self._complexity_and_coupling().findings
                if f.startswith("Classe grande")]

    def detect_cycles(self) -> List[List[str]]:
        return self._find_cycles(self._import_graph())

    def _tests_and_docs(self) -> AuditSection:
        sec = AuditSection("Testes & documentação")
        root = Path(self._p.workspace_root())
        tests = list((root / "tests").rglob("*.py")) if (root / "tests").exists() else []
        sec.metrics["Arquivos de teste"] = len(tests)
        docs = list(root.rglob("README*")) + list(root.rglob("*.md"))
        sec.metrics["Documentos markdown"] = len(docs)
        if not tests:
            sec.findings.append("Nenhuma suíte de testes detectada.")
        return sec

    def _organization(self) -> AuditSection:
        sec = AuditSection("Organização & escalabilidade")
        root = Path(self._p.workspace_root())
        depths = [len(p.relative_to(root).parts) for p in root.rglob("*.py")]
        if depths:
            sec.metrics["Profundidade média"] = round(sum(depths) / len(depths), 2)
            sec.metrics["Profundidade máxima"] = max(depths)
        return sec
