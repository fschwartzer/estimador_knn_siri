![Logotipo VERA](./static/vera_header.png)
# VERA
## Valor Estimado por Referências Amostrais

Aplicativo web para estimar o valor de imóveis a partir de transações e
ofertas comparáveis. Combina similaridade física, proximidade geográfica e
tratamentos estatísticos robustos em um fluxo simples, auditável e preparado
para planilhas do SIRI.

| | |
|---|---|
| **Interface** | Aplicativo web em Streamlit |
| **Método** | K-vizinhos mais próximos (KNN) |
| **Entrada** | Planilhas Excel nos formatos `.xlsx`, `.xlsm` ou `.xls` |
| **Saída** | Estimativa, comparáveis, mapa, diagnósticos e relatório Excel |
| **Abrangência** | Imóveis prediais e territoriais |
| **Versão atual** | LITE 1.17.0 · núcleo 6.12.0 |

## O que o aplicativo faz

A VERA recebe uma planilha de dados imobiliários e encontra os
imóveis mais compatíveis com o bem avaliando. O processo:

1. reconhece e normaliza o schema da planilha;
2. seleciona registros da mesma finalidade imobiliária;
3. exclui aluguéis, duplicidades e observações inválidas;
4. ajusta ofertas em relação às transações observadas;
5. calcula a similaridade física e a proximidade geográfica;
6. escolhe adaptativamente os comparáveis e limita concentrações de peso;
7. reduz a influência de valores extremos com tratamento robusto;
8. apresenta o valor estimado e os elementos necessários à auditoria.

Para imóveis prediais, a similaridade física considera a área do regime
selecionado e o ano da construção. Para terrenos, considera a área do lote e
a testada. O aplicativo trabalha com um único regime de área em cada
estimativa, evitando misturar denominadores incompatíveis.

## Principais recursos

- reconhecimento automático das colunas usadas pelo SIRI;
- taxonomia normalizada de finalidades imobiliárias;
- tratamento separado para imóveis prediais e territoriais;
- área privativa ou área total/construída como base da estimativa;
- ano da construção como atributo físico de imóveis prediais;
- K adaptativo e perfis de parâmetros por finalidade;
- combinação de distância física e distância geográfica;
- deduplicação de ofertas e exclusão de ofertas de aluguel;
- fator de oferta calculado ou conservador, conforme a amostra;
- pré-filtros, controles de cauda e média ponderada robusta;
- controle de conflitos tipológicos;
- limite para o peso individual de cada comparável;
- mapa interativo do avaliando e dos comparáveis;
- alertas de extrapolação, cobertura e concentração dos pesos;
- exportação de comparáveis, diagnósticos, exclusões e alertas para Excel.

## Como usar

1. Abra o aplicativo no navegador.
2. Envie a planilha Excel.
3. Selecione a finalidade do imóvel.
4. Escolha ou confirme o regime de área.
5. Informe as características do avaliando e suas coordenadas.
6. Clique em **Calcular estimativa**.
7. Analise o resultado, os comparáveis e o mapa.
8. Baixe o relatório Excel para auditoria ou documentação.

## Dados necessários

| Escopo | Informações esperadas |
|---|---|
| Todos os imóveis | Tipo da informação, finalidade, valor, latitude e longitude |
| Imóvel predial | Área privativa ou construída e `siat_ano` |
| Imóvel territorial | Área total do lote e testada |

O aplicativo possui aliases para diferentes nomes de colunas de área,
coordenadas e valores. A finalidade é convertida automaticamente para a
taxonomia utilizada pelo estimador. Imóveis prediais exigem um ano da
construção inteiro entre 1500 e o ano corrente.

## Linguagem e tecnologias

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.10 ou superior |
| Interface web | Streamlit 1.47+ |
| Manipulação de dados | pandas e NumPy |
| Leitura e escrita de Excel | openpyxl e xlrd |
| Mapas e visualizações | Plotly / MapLibre |
| Testes | `unittest` da biblioteca padrão |

As versões aceitas das bibliotecas estão declaradas em `requirements.txt`.

## Recursos necessários

### Software

- Python 3.10 ou superior;
- `pip` para instalação das dependências;
- navegador web atualizado;
- Git, caso o projeto seja obtido diretamente do repositório.

Não é necessário banco de dados, servidor externo ou GPU. Depois da
instalação das dependências, o cálculo é executado localmente. O mapa-base
depende de acesso à internet; sem ele, o aplicativo pode usar o modo sem
mapa-base.

### Hardware

- processador convencional de 64 bits;
- pelo menos 4 GB de memória disponível para planilhas pequenas ou médias;
- 8 GB ou mais para bases maiores.

As planilhas são processadas em memória. O limite configurado para upload é
de 200 MB, mas o consumo efetivo de RAM pode ser várias vezes maior que o
tamanho do arquivo Excel.

## Como rodar localmente

Clone o repositório e entre na pasta do projeto:

```powershell
git clone https://github.com/fschwartzer/estimador_knn_siri.git
cd estimador_knn_siri
```

Crie e ative um ambiente virtual no Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

No Linux ou macOS, a ativação é:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependências e inicie o aplicativo:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

O Streamlit exibirá no terminal o endereço local, normalmente
`http://localhost:8501`.

## Testes

Execute a suíte automatizada a partir da raiz do projeto:

```powershell
python -m unittest discover -s tests -v
```

Os testes verificam a integridade da versão publicada, o mapeamento do schema,
a ativação dos atributos físicos e o tratamento do ano da construção.

## Estrutura do repositório

```text
estimador_knn_siri/
├── app.py                         # interface e orquestração
├── estimador_knn_core_v6120.py    # cálculo e diagnósticos do KNN
├── estimador_knn_schema_v6120.py  # normalização do schema SIRI
├── requirements.txt               # dependências de execução
├── tests/                         # testes automatizados
├── artifacts/calibration/         # evidências e resultados de calibração
├── archive/legacy/                # módulos de versões anteriores
├── docs/                          # documentação histórica
└── .streamlit/config.toml          # tema e configuração do servidor
```

Os módulos de `archive/legacy/` não participam da execução atual. Eles foram
preservados apenas para rastreabilidade e reprodução de resultados antigos.

## Publicação no Streamlit Community Cloud

Defina `app.py` como arquivo principal. Os arquivos indispensáveis no mesmo
repositório são:

- `app.py`;
- `estimador_knn_core_v6120.py`;
- `estimador_knn_schema_v6120.py`;
- `requirements.txt`;
- `.streamlit/config.toml`.

## Rastreabilidade e uso responsável

O aplicativo é um instrumento de apoio à avaliação, não um substituto para a
análise técnica. Os comparáveis, exclusões, pesos e diagnósticos devem ser
revisados antes do uso operacional do resultado.

Em avaliações em massa, valide o modelo em dados separados do ajuste e
acompanhe, além dos erros preditivos, a mediana das razões, COD, PRD,
regressividade por faixa de valor e estabilidade temporal e espacial. A
ausência sistemática de atributos, como o ano da construção, pode reduzir a
cobertura e introduzir viés amostral.

## Documentação complementar

- `VERSION.txt`: identificação da versão em produção;
- `README_DEPLOY.txt`: lista mínima para publicação;
- `docs/HISTORICO_VERSOES.md`: histórico funcional até a versão 1.16.0;
- `artifacts/calibration/`: parâmetros e relatórios de calibrações anteriores.
