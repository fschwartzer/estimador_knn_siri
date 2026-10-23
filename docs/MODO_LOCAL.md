# Instalação corporativa sem internet

A aplicação opera obrigatoriamente sem serviços externos. O servidor processa
as planilhas e o navegador acessa apenas o servidor corporativo. Não existe
configuração para reativar Nominatim, downloads de base ou mapas externos.
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

- Não há cartografia de ruas: mapas preservam pontos, enquadramento e comparáveis.
- Base ausente ou com hash inválido gera mensagem explícita; não ocorre download.
- Endereço não resolvido conserva o motivo da falha. Informe coordenadas ou escolha
  explicitamente ignorar localização; o sistema não troca sozinho para busca online.
- Geocodificação cobre Porto Alegre, com as limitações da base e da interpolação.
- O núcleo e seus parâmetros não mudaram. Com coordenadas idênticas, o cálculo é o
  mesmo. A redução de cobertura pode afetar composição da amostra, COD, PRD e
  regressividade: não constitui evidência de melhora ou piora sem avaliação própria.

Verificação reproduzível: `python -m unittest discover -s tests -v`.
