# VERA: Eixos locais, mapas CARTO e fallback Nominatim

Desde a versão 1.19.2, os mapas e a geocodificação retomam os serviços online
anteriores. A base dos Eixos permanece incorporada ao VERA. A aplicação não
consulta o Hugging Face nem baixa shapefiles em execução.

## Fluxo

1. Coordenadas fornecidas na planilha ou formulário continuam utilizáveis.
2. Endereços de Porto Alegre usam primeiro a correspondência do logradouro e
   a interpolação do número no eixo viário local.
3. Quando o eixo não resolve o endereço, a aplicação consulta Nominatim online.
   Mantém cache, timeout e intervalo mínimo de 1,05 s no limitador. Endereços
   resolvidos localmente não são enviados ao Nominatim.
4. O mapa da tela usa CARTO Positron por padrão, com OpenStreetMap e fundo
   neutro como alternativas. O PDF usa tiles vetoriais CARTO e registra a
   contingência de grade neutra quando os tiles não estão disponíveis.

Nominatim recebe os endereços consultados. O navegador solicita mapas
CARTO/OpenStreetMap; o servidor solicita tiles CARTO para o PDF. Esses serviços
exigem rede. O cálculo e o geocodificador dos Eixos continuam locais.
Estatísticas de uso do Streamlit permanecem desativadas.

## Recursos instalados

- `app.py`, módulos de núcleo/schema e `vera_pdf_report.py`;
- `geocodificador_porto_alegre.py` e `siri_export_adapter.py`;
- `assets/eixos_poa/Eixos.shp`, `.shx`, `.dbf` e `.prj`;
- `static/vera_header.png` e `.streamlit/config.toml`;
- dependências de `requirements.txt` ou versões de `requirements-local.lock.txt`;
- `scripts/verify_local_install.py`.

O verificador carrega os Eixos após validar os quatro hashes SHA-256 definidos
no geocodificador. Base ausente/corrompida nunca é baixada automaticamente.
Na interface, há aviso explícito antes do fallback Nominatim. Reinstale a base
copiando os quatro arquivos íntegros da distribuição do VERA.
Os Eixos usam TM-POA, transformado em WGS84 para as coordenadas resultantes.
Lotes fiscais não são carregados pelos mapas nem exigidos pelo verificador.
Seus utilitários/dados históricos permanecem no repositório sem dependência
do fluxo atual e sem participação no cálculo de estimativas.

## Instalação

Na raiz do projeto, em ambiente virtual exclusivo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe scripts/verify_local_install.py
.venv\Scripts\python.exe -m streamlit run app.py
```

Para preparar dependências previamente, use uma máquina conectada com o mesmo
sistema, arquitetura e Python do servidor:

```powershell
python -m pip download --only-binary=:all: -r requirements-local.lock.txt -d wheelhouse
```

Transfira os pacotes e instale no servidor:

```powershell
.venv\Scripts\python.exe -m pip install --no-index --find-links=wheelhouse -r requirements-local.lock.txt
```

O lock corresponde à distribuição Windows x64/Python 3.14 validada. Instalação
por wheels não torna os mapas e o fallback Nominatim offline. Para uso corporativo,
use HTTPS/autenticação e regras de rede da organização, mantendo CORS/XSRF.
Inicie a aplicação na raiz para carregar a configuração do projeto.

## Verificação e metodologia

`python -m unittest discover -s tests -v`

Os testes simulam Nominatim e CARTO para verificar o fluxo sem enviar endereços
nem depender da rede. Conferem geocodificação local, fallback, integridade e
que os Eixos não têm rotina de download.
Coordenadas iguais preservam o cálculo. Recuperar cobertura pelo Nominatim pode
mudar comparáveis e trazer erros de localização/viés espacial. Não houve ajuste
de pesos ou modelo; sem nova feature, tuning ou leakage/overfitting adicional.
Não se presume melhora de COD, PRD ou regressividade sem avaliação independente.

## Exportação SIRI com cabeçalhos camelCase

O importador reconhece a exportação com `fonteTransacao`, `finalidadeNmeSiat`,
`finalidadeNmeCrawlerSiri` e campos PMI/Crawler. Preserva todas as colunas originais
(inclusive metadados que não entram no KNN) e acrescenta aliases de compatibilidade:

| Informação | Regra da exportação |
|---|---|
| Tipo | `fonteTransacao`, distinguindo Oferta/Guia ITBI |
| Finalidade | SIAT com fallback PMI; tipo do Crawler para ofertas, com auditoria de conflitos existente |
| Preço da guia | Somente `valorGuiaTotalDeclarado`, sem substituição pelo atribuído |
| Área territorial da guia | Somente `guiaAreaTerrTransmitida`, inclusive em transmissões parciais |
| Preço da oferta | `valorOfertaCrawler`, depois `valorOfertaPmi` |
| Área territorial da oferta | Privativa PMI/SIAT; na ausência, lote fiscal PMI/SIAT fora de condomínio |
| Área em condomínio | Área da unidade; não substitui pela área coletiva |
| Área construída | Total Crawler/PMI ou SIAT; guias priorizam `guiaAcoTransmitida` |
| Área privativa | `acoPrivativaCrawler` / `acoPrivativaPmi` |
| Coordenadas | Par válido Crawler, depois par válido PMI; nunca combina fontes |
| Endereço | Logradouro e número selecionados da mesma fonte |
| Inscrição/IDs | Aliases para deduplicação por inscrição/preço e identificadores do anúncio |
| Datas | Encaminhamento/registro mantidos como disponibilidade cadastral; sem inferir ano da construção |

Registros sem preço declarado ou área transmitida válida não recebem valor
atribuído ou área total fiscal como substitutos. Campos de auditoria indicam
origem do preço, origem das coordenadas e regra de área. Transmissões parciais
são contadas nas notas para revisão de direitos e comparabilidade. Os campos
não usados pelo estimador continuam na base e nas exportações de diagnóstico.
