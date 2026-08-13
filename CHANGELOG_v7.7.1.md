# v7.7.1 — Automatic Model Failover

## Objetivo

Tornar a run resiliente a esgotamento de quota/modelo sem reiniciar o roteiro e sem converter erro de infraestrutura em falha de qualidade.

## Mudanças

- Adicionado roteador persistente de modelos por função em `rh7_cli.py`.
- `QUOTA EXHAUSTED`, `insufficient quota` e indisponibilidade de modelo podem ser reportados com `model-failure`; o CLI seleciona o próximo executor compatível.
- Failover NÃO incrementa `draft_count`, reparos ou `invalid_outputs`.
- DNA, B Decompiler, Rewriter, Critic e Second Opinion possuem pools de fallback.
- Fallbacks são aliases ocultos da MESMA função cognitiva; não criam novas etapas no objective loop.
- O modelo usado com sucesso em cada função fica salvo em `state.json`.
- O Release Challenger evita reutilizar o mesmo modelo que atuou como Critic quando há alternativa disponível.
- Candidatos rejeitados não são mais apagados: são movidos para `rejected/<stage>/...` com `rejection.json`.
- Novo comando de emergência `/pular-modelo-roteiro`.
- Novos comandos CLI: `model-failure`, `model-failure-latest`, `model-reset`.
- `status` agora mostra pool, modelos falhos, modelo selecionado e contagem de failovers.

## Pools

Como a quota de `qwen3.7-max` já está esgotada na conta atual, ele não é mais tentado no caminho normal.

### DNA
1. qwen3.7-max-2026-05-20
2. qwen3.7-max-2026-05-17
3. qwen3.7-max-preview
4. qwen3.6-max-preview

### B Decompiler
1. qwen3.7-max-2026-05-17
2. qwen3.7-max-preview
3. qwen3.7-max-2026-05-20
4. qwen3.6-max-preview

### Rewriter
1. qwen3.8-max
2. qwen3.7-max-preview
3. qwen3.7-max-2026-05-20
4. qwen3.7-max-2026-05-17
5. qwen3.6-max-preview

### Critic
1. deepseek-v4-pro
2. glm-5.2
3. qwen3.7-max-preview
4. qwen3.7-max-2026-05-17

### Release Challenge / Second Opinion
1. glm-5.2
2. qwen3.7-max-preview
3. qwen3.7-max-2026-05-17
4. deepseek-v4-pro

Quando possível, o Challenger não usa o mesmo modelo que acabou de atuar como Critic.
