"""Consolida evidências da calibração em CSV, JSON, Markdown e gráficos."""
from pathlib import Path
import hashlib
import html
import json
import re
import numpy as np
import pandas as pd
from reportlab.graphics.shapes import Drawing, String, Rect
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics import renderSVG
from reportlab.lib import colors
from calibration_audit import OUT, ROOT
from calibrate_siri import metrics


def percent(x):
    return f'{100*x:.1f}%'.replace('.', ',')

def money(x):
    return f'{x:,.0f}'.replace(',', '.')

def md_table(frame):
    headers=list(frame.columns)
    rows=['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']
    rows += ['| '+' | '.join(str(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(rows)

def render_report_markdown(source):
    """Renderizador restrito aos elementos do relatório gerado neste módulo."""
    def inline(text):
        text=html.escape(text)
        text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
        text=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',text)
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',text)
    output=[]; paragraph=[]; table=[]; items=[]; kind=[None]
    def flush_list():
        if items:
            output.append(f'<{kind[0]}>'+''.join('<li>'+inline(item)+'</li>' for item in items)+f'</{kind[0]}>')
            items.clear(); kind[0]=None
    def flush():
        if paragraph:
            output.append('<p>'+inline(' '.join(paragraph))+'</p>'); paragraph.clear()
        if table:
            headers=table[0].strip('|').split('|')
            output.append('<table><thead><tr>'+''.join('<th>'+inline(c.strip())+'</th>' for c in headers)+'</tr></thead><tbody>')
            for line in table[2:]:
                output.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>')
            output.append('</tbody></table>'); table.clear()
        flush_list()
    for line in source.splitlines():
        if line.startswith('|'):
            if paragraph: flush()
            table.append(line)
        elif not line.strip(): flush()
        elif line.startswith('#'):
            flush(); n=len(line)-len(line.lstrip('#'))
            output.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>')
        elif line.startswith('!['):
            flush(); match=re.match(r'!\[(.*?)\]\((.*?)\)',line)
            output.append(f'<img alt="{html.escape(match[1])}" src="{html.escape(match[2])}">')
        elif re.match(r'^(?:- |\d+\. )',line):
            if paragraph or table: flush()
            new_kind='ul' if line.startswith('- ') else 'ol'
            if kind[0] and kind[0]!=new_kind: flush_list()
            kind[0]=new_kind
            items.append(re.sub(r'^(?:- |\d+\. )','',line))
        elif line.startswith('  ') and items:
            items[-1]+=' '+line.strip()
        else:
            flush_list(); paragraph.append(line)
    flush()
    return '\n'.join(output)

def main():
    results=[json.loads(path.read_text(encoding='utf-8')) for path in sorted(OUT.glob('*_mercado/result.json'))]
    if len(results)!=18:
        raise RuntimeError(f'Esperadas 18 finalidades concluídas; encontradas {len(results)}.')
    (OUT/'results_market.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    correction=json.loads((OUT/'terreno_area_negociada/result.json').read_text(encoding='utf-8'))
    summaries=[]
    strata=[]
    all_test=[]
    failures=[]
    parameters=[]
    neighbor_rows=[]
    for r in results:
        purpose=r['purpose']
        b=r['baseline']
        s=r.get('selected',b)
        evaluated=r['status']=='avaliado'
        row=dict(finalidade=purpose,n_teste=0,n_disponivel_periodo_teste=list(r['counts'].values())[-1],
                 k_min=s['min_k'],k_max=s['max_k'],
                 n_efetivo_min=s['min_effective_neighbors'],peso_fisico=s['similarity_weight'],
                 peso_geografico=1-s['similarity_weight'],piso_rs_m2=s['floor'],
                 k_min_atual=b['min_k'],k_max_atual=b['max_k'],peso_fisico_atual=b['similarity_weight'],
                 piso_atual=b['floor'],piso_fixo_validacao=r.get('fixed_validation_floor',b['floor']),
                 tipo_teste=r.get('holdout_kind',''),status='Sem amostra suficiente; manter provisoriamente')
        if evaluated:
            baseline=r['test']['baseline']; candidate=r['test'][s['config']]
            conf=r['confidence']
            row.update(n_teste=candidate['n'],mdape_atual=baseline['mdape'],mdape_candidato=candidate['mdape'],
                       cod_atual=baseline['cod'],cod_candidato=candidate['cod'],prd_atual=baseline['prd'],
                       prd_candidato=candidate['prd'],razao_mediana_atual=baseline['median_ratio'],
                       razao_mediana_candidato=candidate['median_ratio'],prb_candidato=candidate['prb'],
                       ganho_mdape=baseline['mdape']-candidate['mdape'],
                       ganho_ic95_inferior=conf.get('gain_ci95_low',0),ganho_ic95_superior=conf.get('gain_ci95_high',0))
            if s['config']=='baseline':
                row['status']='Manter: perfil atual venceu a validação'
            else:
                row['status']='Candidato exploratório; ganho não confirmado'
                # Confirmação exige melhora de precisão, dispersão e PRD, além de IC.
                sp=r['spatial']
                if conf.get('gain_ci95_low',-1)>0:
                    row['status']='Ganho de precisão; demais indicadores exigem cautela'
                if (conf.get('gain_ci95_low',-1)>0 and candidate['cod']<=baseline['cod']
                    and abs(np.log(candidate['prd']))<=abs(np.log(baseline['prd']))
                    and sp[s['config']]['mdape']<=sp['baseline']['mdape']):
                    row['status']='Ganho confirmado neste experimento'
            slug=purpose.lower()
            from estimador_knn_core_v6120 import normalize_text
            slug=normalize_text(purpose).replace(' / ','_').replace(' ','_')+r.get('output_suffix','')
            for file in ('validation_predictions.csv','test_predictions.csv','spatial_predictions.csv'):
                p=pd.read_csv(OUT/slug/file)
                failures += p.loc[p.predicted.isna(),['purpose','config','fold','row_excel','error']].to_dict('records')
                if file!='test_predictions.csv':
                    for (cid,fold),g in p.groupby(['config','fold']):
                        strata.append(dict(finalidade=purpose,config=cid,estrato='periodo_ou_espaco',grupo=fold,**metrics(g.actual,g.predicted)))
                    continue
                all_test.append(p)
                selected_predictions=p.loc[p.config.eq(s['config'])]
                neighbor_rows.append(dict(finalidade=purpose,n=len(selected_predictions),
                    k_mediano=float(selected_predictions.k.median()),
                    vizinhos_efetivos_medianos=float(selected_predictions.effective.median()),
                    casos_abaixo_meta_efetiva=int(selected_predictions.effective.lt(s['min_effective_neighbors']-1e-9).sum()),
                    falhas=int(selected_predictions.predicted.isna().sum())))
                for cid,g in p.groupby('config'):
                    g=g.copy()
                    g['decil_valor']=pd.qcut(g.actual.rank(method='first'),10,labels=False)+1
                    for field in ('decil_valor','bairro','tile'):
                        for value,part in g.groupby(field,dropna=False):
                            strata.append(dict(finalidade=purpose,config=cid,estrato=field,grupo=value,**metrics(part.actual,part.predicted)))
        summaries.append(row)
        parameters.append(dict(purpose=purpose,reference_area=r['reference_area'],status=row['status'],
                               candidate=dict(s,location_weight=1-s['similarity_weight']),
                               current=dict(b,location_weight=1-b['similarity_weight']),applied_to_runtime=False))
    summary=pd.DataFrame(summaries).sort_values('finalidade')
    summary.to_csv(OUT/'parametros_por_finalidade.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(strata).to_csv(OUT/'diagnosticos_por_estrato.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(neighbor_rows).to_csv(OUT/'vizinhos_efetivos_teste.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(failures,columns=['purpose','config','fold','row_excel','error']).to_csv(OUT/'falhas_previsao.csv',index=False)
    (OUT/'parametros_candidatos.json').write_text(json.dumps(parameters,indent=2,ensure_ascii=False),encoding='utf-8')
    decision=summary[['finalidade','status','ganho_ic95_inferior','ganho_ic95_superior','tipo_teste']].copy()
    decision.to_csv(OUT/'decisao_e_incerteza.csv',index=False,encoding='utf-8-sig')
    predictions=pd.concat(all_test,ignore_index=True)
    worst=predictions.loc[predictions.config.eq('baseline')].copy()
    worst['razao']=worst.predicted/worst.actual
    worst['erro_percentual_absoluto']=abs(worst['razao']-1)
    worst.sort_values('erro_percentual_absoluto',ascending=False).to_csv(OUT/'casos_para_revisao.csv',index=False,encoding='utf-8-sig')
    orig=pd.read_csv(OUT/'terreno/test_predictions.csv').query("config == 'baseline'")
    corrected=pd.read_csv(OUT/'terreno_area_negociada/test_predictions.csv').query("config == 'baseline'")
    paired=orig.merge(corrected,on='row_excel',suffixes=('_antes','_depois'))
    before=metrics(paired.actual_antes,paired.predicted_antes)
    after=metrics(paired.actual_depois,paired.predicted_depois)
    paired.to_csv(OUT/'terrenos_comparacao_pareada.csv',index=False,encoding='utf-8-sig')
    corr_result=dict(n_pairs=len(paired),before=before,after=after,post_hoc=True,
                     changed_source_rows=len(pd.read_csv(OUT/'land_area_corrections.csv')))
    (OUT/'land_correction_summary.json').write_text(json.dumps(corr_result,indent=2),encoding='utf-8')
    # Figura científica exportável: mesmas observações para cada par de modelos.
    plot=summary.loc[summary.n_teste.gt(0)&summary.finalidade.ne('TERRENO')].copy()
    drawing=Drawing(960,430)
    chart=HorizontalBarChart()
    chart.x=275; chart.y=75; chart.width=600; chart.height=300
    chart.data=[(plot.mdape_atual*100).tolist(),(plot.mdape_candidato*100).tolist()]
    chart.categoryAxis.categoryNames=plot.finalidade.tolist()
    chart.categoryAxis.labels.fontName='Helvetica'; chart.categoryAxis.labels.fontSize=10
    chart.valueAxis.valueMin=0
    chart.valueAxis.valueMax=max(50,float(plot[['mdape_atual','mdape_candidato']].max().max())*110)
    chart.bars[0].fillColor=colors.HexColor('#8c9eaf')
    chart.bars[1].fillColor=colors.HexColor('#167d8d')
    chart.bars.strokeColor=None
    chart.barSpacing=3; chart.groupSpacing=12
    drawing.add(chart)
    drawing.add(String(20,405,'Confirmação temporal: agosto–setembro de 2026',fontName='Helvetica-Bold',fontSize=17))
    drawing.add(String(275,48,'Erro percentual absoluto mediano no teste (%)',fontSize=11))
    drawing.add(Rect(275,20,14,10,fillColor=colors.HexColor('#8c9eaf'),strokeColor=None))
    drawing.add(String(296,20,'Perfil atual',fontSize=10))
    drawing.add(Rect(425,20,14,10,fillColor=colors.HexColor('#167d8d'),strokeColor=None))
    drawing.add(String(446,20,'Selecionado na validação',fontSize=10))
    renderSVG.drawToFile(drawing,str(OUT/'comparacao_mdape.svg'))
    display=[]
    for _,r in summary.loc[summary.n_teste.gt(0)].iterrows():
        display.append({'Finalidade':r.finalidade,'K':str(r.k_min) if r.k_min==r.k_max else f'{r.k_min}–{r.k_max}',
                        'Físico / geográfico':f'{percent(r.peso_fisico)} / {percent(r.peso_geografico)}',
                        'Piso R$/m²':money(r.piso_rs_m2),'n teste':r.n_teste,
                        'MdAPE atual → candidato':f'{percent(r.mdape_atual)} → {percent(r.mdape_candidato)}'})
    table=pd.DataFrame(display)
    metric_table=summary.loc[summary.n_teste.gt(0),['finalidade','cod_atual','cod_candidato','prd_atual','prd_candidato',
                                                   'razao_mediana_candidato']].copy()
    for col in metric_table.columns[1:]: metric_table[col]=metric_table[col].map(lambda x:f'{x:.3f}')
    metric_table.columns=['Finalidade','COD atual (%)','COD candidato (%)','PRD atual','PRD candidato','Razão mediana candidata']
    low=summary.loc[summary.n_teste.eq(0),['finalidade','k_min','k_max','peso_fisico','piso_rs_m2']]
    low=low.copy()
    low['peso_fisico']=low.peso_fisico.map(percent)
    low.columns=['Finalidade','K mínimo atual','K máximo atual','Peso físico atual','Piso atual (R$/m²)']
    nconfigs=sum(r.get('grid_count',0) for r in results)
    ntest=int(summary.n_teste.sum())
    report=f'''# Calibração SIRI — 23/09/2026

## Resultado e decisão

Foram auditadas **730.246 linhas**, com 159.120 guias ITBI e 571.126 ofertas, de 23/09/2023 a 22/09/2026.
Há 128.565 inscrições e 319.467 combinações distintas de tipo, inscrição e preço: linhas não equivalem a imóveis independentes.
A busca operacional examinou **{nconfigs} configurações por finalidade somadas**, em {int(summary.n_teste.gt(0).sum())} finalidades com amostra suficiente,
e avaliou os finalistas em **{ntest} alvos** de agosto–setembro de 2026.

**K, pesos e pisos abaixo são os candidatos selecionados na validação, não uma garantia de ótimo global.**
Nenhum parâmetro foi copiado automaticamente para o aplicativo. A decisão por finalidade está em `parametros_por_finalidade.csv`.
A correção da área dos terrenos em condomínio foi implementada no aplicativo e testada separadamente.

**Universo operacional:** conforme esclarecimento do usuário, guias abaixo dos pisos atuais não representam
o mercado a calibrar. A tabela principal usa somente alvos acima de um piso de elegibilidade FIXO por finalidade,
igual ao perfil anterior à busca. Esse piso é comum a todos os candidatos. Os pisos candidatos variam apenas
no treino. Assim, o candidato não melhora artificialmente por escolher quais alvos serão pontuados.
É uma avaliação condicionada à hipótese operacional desses pisos, não uma certificação de cada transação.
O CSV identifica quais testes usaram novos imóveis e quais reutilizaram os casos da rodada diagnóstica.

{md_table(table)}

Piso significa limite de aceitação do valor unitário ORIGINAL dos comparáveis, antes do desconto de oferta;
não é limite mínimo da estimativa. As áreas são privativas para apartamentos, coberturas, salas, vagas e lojas;
construídas para casas; área do lote/unidade para terrenos. Não transportar estes pisos para outro regime.
K em intervalo é adaptativo. O mínimo de vizinhos efetivos e os outros controles estão no JSON e no CSV.
Na configuração de K fixo, o número efetivo de vizinhos pode ser menor que K.
Piso candidato zero desativa somente esse corte absoluto: os filtros robustos global e local continuam ativos.
Uma vantagem pequena do piso zero não basta para recomendar sua adoção em outras bases.

![Comparação de erro no teste](comparacao_mdape.svg)

## Equidade e dispersão no teste

{md_table(metric_table)}

COD é expresso em porcentagem; PRD e razão mediana são adimensionais. PRD foi calculado com valores totais.
As razões elevadas nos estratos de baixo valor apontam risco de regressividade, mas não permitem atribuí-lo
integralmente ao modelo: ainda pode haver frações de direitos e inconsistências de área acima dos pisos.
A rodada bruta foi mantida nas subpastas sem sufixo. Exemplo: linha Excel 165.319 registra R$ 2,29 para uma casa;
foi excluída do universo operacional pelo piso fixo, coerentemente com a finalidade do filtro esclarecida pelo usuário.
A melhora de MdAPE, sozinha, não demonstra equidade tributária.
O arquivo `diagnosticos_por_estrato.csv` contém PRB, decis de valor, bairros, células espaciais e períodos.
Grupos pequenos são descritivos; estratificar pelo preço observado também pode produzir associação mecânica.

## Área dos terrenos em condomínio

O usuário esclareceu que é necessário usar a área da unidade negociada. O schema agora prioriza
`area_lote_negociada`, `area_terreno_unidade` ou `crawler_area_terreno` para terrenos explicitamente
identificados como condomínio. Preserva a área SIAT original, registra a regra e deixa a área efetiva
ausente quando falta área de unidade válida. Não infere condomínio por tamanho ou preço.

Foram alteradas **{corr_result['changed_source_rows']} linhas**. Na comparação pareada de **{len(paired)} guias**,
mantendo K, pesos e piso atuais, o MdAPE passou de **{percent(before['mdape'])}** para **{percent(after['mdape'])}**.
Isso é uma comparação **exploratória após diagnóstico**, não uma confirmação independente: o teste já havia sido observado.
O resultado detalhado está em `terreno_area_negociada/`, e as linhas alteradas em `land_area_corrections.csv`.
Registros rotulados apenas TERRENO ainda podem conter área fiscal coletiva; precisam de identificação cadastral.
A interpretação de `crawler_area_terreno` como área negociada nas guias é uma hipótese apoiada pelo esclarecimento
do usuário, não uma verificação documental das transações. A testada continua sendo a disponível na extração.

## Protocolo reproduzível

1. Normalização sem alvo e seleção do regime principal de área. Sem imputar preços ou usar preço como atributo.
2. Fixar elegibilidade de mercado pelo piso anterior à busca e validar períodos futuros:
   fev–jul/2025, ago/2025–jan/2026 e fev–jul/2026, sempre com treino anterior ao início.
3. Antes de qualquer filtro, deduplicação, desconto ou padronização, retirar do treino inscrições e
   assinaturas coordenadas/áreas dos alvos. Assinatura conservadora arredonda coordenadas a cinco casas e áreas a m².
4. Triagem aproximada: até 6.000 linhas de treino e 24 alvos por período; omite filtro local para reduzir custo.
   Grade: K fixos 5, 8, 12, 16, 24, 32 e 48; faixas 5–15, 8–24, 12–36 e 16–48;
   faixa atual; pesos físicos 10%, 25%, 45%, 60%, 75%, 90% e o atual;
   pisos zero, metade, atual, 1,5× e 2× o atual. Peso geográfico é 1 menos peso físico.
5. Reavaliar dois melhores da triagem, melhor de cada piso e perfil atual com **núcleo completo**,
   todo treino elegível e até 90 alvos por período. A triagem não avalia exaustivamente toda a grade com o núcleo completo.
6. Critério definido no script antes da busca: erro logarítmico absoluto médio + 0,25×COD/100
   + 0,5×|ln(razão mediana)| + 0,5×|ln(PRD)|, com penalização de instabilidade entre períodos e falhas.
   É um critério de trabalho, não um índice normativo. Preços anômalos podem dominar o componente COD.
7. Congelar seleção em `locked_selection.json`, antes do teste de 01/08/2026 a 22/09/2026.
   Até 350 guias por finalidade; alvo nunca excluído pelo piso CANDIDATO ou por outlier estatístico de preço.
   Quando restaram pelo menos 50 alvos válidos ainda não avaliados na rodada bruta, usar somente esses novos alvos.
   Caso contrário, registrar reutilização do teste condicionado ao piso fixo. A configuração territorial já usa área corrigida.
8. Teste espacial de até 60 alvos, retirando a célula de aproximadamente 1 km do treino e refazendo a preparação.
   Células usam latitude/longitude com aproximação local, sem faixa de isolamento nas bordas.
9. IC de 95% do ganho de MdAPE por 1.000 reamostragens pareadas de células espaciais. Semente: 23092026.
   IC que inclui zero não comprova ganho. Não mede a incerteza de toda a busca nem corrige seleção múltipla.

As coordenadas são interpretadas como EPSG:4326. Alvos restringem-se à janela -31 a -29 de latitude e -52 a -50
de longitude, coerente com a área de Porto Alegre. A distância usa aproximação equiretangular em km.
Distância física usa atributos de área e ano quando disponível; casas incluem também área do terreno.
As escalas robustas (IQR/MAD) são calculadas apenas nos candidatos de treino. A escala geográfica é a mediana
das distâncias do treino ao alvo, limitada a 0,25–20 km. O filtro local mantém os raios do aplicativo (5/10 km).
Mudar o peso físico não representa a mesma troca em metros; os componentes são padronizados.

## Finalidades sem sustentação para ajuste específico

Estas categorias não atingiram 90 alvos nos períodos de validação e 30 no teste final.
Os números abaixo são **parâmetros atuais preservados, não parâmetros otimizados**.

{md_table(low)}

## Limitações e próximos controles

- 47.654 linhas sem finalidade normalizável não entraram na busca por finalidade.
- Nenhuma linha veio rotulada como aluguel. Existem 33 ofertas com valor total até R$ 10 mil;
  a classificação merece revisão, sem presumir que todas sejam locações.
- `data_encaminhamento` é data de disponibilidade cadastral, não data comprovada de negócio ou avaliação.
  Valores nominais dos três anos foram mantidos; não houve correção monetária presumida.
- A extração atual pode incorporar revisões cadastrais posteriores. Sem snapshots históricos,
  não é possível excluir inteiramente esse tipo de informação retrospectiva.
- Piso e corte de cauda podem remover submercados baratos legítimos e aumentar regressividade.
  O universo principal assume válidos os pisos atuais para identificar mercado; sua validade exige auditoria cadastral.
  Só o piso do treino varia na busca. A avaliação bruta anterior fica preservada para rastreabilidade.
- O preditor é média winsorizada em escala original; log é usado em filtros e no critério de seleção,
  não há retransfomação de uma previsão logarítmica nem necessidade automática de smearing.
- Amostra limitada, dependência espacial e busca extensa criam risco de overfitting.
  Não houve otimização da potência de distância, limite individual, MAD, raios ou correção temporal.
- Resultados referem-se ao regime principal e à configuração de atributos descrita; não validam automaticamente
  estimativas sem ano, sem localização ou com regime alternativo de área.
- As razões são em relação a valores declarados de ITBI, não comprovação de valor de mercado ou conformidade tributária.

## Arquivos e verificação

- `parametros_por_finalidade.csv`: comparação completa e decisão operacional.
- `parametros_candidatos.json`: configurações propostas, preservando parâmetros não pesquisados.
- `decisao_e_incerteza.csv`: situação de cada candidato e intervalo do ganho de erro mediano.
- `baseline_parameters.json`: fotografia das configurações do aplicativo antes da análise.
- `diagnosticos_por_estrato.csv`: métricas de equidade, tempo, localização e valor.
- `casos_para_revisao.csv`: casos do teste ordenados por erro, com linha Excel para rastreamento.
- `cobertura_universo_operacional.csv`: quantos imóveis passam pelos requisitos e pelo piso fixo.
- `vizinhos_efetivos_teste.csv`: K realizado, tamanho efetivo e frequência de meta não atingida.
- Subpastas: grade de triagem, ranking de validação, seleção congelada e previsões individuais.
- `provenance.json`: SHA-256 da fonte e dos módulos originais.
- Scripts `calibration_audit.py`, `calibrate_siri.py`, `calibration_report.py`: reprodução local.
  Rodar `python calibration_audit.py`, `python calibrate_siri.py --workers 3`,
  `python calibrate_siri.py --corrected-land`, `python calibrate_siri.py --market --workers 3`
  e `python calibration_report.py`.
  O cache `enriched.pkl` preserva o schema original desta rodada. Removê-lo após modificar o schema muda o experimento.

Referências metodológicas: [IAAO, Standard on Ratio Studies (2013)](https://www.iaao.org/wp-content/uploads/Standard_on_Ratio_Studies.pdf)
para COD/PRD/PRB, e [scikit-learn, prevenção de vazamento](https://github.com/scikit-learn/scikit-learn/blob/main/doc/common_pitfalls.rst)
para separação antes da preparação. Nenhum limite normativo de aprovação foi atribuído a estes resultados.
'''
    (OUT/'RELATORIO.md').write_text(report,encoding='utf-8')
    # Relatório de leitura local; sem enviar dados a serviços externos.
    body=render_report_markdown(report)
    page='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Calibração SIRI</title>
    <style>body{max-width:1180px;margin:40px auto;padding:0 28px;font:16px/1.55 system-ui;color:#182b3a}
    h1{font-size:32px}h2{margin-top:36px;color:#116b7a}table{width:100%;border-collapse:collapse;font-size:13px}
    th,td{text-align:left;padding:9px;border-bottom:1px solid #dae2e8}th{background:#eef4f6}
    tr:nth-child(even){background:#fafcfd}img{max-width:100%}code{background:#eef4f6;padding:2px 4px}
    a{color:#086f83}@media print{body{font-size:11px;margin:0}h2{break-after:avoid}tr{break-inside:avoid}}</style>'''+body+'</html>'
    (OUT/'RELATORIO.html').write_text(page,encoding='utf-8')
    print(summary.to_string(index=False))
    print(json.dumps(corr_result,indent=2))

if __name__=='__main__':
    main()
