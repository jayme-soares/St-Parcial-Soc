import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import html as html_lib
import os
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Parcial SOC - Maricá | Ceneged", page_icon="📊", layout="wide")

# Paleta de cores baseada no seu print
CORES_PRODUCAO = {"Produtivo": "#005b96", "Improdutivo": "#d9534f", "Contato Gestor": "#5cb85c"}
CORES_SETOR = {"Corte": "#d9534f", "Religa": "#005b96", "Novas": "#5bc0de", "Pré Venda": "#5bc0de", "Aferição": "#00008b", "Vistoria": "#f0ad4e"}

def obter_url_drive(chave: str) -> str | None:
    return os.getenv(chave) or st.secrets.get(chave)

def validar_config_drive(url_base: str | None, url_suporte: str | None) -> None:
    faltando = []
    if not url_base:
        faltando.append("DRIVE_URL_BASE")
    if not url_suporte:
        faltando.append("DRIVE_URL_SUPORTE")
    if faltando:
        st.error(
            "Configuração do Drive ausente. Defina as variáveis de ambiente "
            f"{', '.join(faltando)} localmente ou em st.secrets no Streamlit Cloud."
        )
        st.stop()

# Alturas padrão para reduzir o tamanho dos gráficos
ALTURA_GRAFICO_P = 200
ALTURA_GRAFICO_M = 260

def estilo_tabela(df: pd.DataFrame, destacar_total: bool = False):
    azul_cabecalho = "#0b5ea8"
    azul_claro = "#e9f2ff"
    styler = df.style
    if hasattr(styler, "hide"):
        styler = styler.hide(axis="index")
    else:
        styler = styler.hide_index()
    styler = styler.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", azul_cabecalho),
                    ("color", "white"),
                    ("font-weight", "bold"),
                    ("text-align", "left"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("border", "1px solid #d6e4f0"),
                ],
            },
        ]
    )

    def zebra_linhas(linha):
        cor = azul_claro if linha.name % 2 == 0 else "white"
        return [f"background-color: {cor}"] * len(linha)

    styler = styler.apply(zebra_linhas, axis=1)

    if destacar_total and "Setor" in df.columns:
        def destacar_linha_total(linha):
            if str(linha.get("Setor", "")) == "Total":
                return ["background-color: #0b5ea8; color: white; font-weight: bold"] * len(linha)
            return [""] * len(linha)

        styler = styler.apply(destacar_linha_total, axis=1)

    return styler

def altura_tabela(
    df: pd.DataFrame,
    altura_min: int = 240,
    altura_max: int = 800,
    altura_linha: int = 32,
    altura_cabecalho: int = 40,
    padding_extra: int = 12,
) -> int:
    linhas = len(df)
    if linhas <= 0:
        return altura_min
    altura = altura_cabecalho + (linhas * altura_linha) + padding_extra
    return max(altura_min, min(altura, altura_max))

def altura_tabela_setor_equipes(
    df: pd.DataFrame,
    altura_min: int = 360,
    altura_max: int = 820,
    altura_linha: int = 30,
    altura_cabecalho: int = 40,
    padding_extra: int = 16,
) -> int:
    if df.empty:
        return altura_min
    linhas = len(df) + df['Setor'].nunique()
    altura = altura_cabecalho + (linhas * altura_linha) + padding_extra
    return max(altura_min, min(altura, altura_max))

def render_tabela(df: pd.DataFrame, altura: int, destacar_total: bool = False) -> None:
    styler = estilo_tabela(df, destacar_total=destacar_total)
    styler = styler.set_table_attributes('style="width:100%; border-collapse: collapse;"')
    html = styler.to_html()
    st.markdown(
        f"<div style='height:{altura}px; overflow-y:auto; border:1px solid #d6e4f0; border-radius:4px;'>"
        f"{html}"
        "</div>",
        unsafe_allow_html=True,
    )

def render_tabela_setor_equipes(df: pd.DataFrame, altura: int) -> None:
    df_local = df.copy()
    for coluna in ["Produtivo", "Improdutivo"]:
        if coluna not in df_local.columns:
            df_local[coluna] = 0
    df_local["Setor"] = df_local["Setor"].fillna("Não Classificado")
    df_local["Equipe"] = df_local["Equipe"].fillna("Sem Equipe")
    df_local["Produtivo"] = df_local["Produtivo"].fillna(0).astype(int)
    df_local["Improdutivo"] = df_local["Improdutivo"].fillna(0).astype(int)
    df_local = df_local[["Setor", "Equipe", "Produtivo", "Improdutivo"]].sort_values(["Setor", "Equipe"])

    th_style = "background-color:#0b5ea8;color:#ffffff;font-weight:bold;text-align:left;padding:4px 6px;border:1px solid #0b5ea8;"
    td_style = "border:1px solid #d6e4f0;padding:4px 6px;"
    rows = []
    zebra = False

    for setor, grupo in df_local.groupby("Setor"):
        setor_nome = html_lib.escape(str(setor))
        rows.append(
            "<tr style='background-color:#0b5ea8;color:#ffffff;font-weight:bold;'>"
            f"<td colspan='3' style='padding:4px 6px;border:1px solid #0b5ea8;'>{setor_nome}</td>"
            "</tr>"
        )
        for _, linha in grupo.iterrows():
            zebra = not zebra
            bg = "#e9f2ff" if zebra else "white"
            equipe = html_lib.escape(str(linha["Equipe"]))
            prod = int(linha["Produtivo"])
            improd = int(linha["Improdutivo"])
            rows.append(
                f"<tr style='background-color:{bg};'>"
                f"<td style='{td_style}'>{equipe}</td>"
                f"<td style='{td_style} text-align:right;'>{prod}</td>"
                f"<td style='{td_style} text-align:right;'>{improd}</td>"
                "</tr>"
            )

    if not rows:
        rows.append(
            "<tr><td colspan='3' style='padding:6px; text-align:center;'>Sem dados</td></tr>"
        )

    tabela_html = (
        f"<div style='height:{altura}px; overflow-y:auto; border:1px solid #d6e4f0; border-radius:4px;'>"
        "<table style='width:100%; border-collapse: collapse; font-size:0.9rem;'>"
        "<thead><tr>"
        f"<th style='{th_style}'>Setor</th>"
        f"<th style='{th_style} text-align:right;'>Produtivo</th>"
        f"<th style='{th_style} text-align:right;'>Improdutivo</th>"
        "</tr></thead>"
        "<tbody>"
        f"{''.join(rows)}"
        "</tbody></table></div>"
    )
    st.markdown(tabela_html, unsafe_allow_html=True)

# 2. FUNÇÃO DE LEITURA E TRATAMENTO (Com Cache para velocidade)
@st.cache_data(ttl=300) # O cache dura 5 min. O botão de atualizar força a limpeza.
def carregar_dados():
    # Lendo as abas do Excel
    df_linhas = pd.read_excel(URL_BASE, sheet_name="Linhas TdC")
    df_ciclos = pd.read_excel(URL_SUPORTE, sheet_name="Ciclos")
    
    # === TRATAMENTOS DA TABELA 'Linhas TdC' (Tradução do M para Python) ===
    # Coluna Condicional: ResultadoProducao
    cond_res = [
        df_linhas['Nota Codificada'].astype(str).str.contains("CONTATO TEL GESTOR", case=False, na=False),
        df_linhas['Resultado'] == "Realizado"
    ]
    escolhas_res = ["Contato Gestor", "Produtivo"]
    df_linhas['ResultadoProducao'] = np.select(cond_res, default="Improdutivo", choicelist=escolhas_res)

    # Coluna Condicional: TramiteExec
    cond_tram = [
        df_linhas['Causa/Descritivo Resultado'].astype(str).str.contains("MEDIDOR", case=False, na=False),
        df_linhas['Causa/Descritivo Resultado'].astype(str).str.contains("POSTE", case=False, na=False),
        df_linhas['Causa/Descritivo Resultado'].astype(str).str.contains("RAMAL", case=False, na=False)
    ]
    escolhas_tram = ["EXECUTADO MEDIDOR", "EXECUTADO POSTE", "EXECUTADO RAMAL"]
    df_linhas['TramiteExec'] = np.select(cond_tram, default="Não Executado", choicelist=escolhas_tram)
    
    # Relacionamento (Mesclagem) com a tabela Ciclos para buscar o "Setor"
    df_linhas = df_linhas.merge(df_ciclos[['Tipo Operação', 'Setor']], on='Tipo Operação', how='left')
    
    # Preencher setores vazios para evitar erro nos filtros
    df_linhas['Setor'] = df_linhas['Setor'].fillna("Não Classificado")
    df_linhas['Equipe'] = df_linhas['Equipe'].fillna("Sem Equipe")

    return df_linhas

@st.cache_data(ttl=300)
def buscar_data_atualizacao(url_arquivo: str):
    requisicao = Request(url_arquivo, method="HEAD")
    with urlopen(requisicao, timeout=10) as resposta:
        last_modified = resposta.headers.get("Last-Modified")
    if not last_modified:
        return None
    data_modificacao = parsedate_to_datetime(last_modified)
    
    # Força a conversão sempre para o fuso horário de Brasília/RJ (UTC-3)
    fuso_br = ZoneInfo("America/Sao_Paulo")
    return data_modificacao.astimezone(fuso_br)

# 3. INTERFACE E BOTÃO DE REFRESH
URL_BASE = obter_url_drive("DRIVE_URL_BASE")
URL_SUPORTE = obter_url_drive("DRIVE_URL_SUPORTE")
validar_config_drive(URL_BASE, URL_SUPORTE)
data_atualizacao = buscar_data_atualizacao(URL_BASE)

col_header1, col_header2, col_header3 = st.columns([1, 7, 2])
with col_header1:
    # Se quiser, coloque a logo da Ceneged aqui: 
    st.image("logo.png", width=100)
    # st.markdown("### ⚡ Ceneged")
with col_header2:
    st.title("Parcial SOC - Maricá")
with col_header3:
    if data_atualizacao:
        st.markdown(
            f"<div style='text-align:right; font-size:0.9rem;'>"
            f"<strong>Última atualização</strong><br>{data_atualizacao:%d/%m/%Y %H:%M}"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='text-align:right; font-size:0.9rem;'>"
            "<strong>Última atualização</strong><br>Indisponível"
            "</div>",
            unsafe_allow_html=True,
        )

# Botão para forçar a busca de novos dados do Drive
if st.button("🔄 Recarregar Dados do Drive"):
    st.cache_data.clear() # Limpa a memória e vai no Drive buscar a planilha nova
    st.rerun()

# Carregamento dos dados
with st.spinner("Conectando ao Google Drive e montando o painel..."):
    df = carregar_dados()

# 4. FILTROS LATERAIS (Slicers)
with st.sidebar:
    st.header("Filtros")
    
    # Filtro de Setor
    setores = sorted(df['Setor'].unique())
    setor_selecionado = st.multiselect("Setor", options=setores, default=setores)
    
    # Filtro de ResultadoProducao
    resultados = df['ResultadoProducao'].unique()
    resultado_selecionado = st.multiselect("Resultado", options=resultados, default=resultados)
    
    # Filtro de Equipe
    equipes = ["Todas"] + sorted(df['Equipe'].unique().tolist())
    equipe_selecionada = st.selectbox("Equipe", options=equipes)

# Aplicar filtros no Dataframe
df_filtrado = df[
    (df['Setor'].isin(setor_selecionado)) & 
    (df['ResultadoProducao'].isin(resultado_selecionado))
]
if equipe_selecionada != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Equipe'] == equipe_selecionada]

# 5. CARDS SUPERIORES (Métricas)
total_ordens = len(df_filtrado)
qtde_produtivo = len(df_filtrado[df_filtrado['ResultadoProducao'] == 'Produtivo'])
qtde_improdutivo = len(df_filtrado[df_filtrado['ResultadoProducao'] == 'Improdutivo'])

m1, m2, m3, m4 = st.columns(4)
m2.metric("Total de Ordens", total_ordens)
m3.metric("Qtde Produtivo", qtde_produtivo)
m4.metric("Qtde Improdutivo", qtde_improdutivo)

st.markdown("---")

# 6. VISUAIS (Gráficos) - Layout inspirado no print
col_esq, col_dir = st.columns([1.05, 1.65], gap="large")

with col_esq:
    st.markdown("**Produção Geral**", unsafe_allow_html=True)
    fig_prod_geral = px.pie(
        df_filtrado,
        names='ResultadoProducao',
        hole=0.6,
        color='ResultadoProducao',
        color_discrete_map=CORES_PRODUCAO,
    )
    fig_prod_geral.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        showlegend=False,
        height=ALTURA_GRAFICO_P,
    )
    st.plotly_chart(fig_prod_geral, use_container_width=True)

    st.markdown("**Qtde Visitação x Setor**")
    fig_vis_setor = px.pie(
        df_filtrado,
        names='Setor',
        hole=0.6,
        color='Setor',
        color_discrete_map=CORES_SETOR,
    )
    fig_vis_setor.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=ALTURA_GRAFICO_P)
    st.plotly_chart(fig_vis_setor, use_container_width=True)

    st.markdown("**Trâmite - Executado**")
    df_tramite = df_filtrado[df_filtrado['TramiteExec'] != "Não Executado"]
    df_group_tramite = df_tramite.groupby('TramiteExec').size().reset_index(name='Quantidade')
    fig_tramite = px.bar(df_group_tramite, x='TramiteExec', y='Quantidade', text='Quantidade')
    fig_tramite.update_traces(marker_color='#005b96')
    fig_tramite.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        xaxis_title=None,
        yaxis_title=None,
        height=ALTURA_GRAFICO_P,
    )
    st.plotly_chart(fig_tramite, use_container_width=True)

    st.markdown("**Top 10 Equipes (Produtivo)**")
    df_top_equipes = df_filtrado[df_filtrado['ResultadoProducao'] == 'Produtivo']
    top_10 = df_top_equipes['Equipe'].value_counts().nlargest(10).reset_index()
    top_10.columns = ['Equipe', 'Quantidade']
    fig_funnel = px.funnel(top_10, y='Equipe', x='Quantidade')
    escala_cores = px.colors.sample_colorscale(
        "Purples",
        np.linspace(0.85, 0.25, len(top_10)),
    )
    fig_funnel.update_traces(
        marker=dict(color=escala_cores),
        selector=dict(type="funnel"),
    )
    fig_funnel.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=ALTURA_GRAFICO_M)
    st.plotly_chart(fig_funnel, use_container_width=True)

with col_dir:
    st.markdown("**Produção x Setor**")
    df_group_setor = df_filtrado.groupby(['Setor', 'ResultadoProducao']).size().reset_index(name='Quantidade')
    fig_prod_setor = px.bar(
        df_group_setor,
        x='Setor',
        y='Quantidade',
        color='ResultadoProducao',
        barmode='group',
        color_discrete_map=CORES_PRODUCAO,
        text='Quantidade',
    )
    fig_prod_setor.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=True,
        height=ALTURA_GRAFICO_M,
    )
    st.plotly_chart(fig_prod_setor, use_container_width=True)

    st.markdown("**Quantitativo por Setor**")
    df_quantitativo = (
        df_filtrado.groupby(['Setor', 'ResultadoProducao'])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for coluna in ["Produtivo", "Improdutivo", "Contato Gestor"]:
        if coluna not in df_quantitativo.columns:
            df_quantitativo[coluna] = 0
    df_quantitativo = df_quantitativo[['Setor', 'Produtivo', 'Improdutivo', 'Contato Gestor']]
    df_total = pd.DataFrame([{
        'Setor': 'Total',
        'Produtivo': int(df_quantitativo['Produtivo'].sum()),
        'Improdutivo': int(df_quantitativo['Improdutivo'].sum()),
        'Contato Gestor': int(df_quantitativo['Contato Gestor'].sum()),
    }])
    df_quantitativo = pd.concat([df_quantitativo, df_total], ignore_index=True)
    render_tabela(
        df_quantitativo,
        altura_tabela(df_quantitativo, altura_min=300, altura_max=420),
        destacar_total=True,
    )

    st.markdown("**Detalhamento de Produção por Setor e Equipe**")
    df_matriz = df_filtrado.pivot_table(
        index=['Setor', 'Equipe'],
        columns='ResultadoProducao',
        values='Código TdC',
        aggfunc='count',
        fill_value=0,
    ).reset_index()
    render_tabela_setor_equipes(
        df_matriz,
        altura_tabela_setor_equipes(df_matriz, altura_min=1750, altura_max=2000),
    )