# Setup Kilo + provider `qwen` — v7.7

A v7.7 usa o Provider ID que você já configurou no Kilo: `qwen`.

Não coloque API key dentro deste projeto.

Modelos usados:
- `qwen3.7-max-2026-06-08`
- `qwen3.7-max`
- `qwen3.8-max`
- `deepseek-v4-pro`
- `glm-5.2`

## Instalação

1. Extraia o ZIP em uma pasta nova.
2. Abra a pasta que contém diretamente `.kilo/`, `rh7_cli.py`, `kilo.jsonc` e `ROTEIROS/`.
3. Copie A e B para `ROTEIROS/`.
4. No VS Code: `Developer: Reload Window`.
5. Selecione `roteirista-harness-v77`.
6. Deixe o modelo da sessão sem override manual, para os pins por agente funcionarem.
7. Rode `/diagnosticar-roteirista`.
8. Se tudo PASS, rode `/novo-roteiro`.

## Saída

O arquivo final não fica enterrado no runtime. Ele aparece em:

`roteiro final/`

# v7.7.1 — modelos de fallback

Além dos modelos principais, adicione/seleciona no provider `qwen` estes IDs caso ainda não estejam visíveis no Kilo:

- `qwen3.7-max-2026-05-20`
- `qwen3.7-max-2026-05-17`
- `qwen3.7-max-preview`
- `qwen3.6-max-preview`

O `kilo.jsonc` do projeto já contém os metadados desses modelos. A API key/Base URL continuam na configuração global do provider `qwen`.

Quando um subagente retornar `QUOTA EXHAUSTED`, **não é necessário interromper a run**: o agente principal deve registrar `model-failure` e usar automaticamente o próximo target retornado pelo CLI.

Se uma sessão antiga tiver morrido antes de registrar a falha, use `/pular-modelo-roteiro` uma vez e depois `/continuar-roteiro`.
