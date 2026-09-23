# Calibração SIRI — 23/09/2026

## Objetivo
Comparar K, peso físico/geográfico e piso de valor unitário por finalidade,
usando a extração fornecida e preservando as interfaces do aplicativo.

## Execução
1. [concluído] Auditar dados, datas, finalidades, coordenadas e duplicidades.
2. [concluído] Definir validação temporal com bloqueio de identidade imobiliária.
3. [concluído] Comparar perfis atuais e candidatos com preparação só no treino.
4. [concluído] Avaliar finalistas em período reservado e verificar COD, PRD,
   mediana das razões, decis de valor e estabilidade espacial.
5. [concluído] Salvar parâmetros, previsões e relatório reproduzível. Aplicar
   somente mudanças sustentadas pela evidência e verificar compatibilidade.

## Restrições metodológicas
- Aluguéis não calibram o estimador de venda atual.
- Piso filtra comparáveis de treino, nunca remove alvos de validação por preço.
- Data de encaminhamento é disponibilidade no cadastro, não data do negócio.
- Não estimar atualização monetária sem índice ou datas de negócio confiáveis.
- Regimes de área devem permanecer separados.
- Não declarar ótimo universal: resultados dependem da grade e da amostra.

## Protocolo executado
- Três validações semestrais iniciadas em 01/02/2025, 01/08/2025 e 01/02/2026.
- Teste final: 01/08/2026 a 22/09/2026, posterior à calibração anterior de julho.
- Até 24 alvos/fold na triagem aproximada, 90/fold na seleção com núcleo completo,
  350 no teste e 60 no teste de exclusão de célula espacial (~1 km, sem buffer).
- Inscrição e assinatura coordenada/área dos alvos removidas antes da preparação.
- Triagem de K fixo 5–48, quatro faixas adaptativas, perfil atual, pesos físicos
  10–90% e pisos 0%, 50%, 100%, 150% e 200% do atual. Outros parâmetros constantes.
- Métricas sobre valor total; razão individual equivale à razão unitária.
- Categorias com menos de 30 alvos no teste ou 90 na validação ficam sem ajuste.

## Achados
- 730.246 linhas, 128.565 inscrições; 319.467 combinações tipo/inscrição/preço.
- 47.654 linhas sem finalidade normalizável. Nenhuma linha rotulada como aluguel.
- Inconsistência territorial: SIAT pode fornecer área de condomínio inteiro,
  enquanto crawler_area_terreno fornece outra área muito menor. Interpretação
  esclarecida pelo usuário: utilizar área negociada da unidade. Schema corrigido
  apenas para terrenos explicitamente identificados como condomínio; 765 linhas
  alteradas e ausência de unidade sem fallback silencioso para área coletiva.

## Esclarecimento sobre pisos e rodada operacional
- O usuário confirmou que pisos excluem guias incompatíveis com mercado.
- Nova rodada `_mercado` usa elegibilidade de alvos pelo piso ATUAL, congelado
  por finalidade e comum a todos os candidatos. O piso pesquisado só filtra treino.
- Preserva rodada bruta anterior como diagnóstico, não como avaliação operacional.
- Para segmentos com ao menos 50 alvos remanescentes, reserva imóveis do período
  final que não foram previstos na rodada bruta. Nos segmentos pequenos, identifica
  expressamente a reutilização do teste condicionado ao piso fixo.

## Conclusão
- 3.060 configurações triadas em oito finalidades; 1.390 alvos na confirmação
  operacional, sem falhas de previsão. Dez finalidades sem amostra suficiente.
- Após auditoria de identidade, duas casas repetidas por guias diferentes foram
  removidas da confirmação nova; a rodada de casas foi refeita com 196 alvos.
- Parâmetros candidatos salvos com incerteza. Nenhuma substituição automática
  de K, pesos ou pisos: ganhos pequenos não confirmados, ou troca entre precisão
  e dispersão no caso territorial. Perfil atual venceu para vagas residenciais.
- Correção da área de terrenos em condomínio e orientação no formulário aplicadas.
- 37 testes aprovados; conferência independente das métricas, dos pares e da
  ausência de imóveis repetidos nos novos testes passou (`verification.json`).
- Relatórios Markdown, HTML, CSV, JSON e figura SVG gerados. Prévia HTML no
  navegador bloqueada pela política de URL local; entrega textual aberta no Codex
  e estrutura HTML/SVG conferida sem navegação alternativa.
