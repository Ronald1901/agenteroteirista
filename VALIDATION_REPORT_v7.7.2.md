# Validation Report v7.7.2

## Motivo da correção

O resultado real da v7.7.1 mostrou duas coisas distintas:

1. **Transferência semântica/narrativa melhorou** em relação à v7.5.1: o Writer criou callbacks e paralelos novos sem usar B bruto como molde.
2. **Formato final estava errado** porque a própria v7.7.1 proibia `headings Markdown` no Rewriter e rejeitava headings no CLI. Como o Arquivo F nunca foi modelado como terceira fonte (`F = formato`), o runtime não tinha como exigir GANCHO/BLOCOS/subtítulos/FECHAMENTO.

## Contrato v7.7.2

- A = voz, storytelling, cadência e forma.
- B = conteúdo, fatos, ordem temática e tamanho.
- F = layout editorial somente.

O Arquivo F nunca é entregue como fonte de voz ou conteúdo. O Python extrai apenas seus rótulos editoriais.

## Formato obrigatório

- `**GANCHO**`
- `**BLOCO 1 - subtítulo específico**`
- blocos subsequentes numerados sem saltos
- `**CTA BLOCO N**` quando usado
- `**FECHAMENTO**`

A contagem de palavras e os gates de estilo ignoram esses rótulos editoriais.

## Testes

- 26/26 unit tests PASS.
- doctor PASS.
- selftest PASS.
- `arquivo F.txt` real: 9 blocos e 2 CTAs detectados corretamente.
- resultado sem headings da v7.7.1: rejeitado pelo `OUTPUT_FORMAT_CONTRACT`.
- release gera roteiro formatado + locução limpa.
