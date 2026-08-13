# Roteirista Harness v7.7.2 — True Objective Loop + Auto Failover

Harness Kilo/Qwen para transformar **B pelo DNA narrativo de A** sem usar a prosa de B como molde.

## Objective Loop

```text
A → DNA
B → CONTENT LEDGER + B SCAFFOLD (critic-only)
DNA + LEDGER + A → REWRITER
DRAFT → PYTHON AUDIT → CRITIC
PASS → RELEASE CHALLENGE → RELEASE
FAIL/VETO → OBJECTIVE DELTA → REPAIR → RE-MEASURE
```

## Failover automático

Se um subagente retornar `QUOTA EXHAUSTED`, o agente principal registra o erro no CLI e o runtime escolhe outro modelo compatível da mesma função. A run, o task file e os checkpoints permanecem os mesmos.

Erro de quota **não** consome tentativa de qualidade.

## Comandos

- `/novo-roteiro`
- `/continuar-roteiro`
- `/progresso-roteiro`
- `/status-roteiro`
- `/abrir-roteiro-final`
- `/pular-modelo-roteiro` — emergência quando uma sessão anterior morreu antes de registrar a quota esgotada
- `/diagnosticar-roteirista`

## Saída final

Todo release aprovado é criado diretamente em:

```text
roteiro final/roteiro_final_<RUN_ID>.txt
roteiro final/ULTIMO_ROTEIRO.txt
```

## Provider

O projeto espera o Provider ID global `qwen`. API key e Base URL continuam fora do projeto.

## Formato final obrigatório

O `arquivo F.txt` é reconhecido como **F = FORMAT_REFERENCE_ONLY**. Sua prosa não entra no Writer; o Python extrai somente a gramática editorial. Mesmo sem F, o formato canônico é:

- `**GANCHO**`
- `**BLOCO 1 - subtítulo específico**`, `**BLOCO 2 - ...**` etc.
- `**CTA BLOCO N**` quando o DNA de A pedir CTA
- `**FECHAMENTO**`

O arquivo principal formatado fica em `roteiro final/ULTIMO_ROTEIRO.txt`. Uma versão sem rótulos fica em `roteiro final/ULTIMA_LOCUCAO_LIMPA.txt`.
