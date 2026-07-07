import streamlit as st
# from streamlit.errors import StreamlitSecretNotFoundError
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import html as html_lib
import os
import re
import unicodedata
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Parcial SOC - Maricá | Ceneged", page_icon="📊", layout="wide")

# Paleta de cores baseada no seu print
CORES_PRODUCAO = {"Produtivo": "#005b96", "Improdutivo": "#d9534f", "Contato Gestor": "#5cb85c"}
CORES_SETOR = {"Corte": "#d9534f", "Religa": "#005b96", "Novas": "#5bc0de", "Pré Venda": "#5bc0de", "Aferição": "#00008b", "Vistoria": "#f0ad4e"}

st.markdown(
    """
    <style>
    .indicador-card {
        border: 1px solid #d6e4f0;
        border-radius: 10px;
        background: #f8fbff;
        padding: 12px 14px;
    }
    .indicador-titulo {
        font-size: 0.86rem;
        color: #5b6b7c;
        margin-bottom: 2px;
    }
    .indicador-valor {
        font-size: 1.55rem;
        font-weight: 700;
        color: #0b5ea8;
        line-height: 1.2;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Dicionários de referência (edite aqui quando precisar ajustar os mapeamentos)
MAPA_TRAMITE_EXEC = {
    "SR0002 - CORTE NO MEDIDOR": "Medidor",
    "SR0001 - CORTE NO POSTE": "Poste",
    "SR0032-CORTE MEDIDOR - MED AGRUPADA": "Medidor",
    "SR0018 - CORTE COM RETIRADA DE RAMAL": "Ramal",
    "SR0020 - CORTE COM RETIRADA DE MEDIDOR": "Medidor",
    "SR0019 - CORTE C/ RETIRADA MEDIDOR E RAMAL": "Ramal",
    "CORTE NO MEDIDOR-POSTE MADEIRA": "Medidor",
    "SR0026 - RETIRADA DE GAMBIARRA": "Medidor",
    "SR0040 - CORTE POSTE DAT": "Poste",
    "SR0011 - CORTE NO RAMAL DAT": "Ramal",
    "SR0062 - CORTE MEDIDOR REDE D": "Medidor",
    "SR0027 - RETIRO DE GAMB C/INST DE DISP": "Medidor",
    "SR0061 - CORTE MEDIDOR REDE M": "Medidor",
    "SR0087 - CORTE DISJ C/ INST DE DISP": "Medidor",
    "SR0017 - CORTE NO DISJUNTOR": "Medidor",
    "SR0060-CORTE POSTE PODAO": "Poste",
}

MAPA_CLASSIF_CORTE = {
    "CICLO 1 - DESLIGAMENTO A PEDIDO RET MEDIDOR E RAMAL AEREA": "Massivo",
    "CICLO 1.1 - DESLIGAMENTO A PEDIDO RET MEDIDOR E RAMAL DAT": "Massivo",
    "CICLO 15 - CORTE PRIORIDADE 1 - MEDIDOR": "Massivo",
    "CICLO 16 - CORTE PRIORIDADE 2 - MEDIDOR": "Massivo",
    "CICLO 17 - CORTE PRIORIDADE 3 - MEDIDOR": "Massivo",
    "CICLO 2 - RECORTE - AEREA": "Massivo",
    "CICLO 2.1 - RECORTE - DAT": "Massivo",
    "CICLO 2.2 - RECORTE - MEDIDOR": "Massivo",
    "CICLO 22 - CORTE - PRIORIDADE 1 - POSTE AEREA": "Massivo",
    "CICLO 23 - CORTE - PRIORIDADE 2 - POSTE AEREA": "Massivo",
    "CICLO 24 - CORTE - PRIORIDADE 3 - POSTE AEREA": "Massivo",
    "CICLO 29 - CORTE - PRIORIDADE 1 - POSTE DAT": "Massivo",
    "CICLO 3 - CORTE - MASSIVO MEDIDOR": "Perdas",
    "CICLO 3.1 - CORTE - MASSIVO POSTE AEREA": "Massivo",
    "CICLO 3.2 - CORTE - MASSIVO POSTE DAT": "Massivo",
    "CICLO 30 - CORTE - PRIORIDADE 2 - POSTE DAT": "Massivo",
    "CICLO 36 - CORTE - PRIORIDADE 1 - RETIRADA DE RAMAL AEREA": "Massivo",
    "CICLO 37 - CORTE - PRIORIDADE 2 - RETIRADA DE RAMAL AEREA": "Massivo",
    "CICLO 43 - CORTE - PRIORIDADE 1 - RETIRADA DE RAMAL DAT": "Massivo",
    "CICLO 44 - CORTE - PRIORIDADE 2 - RETIRADA DE RAMAL DAT": "Massivo",
    "CICLO 5 - FISCALIZACAO": "Perdas",
    "CICLO 5.1 - FISCALIZACAO DAT": "Perdas",
    "CICLO 51 - CORTE - PRIORIDADE 1 SENTINELA MI": "Massivo",
    "CICLO 52 - CORTE - PRIORIDADE 2 SENTINELA MI": "Massivo",
    "CICLO 53 - CORTE - PRIORIDADE 3 SENTINELA MI": "Massivo",
    "CICLO 6 - SEM CONTRATO": "Perdas",
    "CICLO 6.1 - SEM CONTRATO DAT": "Perdas",
}

def obter_url_drive(chave: str) -> str | None:
    valor_env = os.getenv(chave)
    if valor_env:
        return valor_env
    else:
        return st.secrets.get(chave)
    

def normalizar_chave_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"[^A-Z0-9\s\-\/\.]", "", texto.upper())
    return " ".join(texto.strip().split())

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
                    ("text-align", "center"),
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
    altura_min: int = 280,
    altura_max: int = 800,
    altura_linha: int = 15,
    altura_cabecalho: int = 30,
    padding_extra: int = 20,
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
    altura_cabecalho: int = 10,
    padding_extra: int = 16,
) -> int:
    if df.empty:
        return altura_min
    linhas = len(df) + df['Setor'].nunique()
    altura = altura_cabecalho + (linhas * altura_linha) + padding_extra
    return max(altura_min, min(altura, altura_max))

def _formatar_valor_tabela(valor) -> str:
    if pd.isna(valor):
        return ""
    if isinstance(valor, (np.integer, int)):
        return f"{int(valor):,}".replace(",", ".")
    if isinstance(valor, (np.floating, float)) and float(valor).is_integer():
        return f"{int(valor):,}".replace(",", ".")
    return str(valor)

def _renderizar_tabela_plotly(df: pd.DataFrame, altura: int, destacar_total: bool = False) -> None:
    df_local = df.copy().reset_index(drop=True)
    colunas = list(df_local.columns)
    valores = [
        [_formatar_valor_tabela(valor) for valor in df_local[coluna].tolist()]
        for coluna in colunas
    ]

    linhas = len(df_local)
    cores_linhas = []
    for i in range(linhas):
        if destacar_total and "Setor" in df_local.columns and str(df_local.iloc[i]["Setor"]) == "Total":
            cores_linhas.append("#0b5ea8")
        else:
            cores_linhas.append("#e9f2ff" if i % 2 == 0 else "white")

    cores_celulas = [cores_linhas[:] for _ in colunas]
    cores_fontes = []
    for i in range(linhas):
        if cores_linhas[i] == "#0b5ea8":
            cores_fontes.append("white")
        else:
            cores_fontes.append("#1f2937")
    fontes_celulas = [cores_fontes[:] for _ in colunas]

    alinhamentos = []
    for coluna in colunas:
        if coluna == "Setor" or coluna == "Equipe":
            alinhamentos.append("left")
        else:
            alinhamentos.append("right")

    if "Setor" in df_local.columns:
        widths = []
        for coluna in colunas:
            if coluna == "Setor":
                widths.append(1.8)
            elif coluna == "Equipe":
                widths.append(2.4)
            else:
                widths.append(1.0)
    else:
        widths = [1.0 for _ in colunas]

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=[f"<b>{coluna}</b>" for coluna in colunas],
                    fill_color="#0b5ea8",
                    font=dict(color="white", size=13),
                    align=["left" if coluna in ("Setor", "Equipe") else "right" for coluna in colunas],
                    line_color="#0b5ea8",
                    height=30,
                ),
                cells=dict(
                    values=valores,
                    fill_color=cores_celulas,
                    font=dict(color=fontes_celulas, size=12),
                    align=alinhamentos,
                    line_color="#d6e4f0",
                    height=26,
                ),
                columnwidth=widths,
            )
        ]
    )
    fig.update_layout(
        height=max(altura, 260),
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

def render_tabela(df: pd.DataFrame, altura: int, destacar_total: bool = False) -> None:
    _renderizar_tabela_plotly(df, altura, destacar_total=destacar_total)

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
        f"<div style='height:{altura}px; min-width:320px; overflow:auto; resize:both; box-sizing:border-box; border:1px solid #d6e4f0; border-radius:4px;'>"
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

def filtro_checkbox_multiplo(label: str, opcoes: list[str], chave_base: str) -> tuple[list[str], bool]:
    st.markdown(f"**{label}**")
    chave_todas = f"{chave_base}_todas"
    chave_todas_prev = f"{chave_base}_todas_prev"

    if chave_todas not in st.session_state:
        st.session_state[chave_todas] = True
    if chave_todas_prev not in st.session_state:
        st.session_state[chave_todas_prev] = st.session_state[chave_todas]

    for i, _ in enumerate(opcoes):
        chave_item = f"{chave_base}_item_{i}"
        if chave_item not in st.session_state:
            st.session_state[chave_item] = True

    selecionar_todas = st.checkbox("Selecionar todas", key=chave_todas)

    if selecionar_todas != st.session_state[chave_todas_prev]:
        for i, _ in enumerate(opcoes):
            st.session_state[f"{chave_base}_item_{i}"] = selecionar_todas
    st.session_state[chave_todas_prev] = selecionar_todas

    selecionadas = []

    for i, opcao in enumerate(opcoes):
        chave_item = f"{chave_base}_item_{i}"
        marcado = st.checkbox(str(opcao), key=chave_item)
        if marcado:
            selecionadas.append(opcao)

    return selecionadas, selecionar_todas

# 2. FUNÇÃO DE LEITURA E TRATAMENTO (Com Cache para velocidade)
@st.cache_data(ttl=300) # O cache dura 5 min. O botão de atualizar força a limpeza.
def carregar_dados():
    # Lendo as abas do Excel
    df_linhas = pd.read_excel(URL_BASE, sheet_name="Linhas TdC")
    df_ciclos = pd.read_excel(URL_SUPORTE, sheet_name="Ciclos")
    dict_tramite_exec = {normalizar_chave_texto(k): v for k, v in MAPA_TRAMITE_EXEC.items()}
    dict_classif_corte = {normalizar_chave_texto(k): v for k, v in MAPA_CLASSIF_CORTE.items()}
    
    # === TRATAMENTOS DA TABELA 'Linhas TdC' (Tradução do M para Python) ===
    # Coluna Condicional: ResultadoProducao
    cond_res = [
        df_linhas['Nota Codificada'].astype(str).str.contains("CONTATO TEL GESTOR", case=False, na=False),
        df_linhas['Resultado'] == "Realizado"
    ]
    escolhas_res = ["Contato Gestor", "Produtivo"]
    df_linhas['ResultadoProducao'] = np.select(cond_res, default="Improdutivo", choicelist=escolhas_res)

    # Mapeamento de trâmite executado via dicionário fixo
    df_linhas['TramiteExec'] = (
        df_linhas['Causa/Descritivo Resultado']
        .map(normalizar_chave_texto)
        .map(dict_tramite_exec)
        .fillna("Não Executado")
    )
    
    # Relacionamento (Mesclagem) com a tabela Ciclos para buscar o "Setor"
    df_linhas = df_linhas.merge(df_ciclos[['Tipo Operação', 'Setor']], on='Tipo Operação', how='left')

    # Classificação de corte via dicionário fixo
    df_linhas['ClassifCorte'] = (
        df_linhas['Tipo Operação']
        .map(normalizar_chave_texto)
        .map(dict_classif_corte)
        .fillna("Não Classificado")
    )
    
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
    with st.container(border=True):
        setores = sorted(df['Setor'].dropna().unique().tolist())
        setor_selecionado = st.multiselect("Setor", options=setores, default=setores)
    
    # Filtro de ResultadoProducao
    with st.container(border=True):
        resultados = sorted(df['ResultadoProducao'].dropna().unique().tolist())
        resultado_selecionado, resultado_todos = filtro_checkbox_multiplo(
            "Resultado",
            resultados,
            "filtro_resultado",
        )

    # Filtro de Classificação de Corte (Massivo/Perdas)
    with st.container(border=True):
        classif_corte_opcoes = [
            opcao for opcao in sorted(df['ClassifCorte'].dropna().unique().tolist())
            if opcao != "Não Classificado"
        ]
        classif_corte_selecionada, classif_corte_todos = filtro_checkbox_multiplo(
            "Classificação Corte",
            classif_corte_opcoes,
            "filtro_classif_corte",
        )
    
    # Filtro de Equipe
    with st.container(border=True):
        equipes = sorted(df['Equipe'].dropna().unique().tolist())
        equipe_selecionada = st.multiselect("Equipe", options=equipes, default=equipes)

# Aplicar filtros no Dataframe
df_filtrado = df.copy()
df_filtrado = df_filtrado[
    (df_filtrado['Setor'].isin(setor_selecionado))
    & (df_filtrado['Equipe'].isin(equipe_selecionada))
]
if not resultado_todos:
    df_filtrado = df_filtrado[df_filtrado['ResultadoProducao'].isin(resultado_selecionado)]
if not classif_corte_todos:
    df_filtrado = df_filtrado[
        (df_filtrado['Setor'] == "Corte")
        & (df_filtrado['ClassifCorte'].isin(classif_corte_selecionada))
    ]

# 5. CARDS SUPERIORES (Métricas)
total_ordens = len(df_filtrado)
qtde_produtivo = len(df_filtrado[df_filtrado['ResultadoProducao'] == 'Produtivo'])
qtde_improdutivo = len(df_filtrado[df_filtrado['ResultadoProducao'] == 'Improdutivo'])

def formatar_inteiro(valor: int) -> str:
    return f"{int(valor):,}".replace(",", ".")

col_ind1, col_ind2, col_ind3 = st.columns(3)
with col_ind1:
    st.markdown(
        "<div class='indicador-card'>"
        "<div class='indicador-titulo'>Total de Ordens</div>"
        f"<div class='indicador-valor'>{formatar_inteiro(total_ordens)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
with col_ind2:
    st.markdown(
        "<div class='indicador-card'>"
        "<div class='indicador-titulo'>Qtde Produtivo</div>"
        f"<div class='indicador-valor'>{formatar_inteiro(qtde_produtivo)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )
with col_ind3:
    st.markdown(
        "<div class='indicador-card'>"
        "<div class='indicador-titulo'>Qtde Improdutivo</div>"
        f"<div class='indicador-valor'>{formatar_inteiro(qtde_improdutivo)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

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
    ordem_setores = df_quantitativo['Setor'].tolist()

    df_setores_gerais = df_quantitativo[df_quantitativo['Setor'] != 'Corte'][
        ['Setor', 'Produtivo', 'Improdutivo', 'Contato Gestor']
    ]

    df_corte_detalhado = (
        df_filtrado[
            (df_filtrado['Setor'] == 'Corte')
            & (df_filtrado['ClassifCorte'].isin(['Massivo', 'Perdas']))
        ]
        .groupby(['ClassifCorte', 'ResultadoProducao'])
        .size()
        .unstack(fill_value=0)
        .reset_index()
        .rename(columns={'ClassifCorte': 'Setor'})
    )
    df_corte_base = pd.DataFrame({'Setor': ['Massivo', 'Perdas']})
    df_corte_detalhado = df_corte_base.merge(df_corte_detalhado, on='Setor', how='left').fillna(0)
    for coluna in ["Produtivo", "Improdutivo", "Contato Gestor"]:
        if coluna not in df_corte_detalhado.columns:
            df_corte_detalhado[coluna] = 0
    df_corte_detalhado['Setor'] = df_corte_detalhado['Setor'].map({
        'Massivo': 'Corte Massivo',
        'Perdas': 'Corte Perdas',
    })
    df_corte_detalhado = df_corte_detalhado[['Setor', 'Produtivo', 'Improdutivo', 'Contato Gestor']]

    df_quantitativo = pd.concat([df_setores_gerais, df_corte_detalhado], ignore_index=True)
    ordem_final = []
    for setor in ordem_setores:
        if setor == 'Corte':
            ordem_final.extend(['Corte Massivo', 'Corte Perdas'])
        else:
            ordem_final.append(setor)
    df_quantitativo['Setor'] = pd.Categorical(df_quantitativo['Setor'], categories=ordem_final, ordered=True)
    df_quantitativo = df_quantitativo.sort_values('Setor').reset_index(drop=True)

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