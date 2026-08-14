# estimador_knn_siri — LITE 1.17.0

Aplicativo Streamlit para estimativa imobiliária por KNN com seleção auditável
de comparáveis, filtros robustos e combinação de similaridade física e
proximidade geográfica.

## Novidade da versão 1.17.0

Imóveis prediais agora exigem o input **Ano da construção**. O aplicativo:

- mapeia automaticamente a coluna `siat_ano` da planilha;
- aceita anos inteiros entre 1500 e o ano corrente;
- usa a área do regime selecionado e o ano da construção como atributos
  físicos do KNN;
- exclui da candidatura registros com ano ausente ou inválido e registra a
  quantidade e as linhas excluídas na exportação;
- mantém terrenos sem o atributo de ano da construção.

O ano não aplica uma curva de depreciação presumida. Ele altera a afinidade e
o peso dos comparáveis: imóveis de idade construtiva mais próxima tendem a ter
menor distância física. Dentro do componente físico, área e ano recebem a
mesma participação; o peso total físico/geográfico continua sendo definido
pelo perfil calibrado da finalidade.

## Dados de entrada

A planilha deve conter, no mínimo:

- tipo da informação;
- finalidade;
- valor total ou unitário;
- latitude e longitude;
- área adequada ao regime da finalidade;
- `siat_ano` para imóveis prediais;
- área do lote e testada para imóveis territoriais.

Os aliases de área e finalidade reconhecidos permanecem compatíveis com a
versão 1.16.0.

## Cálculo e rastreabilidade

Para cada atributo físico ativo, a diferença em relação ao avaliando é
padronizada por escala robusta calculada somente na amostra de candidatos. A
distância física é a raiz da média das diferenças padronizadas ao quadrado.
Ela é combinada com a distância geográfica local conforme o perfil da
finalidade.

O fluxo também mantém:

- exclusão prévia de aluguéis;
- deduplicação de ofertas;
- fator de oferta;
- seleção de um único regime de área por estimativa;
- filtro de conflitos tipológicos;
- pré-filtros e tratamento robusto;
- K adaptativo e limite de peso individual;
- exportação de comparáveis, diagnósticos, exclusões e alertas.

Não há ajuste com dados do avaliando sobre a base de referência e não há
informação de validação/teste usada para criar o atributo.

## Execução local

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Testes

```powershell
python -m unittest discover -s tests -v
```

A suíte cobre ativação exclusiva em imóveis prediais, validação da faixa,
efeito do ano na distância física e auditoria de registros inválidos.

## Estrutura do repositório

- `app.py`: interface e orquestração do fluxo;
- `estimador_knn_core_v6120.py`: núcleo KNN ativo;
- `estimador_knn_schema_v6120.py`: normalização do schema ativo;
- `tests/`: testes automatizados;
- `artifacts/calibration/`: parâmetros, relatórios e tabelas de calibração;
- `archive/legacy/`: módulos antigos, fora do runtime;
- `docs/HISTORICO_VERSOES.md`: documentação histórica até a versão 1.16.0.

## Publicação no Streamlit Community Cloud

Defina `app.py` como arquivo principal e publique, na mesma raiz:

- `app.py`;
- `estimador_knn_core_v6120.py`;
- `estimador_knn_schema_v6120.py`;
- `requirements.txt`;
- `.streamlit/config.toml`.

## Verificação metodológica pendente

A inclusão do ano tem hipótese técnica plausível, mas melhora preditiva e
equidade não podem ser presumidas sem dados de validação. Antes de promover a
versão como recalibrada, compare a 1.16.0 e a 1.17.0 em amostra temporal ou
espacialmente separada, medindo ao menos mediana das razões, COD, PRD,
regressividade por decis de valor e estabilidade por segmento espacial. Anos
ausentes podem reduzir a amostra e introduzir viés de cobertura; esse risco é
explicitado nos diagnósticos.
