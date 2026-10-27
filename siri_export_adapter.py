"""Adapta exportações camelCase do SIRI sem modificar suas colunas originais."""
from __future__ import annotations

import numpy as np
import pandas as pd


def adapt_siri_export(data: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Acrescenta aliases de compatibilidade; recebe a cópia feita pelo schema."""
    lookup = {str(c).strip().casefold(): c for c in data.columns}
    if not ("fontetransacao" in lookup
            and any(c in lookup for c in ("valorofertapmi", "valorofertacrawler", "valorguiatotaldeclarado"))
            and any(c in lookup for c in ("finalidadenmesiat", "finalidadenmepmi", "finalidadenmecrawlersiri"))):
        return [], []
    added = []

    def raw(name):
        column = lookup.get(name.casefold())
        return data[column] if column is not None else pd.Series(pd.NA, index=data.index)

    def text(name):
        return raw(name).astype("string").fillna("").str.strip()

    def numeric(name):
        values = raw(name)
        if pd.api.types.is_numeric_dtype(values):
            return pd.to_numeric(values, errors="coerce").astype("float64")
        cleaned = values.astype("string").str.strip().str.replace(r"[Rr]\$|\s", "", regex=True)
        comma = cleaned.str.contains(",", regex=False, na=False)
        cleaned.loc[comma] = cleaned.loc[comma].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        return pd.to_numeric(cleaned, errors="coerce").astype("float64")

    def positive(*names):
        result = pd.Series(np.nan, index=data.index, dtype=float)
        for name in names:
            values = numeric(name)
            result = result.fillna(values.where(np.isfinite(values) & values.gt(0)))
        return result

    def strings(*names):
        result = pd.Series(pd.NA, index=data.index, dtype="object")
        for name in names:
            values = raw(name)
            valid = text(name).ne("")
            result = result.where(result.notna(), values.where(valid))
        return result

    def add(name, values):
        # Cabeçalhos canônicos fornecidos explicitamente continuam prioritários.
        if name not in data.columns:
            data[name] = values
            added.append(name)

    guia = text("fonteTransacao").str.casefold().eq("guia itbi")
    add("tipo_informacao", raw("fonteTransacao"))
    add("siat_finalidade_descricao", strings("finalidadeNmeSiat", "finalidadeNmePmi"))
    add("crawler_tipo_imovel_normalizado", raw("finalidadeNmeCrawlerSiri"))
    add("pmi_finalidade_descricao", raw("finalidadeNmePmi"))
    for source, alias in {
        "numInscricao": "siat_inscricao", "numGuia": "numero_guia",
        "numRegistroPmi": "idf_registro", "numRegistroCrawler": "crawler_id_registro",
        "dataRegistroPmi": "data_registro", "numLoteFiscalSiat": "siat_lote_fiscal",
        "numLoteFiscalPmi": "pmi_lote_fiscal",
    }.items():
        add(alias, raw(source))
    add("data_encaminhamento", strings("dataEncaminhaCrawler", "dataEncaminhaPmi"))
    add("url_anuncio", raw("urlAnuncioCrawler"))
    crawler_id = text("numRegistroCrawler")
    add("id_anuncio", ("crawler:" + crawler_id).where(~crawler_id.isin({"", "0", "0.0"}), ""))

    price = positive("valorOfertaCrawler", "valorOfertaPmi")
    # Regra escolhida pelo usuário: guia usa somente o declarado, nunca o atribuído.
    price.loc[guia] = positive("valorGuiaTotalDeclarado").loc[guia]
    add("valor_oferta", price)
    price_source = pd.Series("valorOfertaPmi", index=data.index, dtype="string")
    price_source.loc[positive("valorOfertaCrawler").notna()] = "valorOfertaCrawler"
    price_source.loc[guia] = "valorGuiaTotalDeclarado"
    price_source.loc[price.isna()] = "valor ausente ou inválido"
    add("__fonte_valor_exportacao", price_source)

    private_land = positive("areaTerrPrivPmi", "areaTerrPrivSiat")
    land = private_land.fillna(positive("areaTerrLoteFiscalPmi", "areaTerrLoteFiscalSiat"))
    descriptions = (text("finalidadeNmeCrawlerSiri") + " " + text("finalidadeNmePmi")
                    + " " + text("finalidadeNmeSiat"))
    condominium = descriptions.str.casefold().str.contains("condom", regex=False)
    land.loc[condominium] = private_land.loc[condominium]
    # Regra escolhida pelo usuário: área transmitida, inclusive nas frações de guias.
    transmitted_land = positive("guiaAreaTerrTransmitida")
    add("crawler_area_terreno", land.where(~guia))
    add("siat_area_terreno", land.where(~guia, transmitted_land))
    add("area_lote_negociada", private_land.where(~guia, transmitted_land))
    add("siat_area_total_lote", positive("areaTerrLoteFiscalSiat", "areaTerrLoteFiscalPmi"))
    area_source = pd.Series("área privativa; na ausência, lote fiscal fora de condomínio",
                            index=data.index, dtype="string")
    area_source.loc[guia] = "guiaAreaTerrTransmitida; sem substituição pelo lote fiscal"
    area_source.loc[~guia & condominium] = "área privativa da unidade em condomínio"
    add("__regra_area_exportacao", area_source)
    add("crawler_area_construida", positive("acoTotalCrawler", "acoTotalPmi"))
    add("siat_area_construida", positive("acoTotalSiat"))
    add("itbacotot", positive("guiaAcoTransmitida"))
    add("crawler_area_privativa", positive("acoPrivativaCrawler", "acoPrivativaPmi"))
    add("anuncio_testada", positive("testadaPrincipalLoteFiscalPmi", "testadaPrincipalLoteFiscalSiat"))
    add("siat_testada_terreno", positive("testadaPrincipalLoteFiscalSiat", "testadaPrincipalLoteFiscalPmi"))

    latitude = pd.Series(np.nan, index=data.index)
    longitude = pd.Series(np.nan, index=data.index)
    origin = pd.Series("sem par válido", index=data.index, dtype="string")
    # Latitude e longitude vêm sempre do mesmo par, nunca de fontes misturadas.
    for source in ("Crawler", "Pmi"):
        lat = pd.to_numeric(text("endLatitude" + source).str.replace(",", ".", regex=False), errors="coerce").astype("float64")
        lon = pd.to_numeric(text("endLongitude" + source).str.replace(",", ".", regex=False), errors="coerce").astype("float64")
        valid = latitude.isna() & lat.between(-90, 90) & lon.between(-180, 180) & ~(lat.eq(0) & lon.eq(0))
        latitude.loc[valid], longitude.loc[valid] = lat.loc[valid], lon.loc[valid]
        origin.loc[valid] = source
    add("latitude", latitude)
    add("longitude", longitude)
    add("__origem_coordenadas_exportacao", origin)

    # Seleciona logradouro/número/bairro juntos; não completa o número de outra fonte.
    chosen = pd.Series(False, index=data.index)
    address = {k: pd.Series(pd.NA, index=data.index, dtype="object")
               for k in ("logradouro", "numero", "bairro", "cidade", "cep")}
    for source, eligible in (("Pmi", guia), ("Crawler", ~guia), ("Pmi", ~guia), ("Siat", ~chosen)):
        street = "endLogradouroNme" + source
        take = ~chosen & eligible & text(street).ne("")
        for alias, field in {
            "logradouro": street,
            "numero": "crawlerNumero" if source == "Crawler" else "endLogradouroNum" + source,
            "bairro": "endBairroNme" + source,
            "cidade": "endCidade" + source,
            "cep": "endCep" + source,
        }.items():
            address[alias].loc[take] = raw(field).loc[take]
        chosen |= take
    for alias, values in address.items():
        add(alias, values)

    partial = guia & numeric("guiaPercentualGlobalTransmitido").lt(100)
    notes = [
        "Exportação camelCase do SIRI reconhecida; colunas originais preservadas.",
        "Guias ITBI: valorGuiaTotalDeclarado e guiaAreaTerrTransmitida; sem fallback para valor atribuído ou área fiscal total.",
        "Ofertas: valorOfertaCrawler, depois valorOfertaPmi. Coordenadas: par Crawler válido, depois par PMI válido.",
        "Datas de encaminhamento/registro são disponibilidade cadastral, não data do negócio ou ano da construção.",
        f"Guias com percentual transmitido inferior a 100%: {int(partial.sum())}; revisar direitos transmitidos e comparabilidade.",
        "Campos sem uso no KNN permanecem como metadados; campos ausentes não são inventados.",
    ]
    return added, notes
