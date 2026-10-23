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

# Preservação de comparáveis de alto padrão — 12/10/2026

## Objetivo e decisão metodológica
- Preservar registros de alto valor unitário, inclusive lançamentos informados
  pelo usuário em até R$ 30 mil/m², sem usar esse valor como teto de mercado.
- Até a referência residencial informada (R$ 30 mil/m²), valor alto isolado gera
  alerta auditável e não constitui prova de erro cadastral.
- Manter regras determinísticas, exclusões inferiores, deduplicação, desconto
  de ofertas, seleção por características/localização e controle de pesos.
- Preservar essa faixa também na média final e reportar sensibilidade à regra
  anterior. Acima dela, manter controle robusto, inclusive para ofertas: a base
  contém ofertas de milhões de R$/m² que antes escapavam do pré-filtro ITBI.
- A referência não é teto: a faixa protegida é o maior entre R$ 30 mil/m² e o
  limite estatístico. A definição vem do usuário, não de otimização no teste.
- Ano de construção e data de cadastramento são conceitos distintos; não imputar
  ano de lançamento a partir de preço ou data da guia.
- Preservar interfaces e colunas existentes dos notebooks e da exportação.

## Execução
1. [concluído] Auditar fonte, pré-filtro global e winsorização; guardar evidência
   anterior. Apartamentos: limite superior de R$ 16.828,52/m² e 71 guias excluídas.
2. [concluído] Conferir cobertura de apartamentos no Moinhos de Vento por
   ano de construção e etapa, usando o nome cadastral `moinhos vento`.
   Maior ano bruto: 2019; após exigir coordenadas, 2016. Sem ano cadastral 2026.
3. [concluído] Preservar faixa residencial até R$ 30 mil/m² (ou limite robusto
   maior), com alertas, no preparo e no cálculo; controle acima da faixa também
   para ofertas. Atualizadas explicações e diagnósticos. 45 testes aprovados.
4. [concluído] Comparar comportamento antes/depois sem ajuste de parâmetros:
   casos de alto VU e amostra temporal fixa, com bloqueio de identidade antes
   da preparação e avaliação de COD, PRD, mediana e estratos de valor.
   99 pares sem falhas. No decil superior de apartamentos, mediana das razões
   0,864 → 0,890 e COD 18,13 → 17,19. PRD global de apartamentos e casas piorou;
   melhora de equidade não confirmada. Não houve recalibração de parâmetros.
5. [concluído] Finalizar documentação, verificações e relatório de limitações.
   Relatório e evidências em `artifacts/diagnostics/2026-10-12/RELATORIO.md`.
   Código local atualizado e 45 testes aprovados; publicação não realizada.

## Critérios e ressalvas
- Dados originais não são editados. Novos comparáveis continuam sujeitos à
  disponibilidade e qualidade de área, ano e coordenadas.
- A cauda superior protegida pode conter erros: alertas e contribuição dos dados
  altos devem permanecer visíveis; o limite de peso não elimina esse risco.
- O teste de agosto/setembro já foi examinado. A comparação nele é diagnóstico
  de sensibilidade, não confirmação independente nem recalibração de K/pesos.
- Não declarar ganho de equidade ou COD/PRD antes de medir; não escolher
  parâmetros usando preço do avaliando ou informação futura.


# Modo local obrigatório — 23/10/2026

## Objetivo
Executar sem internet no servidor e navegador, com base e dependências instaladas.

## Execução
1. [concluído] Auditar saídas: eixo viário, Nominatim, mapas interativo/PDF.
2. [concluído] Remover downloads/fallbacks; incluir eixo com hashes e fundo neutro.
3. [concluído] Preparar instalação offline e testes com rede bloqueada.
4. [concluído] Revisar diff, validar e publicar branch/PR no GitHub (PR #1).

## Restrições e hipótese
- Núcleo, pesos, seleção e interfaces de notebooks permanecem compatíveis.
- Hipótese: mesmas entradas com coordenadas produzem os mesmos resultados.
- Sem ajuste de modelo ou parâmetros: nenhum novo risco de overfitting ou leakage.
- Cobertura menor sem Nominatim pode alterar seleção da amostra e viés espacial;
  não alegar melhora em COD, PRD ou regressividade. Comparar em base reservada
  antes de usar populações com cobertura diferente.

## Verificação do modo local
- 49 testes aprovados com conexões de rede bloqueadas.
- Interface inicializada permitindo apenas conexões de loopback.
- Instalação limpa com --no-index e base geográfica íntegra aprovada.
- Pacote local Windows x64/Python 3.14 preparado com os wheels.
- Homologação do tráfego do navegador na rede corporativa ainda depende da infraestrutura final.

# Lotes fiscais como suporte visual — 23/10/2026

1. [concluído] Preparar base local compacta, com origem, hash e CRS documentados.
2. [concluído] Integrar consulta espacial e contornos nos mapas da tela e PDF.
3. [concluído] Validar seleção por região, ausência de rede, desempenho e aparência.

Hipótese: suporte estritamente visual, sem alteração de entradas, distâncias, pesos
ou seleção de comparáveis. Não cria features nem utiliza preços; sem novo leakage
ou overfitting. COD, PRD e regressividade não se alteram pelo desenho cartográfico.
Consulta por retângulo em longitude/latitude; não mede distâncias nem atribui
lote a ponto. Cobertura cadastral e posição geocodificada podem divergir.

Verificação: prévia PNG do mapa PDF inspecionada; GeoJSON embutido no Plotly
validado pelo esquema e por teste de integração sem rede. Consulta real de
5.681 lotes em 0,271 s nesta máquina (medição pontual, sem garantia de SLA).
Base preparada: 93.786.112 bytes, 283.290 polígonos, CRS confirmado no catálogo
da extração com mesmo SHA-256. Prévia interativa no navegador não homologada.
