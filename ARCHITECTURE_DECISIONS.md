# Architecture Decisions — v7.7.1 — v7.7

## Correção do defeito v7.5/v7.6

O benchmark real mostrou que entregar A + B brutos ao Writer permite o atalho `parafrasear B + imitar marcadores superficiais de A`.

A v7.7 impede esse caminho estruturalmente:

1. DNA Analyzer lê só A.
2. B Decompiler lê só B e cria:
   - `b_content_ledger.json` para o Writer;
   - `b_scaffold_signature.json` reservado a Critic/GLM.
3. Rewriter lê A + DNA + ledger, mas **não recebe B bruto nem a assinatura retórica de B**.
4. Critic compara A, B e draft diretamente.
5. DeepSeek não libera sozinho: GLM faz release challenge obrigatório.

## Gates novos

- `b_rhetorical_scaffolding_removed`
- `form_closer_to_a_than_b`
- `voice_caricature`

Release exige matriz formal A>=6/8, B<=1/8 e `block_progression`, `retention_logic`, `syntax_voice` mais próximos de A.

## Saída simples

O release fica em `roteiro final/` na raiz, com arquivo histórico por RUN_ID e `ULTIMO_ROTEIRO.txt`.


## ADR — Provider failures are not quality failures

Quota/model errors are infrastructure events. They are persisted in `state.json.model_failures` and routed to the next compatible model for the same logical role. They do not increment invalid outputs, draft count, or repair count. Hidden `*-fb-*` agents are execution aliases only; the cognitive pipeline remains DNA → B Decompiler → Rewriter → Critic → Release Challenger.

Rejected semantic outputs are archived under `rejected/` rather than deleted, preventing stale-path/file-not-found recovery loops.
