"""
angela/
=======
Angela — Chief Engineer do ecossistema AURA.

Angela NÃO é uma assistente conversacional.
Ela é uma engenheira sênior de software que trabalha nos bastidores:
analisa código, investiga bugs, propõe patches, executa auditorias e
supervisiona a saúde técnica do projeto.

AURA é o rosto. Angela é a mão técnica. Elas trabalham em equipe via
EventBus e nunca se substituem.

Arquitetura (modular e preparada para futuros especialistas — Vision,
Security, Infrastructure, Planning):

    angela/
      chief_engineer.py    — orquestrador principal (Angela)
      workflow.py          — sequência obrigatória de 12 passos
      personality.py       — prompt/persona técnica
      report.py            — estruturas de relatório e patch
      audit.py             — modo auditoria completa
      communication.py     — canal AURA↔Angela via EventBus
      autoengineering.py   — gatilhos automáticos por AURA
      platforms/           — adapters plugáveis (OpenClaude, etc.)
        base.py            — interface EngineeringPlatform
        openclaude.py      — adapter para github.com/Gitlawb/openclaude
        local_stub.py      — backend simulado (default até conectar OC)

Ponto de entrada público:

    from angela import Angela
    angela = Angela()
    angela.start()                    # registra listeners no EventBus
    angela.request("Analise X")       # dispara investigação assíncrona
"""

__all__ = ["Angela"]
__version__ = "1.0.0"


def __getattr__(name: str):
    if name == "Angela":
        from angela.chief_engineer import Angela
        return Angela
    raise AttributeError(f"module 'angela' has no attribute {name!r}")
