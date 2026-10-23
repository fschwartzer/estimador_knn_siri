INSTALAÇÃO LOCAL OBRIGATÓRIA — consulte docs/MODO_LOCAL.md.
PUBLICAR NA MESMA PASTA:
1. app.py
2. estimador_knn_core_v6120.py
3. estimador_knn_schema_v6120.py
4. geocodificador_porto_alegre.py
5. vera_pdf_report.py
6. requirements.txt
7. requirements-local.lock.txt
8. assets/eixos_poa/ (os quatro arquivos Eixos, com hashes validados)
9. .streamlit/config.toml e static/vera_header.png
10. scripts/verify_local_install.py
11. local_parcel_map.py, assets/lotes_fiscais.sqlite e assets/lotes_fiscais.json

Instale previamente as dependências com --no-index e execute a verificação local.
Mapas usam lotes fiscais locais; nenhum download ou fallback externo ocorre em execução.
