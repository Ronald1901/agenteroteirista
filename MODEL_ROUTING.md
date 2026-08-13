# Model Routing — v7.7.1

O Harness possui **5 funções cognitivas**. Os arquivos `*-fb-*` são somente rotas de execução alternativas para a mesma função quando um modelo fica sem quota; eles não adicionam novas fases ao flow.

| Função | Primary | Fallbacks automáticos |
|---|---|---|
| Orquestrador | `qwen/qwen3.7-max-2026-06-08` | ver nota sobre MAIN |
| DNA Analyzer | `qwen/qwen3.7-max-2026-05-20` | `qwen3.7-max-2026-05-17` → `qwen3.7-max-preview` → `qwen3.6-max-preview` |
| B Decompiler | `qwen/qwen3.7-max-2026-05-17` | `qwen3.7-max-preview` → `qwen3.7-max-2026-05-20` → `qwen3.6-max-preview` |
| Rewriter | `qwen/qwen3.8-max` | `qwen3.7-max-preview` → `qwen3.7-max-2026-05-20` → `qwen3.7-max-2026-05-17` → `qwen3.6-max-preview` |
| Objective Critic | `qwen/deepseek-v4-pro` | `glm-5.2` → `qwen3.7-max-preview` → `qwen3.7-max-2026-05-17` |
| Release Challenge | `qwen/glm-5.2` | `qwen3.7-max-preview` → `qwen3.7-max-2026-05-17` → `deepseek-v4-pro` |

## Regra de failover

Quando a chamada do subagente falhar por quota/modelo:

```text
SUBAGENT(model A)
    ↓ QUOTA EXHAUSTED
model-failure
    ↓ checkpoint preservado
SUBAGENT(model B, mesma função, mesmo task_file)
```

Isso NÃO conta como tentativa de qualidade.

## Orquestrador / MAIN

Os subagentes podem ser trocados pelo runtime porque cada fallback possui um executor oculto com model override próprio. O modelo do agente PRIMARY é a sessão que está executando o próprio controle; se a quota do MAIN acabar, nenhuma lógica LLM daquela sessão consegue rodar para trocar a si mesma. Por isso:

- o MAIN usa uma quota separada (`qwen3.7-max-2026-06-08`);
- ele consome relativamente pouco porque não escreve o roteiro;
- se o MAIN ficar sem quota, troque o modelo da sessão/agent no Kilo e execute `/continuar-roteiro`; o estado em disco permanece intacto.

O failover automático completo dentro da mesma sessão é garantido para os subagentes do pipeline.
