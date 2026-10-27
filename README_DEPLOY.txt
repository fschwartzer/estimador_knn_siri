VERA 1.19.2 — Eixos locais, mapas CARTO e fallback Nominatim.
Consulte docs/MODO_LOCAL.md.
PUBLICAR NA MESMA PASTA:
1. app.py
2. estimador_knn_core_v6120.py
3. estimador_knn_schema_v6120.py
4. geocodificador_porto_alegre.py e siri_export_adapter.py
5. vera_pdf_report.py
6. requirements.txt e requirements-local.lock.txt
7. assets/eixos_poa/ (Eixos.shp, Eixos.shx, Eixos.dbf, Eixos.prj)
8. .streamlit/config.toml e static/vera_header.png
9. scripts/verify_local_install.py

Execute a verificação local antes de iniciar.
Não há download nem consulta do Hugging Face em execução.
CARTO/OpenStreetMap e fallback Nominatim exigem rede.
Os lotes fiscais da versão anterior não são dependência do aplicativo.
