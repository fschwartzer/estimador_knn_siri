"""Leitura incremental do XLSX SIRI, sem carregar fotos/descrições na memória."""
from pathlib import Path
import json
import importlib.util
import hashlib
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
import estimador_knn_schema_v6120 as schema

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'artifacts/calibration/SIRI_pesquisa_aluguel-23.09.2026 14.41.22.xlsx'
OUT = ROOT / 'artifacts/calibration/2026-09-23'

def file_sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def extract():
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / 'source_selected.pkl'
    if cache.exists():
        provenance=OUT/'provenance.json'
        if provenance.exists():
            expected=json.loads(provenance.read_text(encoding='utf-8'))['source_sha256']
            actual=file_sha256(SOURCE)
            if actual!=expected:
                raise ValueError('Planilha alterada: os caches pertencem a outra extração.')
        return pd.read_pickle(cache)
    omit = {'anuncio_foto', 'descricao', 'pesquisador', 'imobiliaria_telefone',
            'revisao_observacao'}
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    rows, columns = [], {}
    with zipfile.ZipFile(SOURCE) as archive, archive.open('xl/worksheets/sheet1.xml') as stream:
        for _, element in ET.iterparse(stream, events=('end',)):
            if element.tag != ns + 'row':
                continue
            number = int(element.attrib['r'])
            record = {'_row_excel': number}
            for cell in element:
                letter = re.sub(r'\d+', '', cell.attrib['r'])
                if number > 1 and letter not in columns:
                    continue
                value = cell.find(ns + 'v')
                value = value.text if value is not None else ''.join(cell.itertext())
                if number == 1:
                    if value not in omit:
                        columns[letter] = value
                elif value is not None:
                    if cell.attrib.get('t') not in {'str', 'inlineStr', 's'}:
                        try:
                            value = float(value)
                        except ValueError:
                            pass
                    record[columns[letter]] = value
            if number > 1:
                rows.append(record)
            element.clear()
            if number % 25000 == 0:
                print(f'Lidas {number:,} linhas', flush=True)
    data = pd.DataFrame(rows)
    data.to_pickle(cache)
    return data

def audit():
    data = extract()
    if (OUT / 'enriched.pkl').exists() and (OUT / 'audit.json').exists():
        # Preserva a fotografia original mesmo após correções no schema.
        print((OUT / 'audit.json').read_text(encoding='utf-8'), flush=True)
        return
    original_schema = OUT / 'schema_original.py'
    audit_schema = schema
    if original_schema.exists():
        spec = importlib.util.spec_from_file_location('calibration_schema_original', original_schema)
        audit_schema = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = audit_schema
        spec.loader.exec_module(audit_schema)
    enriched, info = audit_schema.enrich_known_schemas(data)
    enriched['_date'] = pd.to_datetime(enriched['data_encaminhamento'], dayfirst=True, errors='coerce')
    enriched.to_pickle(OUT / 'enriched.pkl')
    summary = {'rows': len(data), 'columns': list(data.columns),
               'types': data['tipo_informacao'].value_counts(dropna=False).to_dict(),
               'date_min': str(enriched['_date'].min()), 'date_max': str(enriched['_date'].max()),
               'missing_dates': int(enriched['_date'].isna().sum()), 'schema_notes': info.notes}
    table = pd.crosstab(enriched[schema.DERIVED_FINALIDADE_CRAWLER_NORMALIZADA], enriched[schema.DERIVED_TIPO_INFORMACAO])
    table.to_csv(OUT / 'audit_purposes.csv', encoding='utf-8-sig')
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    print(table.to_string(), flush=True)
    (OUT / 'audit.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')

if __name__ == '__main__':
    audit()
