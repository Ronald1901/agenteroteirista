# Validation Report — v7.7.1 Auto Failover

## Resultado

- `doctor`: PASS
- `selftest`: PASS
- unit tests: 20/20 PASS
- Golden Failure #001: REJECT

## Cenários de failover simulados

1. DNA primary marcado `quota_exhausted` → próximo route escolhido sem alterar `invalid_outputs`: PASS.
2. Rewriter primary marcado `quota_exhausted` → fallback selecionado e `draft_count` permanece 0: PASS.
3. Critic DeepSeek falha → GLM assume Critic; Release Challenge exclui GLM e usa Qwen para independência: PASS.
4. Todos os modelos de uma role falham → `MODEL_POOL_EXHAUSTED`, recoverable=true, sem `QUALITY_BLOCKED`: PASS.
5. Candidate DNA inválido → arquivado em `rejected/`, sem `File not found`: PASS.

## Compatibilidade da run v7.7.0

O runtime continua em `.harness_v77` e os schemas de artefatos permanecem `7.7`. Portanto o hotfix pode ser extraído por cima da pasta v7.7.0 para preservar uma run já existente.
