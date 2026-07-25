"""
tools/file_tools.py — Ferramentas de Arquivos (8)
Extraído de tool_manager.py na divisão por categoria (Fase 2/V10) —
comportamento idêntico, só mudou de arquivo.
"""
import os
import shutil
from pathlib import Path

from tools.base_tool import BaseTool
from tools.resolvers import DESKTOP, _open_folder_native, _shell_open


class CriarPastaTool(BaseTool):
    name = "criar_pasta"
    description = "Cria uma pasta no caminho especificado."
    params_doc = '{"caminho": "C:/Users/User/Desktop/MinhaPasta"}'
    def execute(self, p):
        try:
            caminho = Path(p["caminho"])
            caminho.mkdir(parents=True, exist_ok=True)
            return self._success(str(caminho), f"Pasta '{caminho.name}' criada")
        except Exception as e:
            return self._error("Erro ao criar pasta", e)

class AbrirPastaTool(BaseTool):
    name = "abrir_pasta"
    description = "Abre pasta no Explorador de Arquivos."
    params_doc = '{"caminho": "downloads"}  — nomes: desktop/downloads/documentos/imagens'
    def execute(self, p):
        try:
            caminho = p.get("caminho", str(DESKTOP))
            path    = Path(caminho)
            if not path.exists():
                return self._error(f"Pasta não encontrada: {caminho}")
            _open_folder_native(str(path))
            return self._success(str(path), f"Abrindo: {path.name or str(path)}")
        except Exception as e:
            return self._error("Erro ao abrir pasta", e)

class AbrirArquivoTool(BaseTool):
    name = "abrir_arquivo"
    description = "Abre qualquer arquivo com o programa padrão do Windows."
    params_doc = '{"caminho": "C:/Users/User/Desktop/relatorio.pdf"}'
    def execute(self, p):
        try:
            caminho = os.path.expandvars(os.path.expanduser(p["caminho"]))
            if not os.path.exists(caminho):
                return self._error(f"Arquivo não encontrado: {caminho}")
            _shell_open(caminho)
            return self._success(caminho, f"Abrindo: {os.path.basename(caminho)}")
        except Exception as e:
            return self._error("Erro ao abrir arquivo", e)

class RenomearArquivoTool(BaseTool):
    name = "renomear_arquivo"
    description = "Renomeia um arquivo ou pasta."
    params_doc = '{"caminho": "C:/path/antigo.txt", "novo_nome": "novo.txt"}'
    def execute(self, p):
        try:
            origem  = Path(p["caminho"]).expanduser()
            destino = origem.parent / p["novo_nome"]
            origem.rename(destino)
            return self._success(str(destino), f"Renomeado para: {p['novo_nome']}")
        except Exception as e:
            return self._error("Erro ao renomear", e)

class CopiarArquivoTool(BaseTool):
    name = "copiar_arquivo"
    description = "Copia arquivo ou pasta."
    params_doc = '{"origem": "C:/path/origem", "destino": "C:/path/destino"}'
    def execute(self, p):
        try:
            o = Path(p["origem"]).expanduser()
            d = Path(p["destino"]).expanduser()
            shutil.copytree(str(o), str(d)) if o.is_dir() else shutil.copy2(str(o), str(d))
            return self._success(mensagem=f"Copiado para: {d}")
        except Exception as e:
            return self._error("Erro ao copiar", e)

class MoverArquivoTool(BaseTool):
    name = "mover_arquivo"
    description = "Move arquivo ou pasta."
    params_doc = '{"origem": "C:/path/origem", "destino": "C:/path/destino"}'
    def execute(self, p):
        try:
            shutil.move(str(Path(p["origem"]).expanduser()), str(Path(p["destino"]).expanduser()))
            return self._success(mensagem=f"Movido para: {p['destino']}")
        except Exception as e:
            return self._error("Erro ao mover", e)

class ExcluirArquivoTool(BaseTool):
    name = "excluir_arquivo"
    description = "Exclui arquivo ou pasta permanentemente. REQUER CONFIRMAÇÃO."
    params_doc = '{"caminho": "C:/path/alvo"}'
    def execute(self, p):
        try:
            alvo = Path(p["caminho"]).expanduser()
            shutil.rmtree(str(alvo)) if alvo.is_dir() else alvo.unlink()
            return self._success(mensagem=f"Excluído: {alvo.name}")
        except Exception as e:
            return self._error("Erro ao excluir", e)

class PesquisarArquivoTool(BaseTool):
    name = "pesquisar_arquivo"
    description = "Pesquisa arquivos por nome em um diretório."
    params_doc = '{"nome": "relatorio", "diretorio": "C:/Users/User"}'
    def execute(self, p):
        try:
            d = Path(p.get("diretorio", "~")).expanduser()
            n = p.get("nome", "*")
            r = list(d.rglob(f"*{n}*") if p.get("recursivo", True) else d.glob(f"*{n}*"))[:50]
            c = [str(x) for x in r]
            return self._success(c, f"{len(c)} item(s) encontrado(s)")
        except Exception as e:
            return self._error("Erro na pesquisa", e)


# Auto-registro V11
REGISTRY = [CriarPastaTool(), AbrirPastaTool(), AbrirArquivoTool(), RenomearArquivoTool(), CopiarArquivoTool(), MoverArquivoTool(), ExcluirArquivoTool(), PesquisarArquivoTool()]