# estimador_knn_siri — LITE 1.2

Edição LITE do estimador imobiliário por KNN, preparada para usuários sem
conhecimento estatístico ou de aprendizado de máquina.

## O que o usuário precisa fazer

1. Enviar a planilha Excel.
2. Escolher a finalidade.
3. Confirmar se é terreno/lote ou unidade construída.
4. Informar áreas, testada quando territorial, latitude e longitude.
5. Clicar em **Calcular estimativa**.

## Processamentos automáticos

A aplicação mantém internamente os tratamentos da versão técnica:

- filtro pela finalidade;
- exclusão de ofertas de aluguel;
- deduplicação das ofertas pela data mais recente;
- desconto das ofertas pela mediana de razões pareadas com Guias ITBI;
- K adaptativo;
- mínimo de cinco vizinhos efetivos;
- limite de 30% de peso por comparável;
- potência de distância igual a 1;
- média robusta por mediana e MAD;
- alertas de extrapolação;
- pontuação de confiança;
- exportação dos comparáveis e diagnósticos para Excel.

O backtesting e todos os controles estatísticos foram removidos da interface.

## Parâmetros internos fixos

| Parâmetro | Valor |
|---|---:|
| K inicial | 7 |
| K máximo | 30 |
| Vizinhos efetivos mínimos | 5 |
| Peso físico | 75% |
| Peso geográfico | 25% |
| Peso máximo individual | 30% |
| Potência da distância | 1 |
| Limiar robusto | 2,5 MAD |
| Desconto máximo das ofertas | 20% |

## Execução local

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

Publique na raiz do repositório:

- `app.py`;
- `knn_valuation.py`;
- `schema_utils.py`;
- `requirements.txt`;
- pasta `.streamlit`.

Defina `app.py` como arquivo principal.


## Alertas do fator de oferta

A edição LITE 1.1 mantém integralmente o cálculo anterior e acrescenta apenas
avisos interpretativos.

### Faixas do desconto

| Desconto empírico | Alerta |
|---:|---|
| 0% | Sem desconto positivo aplicado |
| Acima de 0% até 10% | Elasticidade usual ou moderada |
| Acima de 10% até 15% | Elasticidade relevante |
| Acima de 15% até 20% | Elasticidade elevada |
| Acima de 20% bruto | Alerta forte; o teto de 20% continua sendo aplicado |

O desconto permanece definido pela mediana de
`1 - VU_ITBI / VU_Oferta` em quantis pareados, limitado entre 0% e 20%.

### Composição efetiva da amostra

Os números apresentados nos alertas correspondem aos dados que permanecem
após:

- filtro pela finalidade;
- exclusão de ofertas de aluguel;
- deduplicação das ofertas;
- validação do valor unitário.

| Menor grupo entre ITBI e ofertas | Alerta |
|---:|---|
| Menos de 2 | Insuficiente para calcular o desconto |
| 2 a 9 | Amostra reduzida |
| 10 a 14 | Amostra restrita |
| 15 ou mais | Quantidade mínima operacional atendida |

Quando ambos os grupos possuem ao menos 15 dados, o aplicativo também informa
se existe desequilíbrio superior a 3:1 ou 5:1 entre as quantidades.

Essas faixas são diagnósticas: não bloqueiam nem modificam o cálculo.


## Regra do fator de oferta — LITE 1.2

A regra passa a distinguir claramente dois cenários.

### Amostra composta somente por ofertas

Quando existe ao menos uma oferta válida e nenhuma Guia ITBI válida, aplica-se:

\[
Fator\ de\ oferta = 0,90
\]

ou seja, desconto convencional de 10%.

### Amostra com Guias ITBI e ofertas

Quando existem pelo menos duas Guias ITBI e duas ofertas válidas, o desconto é
calculado pela mediana dos quantis pareados:

\[
d = \operatorname{mediana}
\left(
1-\frac{VU_{ITBI,q}}{VU_{Oferta,q}}
\right)
\]

O resultado empírico é limitado ao intervalo de 0% a 20%. Portanto, 20% não é
um desconto fixo: é exclusivamente o freio superior da razão calculada.

### Amostra mista insuficiente

Quando existe alguma Guia ITBI, mas não há pelo menos dois dados válidos em
cada grupo, o desconto permanece em zero. O fator convencional de 10% é
reservado à situação em que não existe nenhuma Guia ITBI.

Nenhuma outra regra do estimador foi alterada.
