# streamlit_simulador.py
import streamlit as st
import pandas as pd
from collections import defaultdict
import io
import plotly.express as px
from datetime import datetime
from pathlib import Path
import pytz

st.set_page_config(page_title="Simulador de Separação", layout="wide")
st.title("🔪 Simulador de Separação de Produtos")

# Colunas principais
col_esq, col_dir = st.columns([2, 2])

# Entrada de parâmetros (lado esquerdo)
with col_esq:
    tempo_produto = st.number_input("⏱️ Tempo médio por produto (s)", value=20.0, step=1.0, format="%.2f")
    tempo_deslocamento = st.number_input("🚚 Tempo entre estações (s)", value=5.0, step=1.0, format="%.2f")
    capacidade_estacao = st.number_input("📦 Capacidade máxima de caixas simultâneas por estação", value=10, min_value=1)
    pessoas_por_estacao = st.number_input("👷‍♂️ Número de pessoas por estação", value=1.0, min_value=0.01, step=0.1, format="%.2f")
    tempo_adicional_caixa = st.number_input("➕ Tempo adicional por caixa (s)", value=0.0, step=1.0, format="%.2f")
    novo_arquivo = st.file_uploader("📂 Arquivo para Simulação", type=["xlsx"], key="upload_simulacao")

# Salva o arquivo no estado, se for novo upload
if novo_arquivo is not None:
    st.session_state.arquivo_atual = novo_arquivo

# Usa o arquivo do estado, se disponível
uploaded_file = st.session_state.get("arquivo_atual", None)

# Função auxiliar para formatar tempo
def formatar_tempo(segundos):
    if segundos < 60:
        return f"{int(round(segundos))} segundos"
    dias = int(segundos // 86400)
    segundos %= 86400
    horas = int(segundos // 3600)
    segundos %= 3600
    minutos = int(segundos // 60)
    segundos = int(round(segundos % 60))
    partes = []
    if dias > 0: partes.append(f"{dias} {'dia' if dias == 1 else 'dias'}")
    if horas > 0: partes.append(f"{horas} {'hora' if horas == 1 else 'horas'}")
    if minutos > 0: partes.append(f"{minutos} {'minuto' if minutos == 1 else 'minutos'}")
    if segundos > 0: partes.append(f"{segundos} {'segundo' if segundos == 1 else 'segundos'}")
    return " e ".join(partes)

# Inicializa session_state
if "simulacoes_salvas" not in st.session_state:
    st.session_state.simulacoes_salvas = {}
if "ultima_simulacao" not in st.session_state:
    st.session_state.ultima_simulacao = {}
if "ordem_simulacoes" not in st.session_state:
    st.session_state.ordem_simulacoes = []

# Upload para comparação externo
st.markdown("---")
st.subheader("📁 Comparação com Outro Arquivo Excel (Opcional)")
uploaded_comp = st.file_uploader("📁 Arquivo para Comparação", type=["xlsx"], key="upload_comparacao")

# Botão de simulação
with col_esq:
    ver_graficos = st.checkbox("📊 Ver gráficos e dashboards", value=True)
    comparar_simulacoes = st.checkbox("🔁 Comparar com simulações anteriores ou Excel", value=True)

# Início da simulação
if uploaded_file is not None and st.button("▶️ Iniciar Simulação"):
    try:
        df = pd.read_excel(uploaded_file)
        df = df.sort_values(by=["ID_Pacote", "ID_Caixas"])
        caixas = df["ID_Caixas"].unique()

        estimativas, tempo_caixas = [], {}
        disponibilidade_estacao = defaultdict(list)
        tempo_por_estacao = defaultdict(float)
        gargalo_ocorrido = False
        tempo_gargalo = None
        tempo_total_simulacao = 0

        for caixa in caixas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            total_produtos = caixa_df["Contagem de Produto"].sum()
            num_estacoes = caixa_df["Estação"].nunique()
            tempo_estimado = (total_produtos * tempo_produto) / pessoas_por_estacao + (num_estacoes * tempo_deslocamento) + tempo_adicional_caixa
            estimativas.append((caixa, tempo_estimado))

        caixas_ordenadas = [cx for cx, _ in sorted(estimativas, key=lambda x: x[1])]

        for caixa in caixas_ordenadas:
            caixa_df = df[df["ID_Caixas"] == caixa]
            tempo_inicio_caixa = 0
            tempos_finais = []

            for _, linha in caixa_df.iterrows():
                estacao = linha["Estação"]
                contagem = linha["Contagem de Produto"]
                duracao = (contagem * tempo_produto) / pessoas_por_estacao + tempo_deslocamento

                if not disponibilidade_estacao[estacao]:
                    disponibilidade_estacao[estacao] = [0.0] * int(max(1, pessoas_por_estacao))

                idx_pessoa_livre = disponibilidade_estacao[estacao].index(min(disponibilidade_estacao[estacao]))
                inicio = max(disponibilidade_estacao[estacao][idx_pessoa_livre], tempo_inicio_caixa)
                fim = inicio + duracao

                if len(disponibilidade_estacao[estacao]) >= capacidade_estacao and not gargalo_ocorrido and inicio > 0:
                    gargalo_ocorrido = True
                    tempo_gargalo = inicio

                disponibilidade_estacao[estacao][idx_pessoa_livre] = fim
                tempo_por_estacao[estacao] += duracao
                tempos_finais.append(fim)

            fim_caixa = max(tempos_finais) + tempo_adicional_caixa if tempos_finais else 0
            tempo_caixas[caixa] = fim_caixa - tempo_inicio_caixa
            tempo_total_simulacao = max(tempo_total_simulacao, fim_caixa)

        fuso_brasil = pytz.timezone("America/Sao_Paulo")
        data_hora = datetime.now(fuso_brasil).strftime("%Y-%m-%d_%Hh%Mmin")
        nome_base = Path(uploaded_file.name).stem
        id_simulacao = f"{nome_base}_{data_hora}"

        st.session_state.ultima_simulacao = {
            "tempo_total": tempo_total_simulacao,
            "tempo_por_estacao": tempo_por_estacao,
            "gargalo": tempo_gargalo,
            "total_caixas": len(caixas),
            "tempo_caixas": tempo_caixas,
            "id": id_simulacao
        }

        st.session_state.simulacoes_salvas[id_simulacao] = st.session_state.ultima_simulacao
        st.session_state.ordem_simulacoes.append(id_simulacao)

        if len(st.session_state.simulacoes_salvas) > 5:
            ids = sorted(st.session_state.simulacoes_salvas)[-5:]
            st.session_state.simulacoes_salvas = {k: st.session_state.simulacoes_salvas[k] for k in ids}
            st.session_state.ordem_simulacoes = ids

        st.success(f"✅ Simulação salva como ID: {id_simulacao}")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")

# Exibição do último resultado
if "ultima_simulacao" in st.session_state and st.session_state.ultima_simulacao:
    sim = st.session_state.ultima_simulacao
    tempo_total = sim["tempo_total"]
    gargalo = sim["gargalo"]
    tempo_por_estacao = sim["tempo_por_estacao"]
    caixas = sim["total_caixas"]

    st.markdown("---")
    st.subheader("📊 Resultados da Simulação")
    st.write(f"🔚 **Tempo total para separar todas as caixas:** {formatar_tempo(tempo_total)}")
    st.write(f"📦 **Total de caixas simuladas:** {caixas}")
    st.write(f"🧱 **Tempo até o primeiro gargalo:** {formatar_tempo(gargalo) if gargalo else 'Nenhum gargalo'}")

    df_estacoes = pd.DataFrame([
        {"Estação": est, "Tempo Total (s)": tempo} for est, tempo in tempo_por_estacao.items()
    ])

    st.markdown("---")
    st.subheader("🧠 Sugestão de Layout Otimizado")
    tempo_medio = df_estacoes["Tempo Total (s)"].mean()
    limiar = 1.5 * tempo_medio
    estacoes_sobrec = df_estacoes[df_estacoes["Tempo Total (s)"] > limiar]

    if not estacoes_sobrec.empty:
        st.warning("⚠️ Estações sobrecarregadas detectadas! Sugere-se redistribuir produtos para:")
        st.dataframe(estacoes_sobrec.assign(Sugestao="Redistribuir para estações abaixo da média."))
    else:
        st.success("🚀 Nenhuma estação sobrecarregada detectada.")

# Comparativo
if comparar_simulacoes and len(st.session_state.simulacoes_salvas) > 1:
    st.markdown("---")
    st.subheader("🔁 Comparativo entre Simulações")

    ids = st.session_state.ordem_simulacoes[-2:]
    id1, id2 = ids[0], ids[1]
    sim1 = st.session_state.simulacoes_salvas[id1]
    sim2 = st.session_state.simulacoes_salvas[id2]

    tempo1 = sim1["tempo_total"]
    tempo2 = sim2["tempo_total"]

    delta_tempo = tempo2 - tempo1
    abs_pct = abs(delta_tempo / tempo1 * 100) if tempo1 else 0
    direcao = "melhorou" if delta_tempo < 0 else "aumentou"

    caixas1 = sim1["total_caixas"]
    caixas2 = sim2["total_caixas"]
    caixas_diferenca = caixas2 - caixas1
    caixas_pct = (caixas_diferenca / caixas1 * 100) if caixas1 else 0

    tempo_formatado = formatar_tempo(abs(delta_tempo))
    st.metric("Delta de Tempo Total", f"{tempo_formatado}", f"{delta_tempo:+.0f}s ({abs_pct:.1f}% {direcao})")
    st.write(f"📦 **Caixas Base:** {caixas1} | **Comparada:** {caixas2} | Δ {caixas_diferenca:+} caixas ({caixas_pct:+.1f}%)")

    df_comp = pd.DataFrame([
        {"Estação": est, "Tempo (s)": tempo, "Simulação": id1} for est, tempo in sim1["tempo_por_estacao"].items()
    ] + [
        {"Estação": est, "Tempo (s)": tempo, "Simulação": id2} for est, tempo in sim2["tempo_por_estacao"].items()
    ])

    st.markdown("### 📊 Comparativo de Tempo por Estação")
    fig_comp = px.bar(df_comp, x="Estação", y="Tempo (s)", color="Simulação", barmode="group")
    st.plotly_chart(fig_comp, use_container_width=True)

elif uploaded_comp is not None:
    st.warning("⚠️ Para comparar corretamente, primeiro clique em '▶️ Iniciar Simulação' com o novo arquivo carregado.")
