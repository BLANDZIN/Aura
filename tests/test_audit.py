from pathlib import Path

from angela.audit import Auditor
from angela.platforms.local_stub import LocalStubPlatform


def make_platform(tmp_path: Path) -> LocalStubPlatform:
    ws = tmp_path / "ws"
    ws.mkdir()
    return LocalStubPlatform(project_root=tmp_path, workspace_dir=ws)


def test_detects_circular_dependency(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "pkg_a").mkdir()
    (root / "pkg_b").mkdir()
    (root / "pkg_a" / "__init__.py").write_text("")
    (root / "pkg_b" / "__init__.py").write_text("")
    (root / "pkg_a" / "mod.py").write_text("from pkg_b import mod\n")
    (root / "pkg_b" / "mod.py").write_text("from pkg_a import mod\n")

    cycles = Auditor(p).detect_cycles()
    assert any({"pkg_a", "pkg_b"} <= set(c) for c in cycles)


def test_no_false_positive_cycle(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "pkg_a").mkdir()
    (root / "pkg_b").mkdir()
    (root / "pkg_a" / "__init__.py").write_text("")
    (root / "pkg_b" / "__init__.py").write_text("")
    (root / "pkg_a" / "mod.py").write_text("from pkg_b import mod\n")
    (root / "pkg_b" / "mod.py").write_text("x = 1\n")

    assert Auditor(p).detect_cycles() == []


def test_detects_giant_class(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    body = "\n".join(f"    def m{i}(self):\n        return {i}" for i in range(80))
    (root / "big.py").write_text(f"class Big:\n{body}\n")

    findings = Auditor(p).detect_large_classes()
    assert any("Big" in f for f in findings)


def test_no_giant_class_for_small_class(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "small.py").write_text("class Small:\n    def m(self):\n        return 1\n")

    assert Auditor(p).detect_large_classes() == []


def test_detects_long_function(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    body = "\n".join(f"    x{i} = {i}" for i in range(70))
    (root / "longf.py").write_text(f"def long_one():\n{body}\n    return x0\n")

    findings = Auditor(p).detect_large_functions()
    assert any("long_one" in f for f in findings)


def test_find_duplicates_reports_locations(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    block = "\n".join(f"    line_{i} = {i} * 999999" for i in range(6))
    (root / "dup.py").write_text(f"def a():\n{block}\n\ndef b():\n{block}\n")

    findings = Auditor(p).find_duplicates()
    assert len(findings) >= 1
    assert "dup.py" in findings[0]


def test_long_duplicate_merges_into_one_region_not_many_windows(tmp_path):
    # Um bloco de 12 linhas repetido gera 7 janelas de 6 linhas sobrepostas
    # (i=0..6) -- sem fusão isso contava como 7 "duplicatas" separadas.
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    block = "\n".join(f"    valor_{i} = {i} * 12345678" for i in range(12))
    (root / "a.py").write_text(f"def x():\n{block}\n")
    (root / "b.py").write_text(f"def y():\n{block}\n")

    report = Auditor(p).audit()
    dup_section = next(s for s in report.sections if s.title == "Duplicações")
    assert dup_section.metrics["Blocos duplicados (regiões fundidas)"] == 1
    assert "-" in dup_section.findings[0]  # reportado como range, não linha única


def test_workspace_snapshot_is_excluded_from_audit(tmp_path):
    # angela/workspace é um espelho do próprio projeto — auditar duas
    # vezes o mesmo conteúdo não pode contar como duplicação real nem
    # inflar o total de arquivos analisados.
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "mod.py").write_text("x = 1\n" * 20)
    (root / "angela" / "workspace" / "mod.py").parent.mkdir(parents=True)
    (root / "angela" / "workspace" / "mod.py").write_text("x = 1\n" * 20)

    files = Auditor(p)._python_files()
    assert not any("workspace" in f.parts for f in files)


def test_deferred_import_inside_function_is_not_a_cycle(tmp_path):
    # Import dentro de função é o jeito padrão em Python de EVITAR
    # circularidade real — não pode ser tratado como se fosse um ciclo.
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "pkg_a").mkdir()
    (root / "pkg_b").mkdir()
    (root / "pkg_a" / "__init__.py").write_text("")
    (root / "pkg_b" / "__init__.py").write_text("")
    (root / "pkg_a" / "mod.py").write_text(
        "def f():\n    from pkg_b import mod\n    return mod\n"
    )
    (root / "pkg_b" / "mod.py").write_text("from pkg_a import mod\n")

    cycles = Auditor(p).detect_cycles()
    assert cycles == []


def test_top_level_mutual_import_is_still_a_real_cycle(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "pkg_a").mkdir()
    (root / "pkg_b").mkdir()
    (root / "pkg_a" / "__init__.py").write_text("")
    (root / "pkg_b" / "__init__.py").write_text("")
    (root / "pkg_a" / "mod.py").write_text("from pkg_b import mod\n")
    (root / "pkg_b" / "mod.py").write_text("from pkg_a import mod\n")

    cycles = Auditor(p).detect_cycles()
    assert any({"pkg_a", "pkg_b"} <= set(c) for c in cycles)


def test_find_dead_code_flags_unused_import(tmp_path):
    p = make_platform(tmp_path)
    root = Path(p.workspace_root())
    (root / "deadimp.py").write_text("from os import getcwd\nx = 1\n")

    report = Auditor(p).audit()
    dead_section = next(s for s in report.sections if s.title == "Código morto & imports")
    assert dead_section.metrics["Imports potencialmente não usados"] >= 1
