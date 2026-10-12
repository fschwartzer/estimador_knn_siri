# VERA — comparáveis de alto padrão e ajuste dos filtros

Auditoria de 12/10/2026. Fonte: extração SIRI de 23/09/2026, 730.246 linhas,
com datas de cadastro de 23/09/2023 a 22/09/2026. A planilha original não foi
alterada. Código ajustado localmente; publicação não realizada nesta tarefa.

## Decompor

Há três mecanismos distintos:

1. **Disponibilidade cadastral:** ano de construção não é data de encaminhamento
   nem data do negócio. A data de encaminhamento é usada na deduplicação, mas
   não dá preferência temporal aos comparáveis no KNN.
2. **Preparação:** o pré-filtro anterior comparava o log do valor unitário das
   Guias ITBI com a distribuição da finalidade inteira, sem separar padrão,
   bairro ou período. Com 15 guias, extremos superiores eram excluídos.
3. **Cálculo final:** valores altos sobreviventes podiam ser reduzidos pela
   winsorização em torno da mediana ponderada dos vizinhos.

Valor unitário elevado é um marcador exploratório. Não equivale a padrão
construtivo alto nem comprova a validade do preço ou do denominador da área.

### Evidência anterior na base completa

| Finalidade | Limite robusto superior anterior (R$/m²) | Guias excluídas na cauda superior | Dessas, até R$ 30 mil/m² |
|---|---:|---:|---:|
| Apartamento | 16.828,52 | 71 | 52 |
| Cobertura | 20.696,81 | 4 | 4 |
| Casa/residência | 23.915,27 | 33 | 10 |

Entre as 71 exclusões superiores de apartamentos, 13 tinham cadastro desde
01/04/2026, sendo 11 abaixo de R$ 30 mil/m². Esses registros podem ser legítimos;
a auditoria não certifica preço, integralidade da transmissão ou área.

Também há erros aparentes muito grandes: no treino temporal auditado havia
77 ofertas de apartamento e uma de cobertura acima de R$ 1 milhão/m².
Elas sobreviviam ao pré-filtro anterior, que tratava estatisticamente guias,
mas não a cauda superior de ofertas. Remover todo o tratamento superior
deixaria esse tipo de dado contaminar o cálculo.

### Moinhos de Vento

O bairro aparece como `moinhos vento` no cadastro. A análise abaixo se limita
às linhas classificadas como apartamento com esse bairro cadastral; não usa
um polígono territorial para corrigir eventuais bairros incorretos.

- Não há ano de construção 2026 nessas linhas; o maior ano informado é 2019.
- Há 167 linhas com ano 2019, somando guias e ofertas, todas sem coordenadas
  válidas. Após deduplicação e filtros anteriores, restavam 51; após o ajuste,
  restam 54. Todas continuam sem coordenadas.
- Ao exigir localização, o maior ano disponível cai para 2016. A preferência
  por comparáveis até 2015 no caso relatado também pode depender da área e da
  localização exatas do avaliando, que não foram recuperadas nesta tarefa.
- Seis guias de apartamento do bairro, entre R$ 16.932,38 e R$ 21.431,21/m²,
  eram excluídas exclusivamente pela cauda superior anterior e passam a ser
  preservadas nessa etapa. Nem todas poderão entrar em uma seleção espacial.

| Base preparada do bairro | Antes | Depois |
|---|---:|---:|
| Registros totais | 1.713 | 1.717 |
| Com coordenadas válidas | 1.608 | 1.609 |
| Entre R$ 15 mil e R$ 30 mil/m² | 79 | 85 |

A variação líquida de quatro registros reúne a recuperação de seis guias
com a exclusão superior de duas ofertas. A faixa protegida não comprova que
um valor acima dela esteja errado: exclusões acima da referência e do limite
estatístico continuam exigindo revisão de preço, área e natureza do negócio.

## Resolver

Foram alterados o núcleo, as explicações da interface, a documentação e a
triagem de calibração, preservando as interfaces públicas dos notebooks.

- Apartamentos, coberturas e casas preservam valores até **R$ 30 mil/m²** nos
  controles da cauda superior da preparação e do cálculo final.
- A faixa efetiva é o **maior entre R$ 30 mil/m² e o limite estatístico**;
  portanto, a referência não impõe um teto universal de mercado.
- A referência foi informada pelo usuário nesta tarefa, não estimada usando
  os preços do teste. Está centralizada em `PURPOSE_UPPER_TAIL_PROTECTION`.
- Valores altos acima da faixa estatística antiga e dentro da faixa protegida
  permanecem em alerta, com motivo e contagem exportáveis.
- No preparo, valores residenciais acima de ambas as referências ficam sujeitos
  ao controle superior também nas ofertas, com pelo menos 15 Guias ITBI para
  exclusão automática. Com amostra insuficiente, permanecem em alerta.
- Na média final, o limite superior de winsorização não pode ficar abaixo da
  faixa protegida. O fator de oferta continua aplicável aos anúncios.
- Pisos, regras cadastrais, regime de área, duplicidades, filtros inferiores,
  validação de ano/coordenadas, seleção física/espacial e limite de peso
  individual continuam aplicáveis. Preservação no filtro não obriga seleção.
- Outras finalidades mantêm o tratamento anterior.

Não foram imputados anos recentes a partir de preço ou data de cadastro,
nem coordenadas pelo centro do bairro. A correção não cria referências de
lançamentos ausentes ou resolve o cadastro espacial incompleto.

## Verificar

**45 testes aprovados.** Os novos testes incluem guias de R$ 20 mil e R$ 30 mil/m²,
o limite exato da faixa, preservação no cálculo final, oferta com erro de
R$ 10 milhões/m², continuidade dos controles inferiores/cadastrais, amostra
pequena e preservação das demais finalidades. O teste de triagem também confere
consistência com o núcleo.

A comparação real usa **99 pares**, sem falhas: 43 apartamentos, 23 coberturas
e 33 casas. Semente 12102026, amostragem aleatória fixa acrescida dos três
maiores valores totais por finalidade. K, pesos, pisos e desconto máximo não
foram otimizados. O treino é anterior a 01/08/2026; alvos são guias do teste
anterior de agosto/setembro. Inscrição e assinatura coordenada/área de todos
os alvos comparados são retiradas antes de preparar dados, ajustar ofertas e
padronizar atributos. Distâncias seguem o núcleo: aproximação local em km,
com escalas calculadas apenas no treino.

O teste já havia sido examinado, e a amostra inclui reforço deliberado dos
imóveis caros. Esta é uma **comparação descritiva de sensibilidade**, não uma
validação nova ou estimativa representativa da população.

### Métricas na amostra pareada completa

Razão = estimativa/valor da guia. COD é dispersão dessas razões, em percentual.
PRD utiliza valores totais. Essas métricas diferem do COD local dos comparáveis.

| Finalidade | n | Mediana da razão antes → depois | COD antes → depois | PRD antes → depois |
|---|---:|---:|---:|---:|
| Apartamento | 43 | 1,003 → 1,031 | 34,48 → 34,56 | 1,137 → 1,147 |
| Cobertura | 23 | 0,862 → 0,874 | 31,41 → 31,74 | 1,213 → 1,189 |
| Casa/residência | 33 | 0,978 → 1,070 | 65,83 → 65,96 | 1,214 → 1,251 |

### Decil superior de valor total do teste original

Os pontos de corte vêm da distribuição do teste antigo de cada finalidade;
não são usados para criar features, preparar treino ou selecionar parâmetros.

| Finalidade | n na comparação | Mediana da razão antes → depois | COD antes → depois | PRD antes → depois |
|---|---:|---:|---:|---:|
| Apartamento | 10 | 0,864 → 0,890 | 18,13 → 17,19 | 1,006 → 1,012 |
| Cobertura | 4 | 0,541 → 0,576 | 38,52 → 39,88 | 0,942 → 0,947 |
| Casa/residência | 6 | 0,845 → 0,851 | 21,74 → 23,26 | 0,953 → 0,957 |

No treino temporal, registros entre R$ 15 mil e R$ 30 mil/m² passaram de
3.042 para 3.089 em apartamentos, de 78 para 82 em coberturas e de 105 para
119 em casas. As 78 ofertas acima de R$ 1 milhão/m² saíram desse treino.
Há diagnósticos por bairro nos CSVs, mas amostras pequenas e a ausência de um
novo teste espacial impedem concluir estabilidade espacial da mudança.

## Sintetizar

A hipótese de perda pelo tratamento superior foi confirmada. A implementação
protege a faixa de mercado indicada e limita erros muito maiores, mantendo
rastreabilidade. No Moinhos de Vento, a ausência de ano 2026 e a falta de
coordenadas nos registros de 2019 explicam uma limitação adicional importante.

Há melhora de nível no grupo de maior valor, mas COD e PRD não melhoram de
forma uniforme. O PRD global piorou para apartamentos e casas na amostra.
Logo, recuperação de comparáveis, precisão operacional e equidade tributária
são resultados distintos. A mudança não resolve a regressividade.

## Ressalvas e confiança

- **Confiança alta** nas contagens, na cobertura cadastral observada e no
  comportamento implementado. **Moderada** na atribuição ao caso relatado,
  pois faltam área e localização exatas. **Baixa** para generalizar as mudanças
  de métricas ou a validade mercadológica individual dos registros.
- A faixa protegida pode conservar erros dentro de R$ 30 mil/m². Conferir
  preço, integralidade da transmissão, área privativa/construída e natureza.
- Alterar a cauda superior pode elevar estimativas de imóveis comuns quando
  padrão/acabamento não está representado nos atributos. Isso pode agravar
  viés e regressividade, como sinaliza o PRD desta amostra.
- Não houve ajuste de hiperparâmetros no teste; permanece risco de generalização
  da regra operacional. A referência precisa ser revista com dados de mercado
  e área consistentes, em validação futura independente.
- Log é usado no pré-filtro; a previsão final continua na escala original.
  Não houve nova transformação do alvo nem necessidade de retransfomação log.
- Para lançamentos, são necessárias referências de ano/preço verificáveis e
  coordenadas ou endereço utilizável para geocodificação. Desativar localização
  sem avaliar sua consequência não é solução equivalente para um bairro caro.

## Evidências e reprodução

- Fonte: `artifacts/calibration/SIRI_pesquisa_aluguel-23.09.2026 14.41.22.xlsx`.
- SHA-256 da fonte: `380fa728f4a4ffa9731305ec5cb8275bfeccdc5974cb7e656edb30fde94188ce`.
- `diagnostico.json`: fotografia anterior, limites, contagens e hashes.
- `exclusoes_cauda_superior.csv`: linhas excluídas anteriormente, valores e motivos.
- `contagens_por_etapa.csv` e `moinhos_anos_por_etapa.csv`: cobertura por etapa.
- `comparacao_metricas.csv`, `comparacao_previsoes.csv` e `comparacao_espacial.csv`:
  pares, métricas e estratos. `comparacao_moinhos.csv`: antes/depois do bairro.
- `comparacao_preparacao.csv`: efeito no conjunto de comparáveis de treino.
- `comparacao_proveniencia.json`: hashes, semente e corte temporal.
- `core_before.py`: núcleo anterior congelado. `audit_alto_padrao.py` reproduz
  a fotografia anterior; `compare_filters.py` reproduz a comparação pareada.

O cache residencial de 23/09/2026 foi reutilizado após verificar o hash da
planilha. O diff do schema anterior para o atual só modifica terrenos em
condomínio; uma amostra residencial de 300 linhas também foi reconciliada
com o schema atual. A auditoria não muda a fonte nem os resultados antigos
da calibração de setembro.
