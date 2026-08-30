# AURA V12.2 — Instalação dos Modelos dos Agentes

## Obrigatório vs opcional

**Só `qwen2.5:3b` é obrigatório** — é o modelo principal (`aura`), sem ele
a AURA não funciona, com ou sem a arquitetura multi-agente. Já é parte da
instalação padrão desde a V10, nada muda aqui.

**Os outros 4 arquivos de modelo são opcionais.** Sem eles, `agents_enabled`
fica `false` automaticamente e a AURA funciona exatamente como na V12.1 —
regras/heurísticas atuais em vez de agentes. Ver "Modo degradado" em
`docs/AI_ARCHITECTURE.md`.

## RAM mínima recomendada

| Cenário | RAM mínima |
|---|---|
| Só o modelo principal (V12.1, sem agentes) | 4GB — inalterado |
| Arquitetura completa (todos os agentes) | **6GB** — novo piso a partir da V12.2 |

## Comandos — ordem recomendada

```bash
# 1. Obrigatório (se ainda não tiver — já é parte da instalação padrão)
ollama pull qwen2.5:3b

# 2. Recomendado primeiro entre os opcionais: intent + autonomy
#    (são os dois de implementação inicial nesta fase — ver AI_ARCHITECTURE.md)
ollama pull smollm2:1.7b-instruct-q4_0
ollama pull llama3.2:1b

# 3. Resto dos agentes (planner + reflection + vision, mesmo arquivo)
ollama pull qwen2.5:1.5b

# 4. memory + emotion (mesmo arquivo, o menor de todos)
ollama pull smollm2:360m-instruct-q4_K_M
```

## Espaço em disco

| Etapa | Download |
|---|---|
| 1 (obrigatório) | ~1.9GB |
| 2 (intent + autonomy) | ~1.7GB |
| 3 (planner/reflection/vision) | ~1.0GB |
| 4 (memory/emotion) | ~0.3GB |
| **Total se instalar tudo** | **~4.9GB** |

## Variável de ambiente necessária

A arquitetura completa precisa de mais de 3 modelos carregados ao mesmo
tempo em algum momento. O Ollama por padrão só mantém 3 modelos
diferentes residentes (`OLLAMA_MAX_LOADED_MODELS`, default 3 em CPU).

- Se for a própria AURA quem inicia o `ollama serve` (`AURA.py::_ensure_ollama()`,
  quando o Ollama não estava rodando ainda): a partir da V12.2 isso é
  configurado automaticamente, nada pra fazer manualmente.
- **Se você já roda o Ollama como serviço/systemd separado da AURA**:
  precisa setar manualmente antes de iniciar o serviço:
  ```bash
  # Linux (systemd) — editar o serviço do Ollama e adicionar:
  Environment="OLLAMA_MAX_LOADED_MODELS=5"

  # Windows — variável de ambiente do sistema:
  setx OLLAMA_MAX_LOADED_MODELS 5
  ```
  Sem isso, a arquitetura completa ainda funciona, só troca modelos com
  mais frequência do que o ideal (latência maior nas trocas de agente,
  não é um erro, só mais lento que o desenhado).

## Verificação de integridade (planejado, não implementado ainda)

`scripts/download_models.py` está preparado como esqueleto de arquitetura
(ver o próprio arquivo) para, quando implementado por completo:

- checar quais modelos já estão baixados (`ollama list`)
- baixar só os que faltam
- validar que o tamanho baixado bate com o esperado (tabela acima)
- oferecer `--minimal` (só o obrigatório) vs `--full` (todos os agentes)

Isso ainda não está implementado de ponta a ponta nesta fase — combinado
com o brief original ("ainda não implementar completamente, apenas deixar
a arquitetura preparada").
