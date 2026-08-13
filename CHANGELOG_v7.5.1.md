# v7.5.1 — Provider ID `qwen`

- Alinhado todo o Harness ao provider global já existente no Kilo: `qwen`.
- Rotas pinadas: `qwen/qwen3.7-plus`, `qwen/qwen3.8-max`, `qwen/qwen3.7-max`.
- Removida a dependência do identificador `qwencloud`.
- Corrigida a causa do erro `undefined/chat/completions` quando a v7.5.0 criava uma rota local sem Base URL resolvida.
- Mantidas credenciais/API key exclusivamente na configuração global do Kilo.
- Diagnóstico atualizado para detectar/explicar mismatch de provider.
- Runtime identificado como v7.5.1.
