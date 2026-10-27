# Alterações

## 1.19.2 — 2026-10-27

- Restaurados mapas CARTO na tela e no PDF e fallback de endereços Nominatim.
- Eixos de Porto Alegre continuam incorporados ao VERA, validados por SHA-256,
  sem comunicação com Hugging Face nem download em execução.
- Lotes fiscais deixam de compor os mapas e a instalação obrigatória.
- Reconhecida a nova exportação SIRI em camelCase, preservando colunas originais.
  Guias usam valor declarado e área transmitida; pares de coordenadas e origem
  de preços/áreas têm rastreabilidade.
- Núcleo e parâmetros de estimativa preservados; documentação ajustada aos serviços online.

## 1.19.1 — 2026-10-23

- Modo local obrigatório: remoção do fallback Nominatim e de downloads em execução.
- Base viária de Porto Alegre incluída e validada por SHA-256.
- Mapas interativo/PDF usam fundo neutro sem tiles externos; telemetria desativada.
- Instalação corporativa offline com versões fixas e verificação dos recursos.
- Núcleo, parâmetros e interfaces de cálculo preservados.
- Lotes fiscais SMAMUS como cartografia local na tela e no PDF, com índice
  espacial, recortes por região e avisos de cobertura/abrangência.
- Preenchimento cinza claro sólido nos lotes, com contornos e vazios preservados;
  renderização do PDF evita projeção duplicada de vértices.
