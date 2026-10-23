# Instalação corporativa sem internet

A aplicação opera obrigatoriamente sem serviços externos. O servidor processa
as planilhas e o navegador acessa apenas o servidor corporativo. Não existe
configuração para reativar Nominatim, downloads de base ou mapas externos.
Os lotes fiscais são desenhados a partir da base instalada `assets/lotes_fiscais.sqlite`,
com manifesto `assets/lotes_fiscais.json` e módulo `local_parcel_map.py`.
Os parâmetros antigos `fetch_tiles` e `fetch_map_tiles` permanecem aceitos para
compatibilidade e não habilitam rede, mesmo quando verdadeiros.

## Preparação da distribuição

Em uma máquina de preparação conectada, com o mesmo sistema, arquitetura e
versão Python do servidor, obtenha o repositório completo. A base de Porto
Alegre está em `assets/eixos_poa/`, fora da pasta pública `static/`.
Os quatro arquivos são conferidos pelos hashes SHA-256 definidos no código.
Sua origem é a base Eixos do Space `fschwartzer/Geocode`, já utilizada pelo projeto;
esta mudança preserva os mesmos arquivos e não altera a interpolação.

O arquivo `requirements-local.lock.txt` fixa a distribuição validada em Windows
x64/Python 3.14. Para outra plataforma, valide a compatibilidade antes de distribuir.
Prepare os pacotes previamente, sem instalar nada durante a execução do aplicativo:

```powershell
python -m pip download --only-binary=:all: -r requirements-local.lock.txt -d wheelhouse
```

Transfira a pasta do aplicativo, a base e `wheelhouse` pelo canal corporativo aprovado.
O diretório de pacotes é específico da plataforma e não é versionado no Git.

## Instalação no servidor isolado

Execute na raiz do projeto, em ambiente virtual exclusivo:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --no-index --find-links=wheelhouse -r requirements-local.lock.txt
.venv\Scripts\python.exe scripts/verify_local_install.py
.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

Use o proxy HTTPS/autenticação da organização para encaminhar o acesso corporativo
ao servidor. Se a infraestrutura exigir acesso direto pela rede, configure o endereço
de escuta e as regras de firewall conforme a política interna. Preserve as proteções
CORS/XSRF padrão do Streamlit. A configuração do projeto desativa estatísticas de uso.
Execute sempre a partir da raiz, para carregar `.streamlit/config.toml`.

Bloqueie a saída à internet no servidor e nas estações durante a homologação.
Teste upload, endereço local, endereço não resolvido, coordenadas explícitas,
estimativa, mapa interativo e download do PDF. Confirme no navegador que não há
requisições para domínios externos. O bloqueio de saída também é a garantia de
infraestrutura contra comportamentos futuros de dependências.

## Comportamento e limites

- Mapas mostram os contornos locais dos lotes, preservando pontos e comparáveis.
  A tela permite selecionar lotes fiscais ou fundo neutro. Não há tiles externos.
- Base ausente ou com hash inválido gera mensagem explícita; não ocorre download.
- Endereço não resolvido conserva o motivo da falha. Informe coordenadas ou escolha
  explicitamente ignorar localização; o sistema não troca sozinho para busca online.
- Geocodificação cobre Porto Alegre, com as limitações da base e da interpolação.
- O núcleo e seus parâmetros não mudaram. Com coordenadas idênticas, o cálculo é o
  mesmo. A redução de cobertura pode afetar composição da amostra, COD, PRD e
  regressividade: não constitui evidência de melhora ou piora sem avaliação própria.

Verificação reproduzível: `python -m unittest discover -s tests -v`.

## Base visual de lotes fiscais

Fonte: extração SMAMUS `01_PUBLICACOES/dmweb_lotes_fiscais/FeatureServer/0`,
coletada em 20/10/2026. O catálogo da extração confirma EPSG:4326 e o hash
`37b5bd9bc3b7df6e9c21271c8e43b963a1570d6e0b59c96eb280cedd427d8a33`.
São 283.290 polígonos, incluindo multipolígonos e anéis internos. As coordenadas
são preservadas integralmente; os atributos cadastrais foram removidos da cópia
visual. O original no Playground permanece intacto. Coleta não comprova vigência
nem cobertura completa; os contornos não certificam a inscrição dos pontos.

O índice SQLite/RTree consulta retângulos em graus WGS84, sem medir distância,
intersectar alvos ou criar variáveis do modelo. O custo de leitura depende do
número de lotes do recorte, limitado a 20 mil. Acima disso, não se mostra um
subconjunto arbitrário: há aviso explícito para reduzir a região. No mapa
interativo use “Aproximação cartográfica”; os contornos são carregados no servidor
para a região dos pontos e precisam ser recarregados ao navegar para fora dela.
No PDF, o recorte acompanha o enquadramento dos pontos. Base ausente/corrompida
ou região sem lotes resulta em pontos sobre fundo neutro e motivo explícito.

Repreparação offline a partir do GeoJSON original, em um destino novo:

```powershell
python scripts/prepare_parcel_map.py CAMINHO_DO_GEOJSON assets/lotes_fiscais.sqlite
```

A preparação usa apenas a biblioteca padrão e conserva o hash da fonte e o hash
da base preparada no manifesto. O verificador de instalação confere a integridade.
Não há influência sobre COD, PRD, regressividade, pesos ou seleção do KNN.
