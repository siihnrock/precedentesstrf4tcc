"""
app.py - Interface Web para Pesquisa, Comparação de Precedentes e Sessões do TRF4
Especializado em matéria Previdenciária e no Mapeamento de Prova Emprestada.
Executar com: streamlit run app.py
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

from database import init_db, buscar_precedentes, obter_estatisticas, salvar_precedente
from crawler import buscar_jurisprudencia_trf4, coletar_e_salvar, atualizar_semanalmente_previdenciario
from comparator import gerar_analise_comparativa
from sessoes import coletar_sessoes_trf4, extrair_acordaos_da_sessao

# Configuração da Página
st.set_page_config(
    page_title="Precedentes & Prova Emprestada — TRF4",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar banco
init_db()

# Custom CSS
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1a365d;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.02rem;
        color: #4a5568;
        margin-bottom: 1.4rem;
    }
    .turma-tag {
        font-size: 0.82rem;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        display: inline-block;
    }
    .tag-tribunal { background-color: #e2e8f0; color: #1a202c; border-left: 3px solid #3182ce; }
    .tag-rs { background-color: #ebf8ff; color: #2b6cb0; border-left: 3px solid #3182ce; }
    .tag-sc { background-color: #f0fff4; color: #276749; border-left: 3px solid #38a169; }
    .tag-pr { background-color: #faf5ff; color: #6b46c1; border-left: 3px solid #805ad5; }
    .tag-tru { background-color: #fffaf0; color: #c05621; border-left: 3px solid #dd6b20; font-weight: bold; }
    .status-hoje { background-color: #feebc8; color: #7b341e; font-weight: bold; padding: 2px 7px; border-radius: 4px; }
    .status-futuro { background-color: #e6fffa; color: #234e52; padding: 2px 7px; border-radius: 4px; }
    .status-passado { background-color: #edf2f7; color: #4a5568; padding: 2px 7px; border-radius: 4px; }
    .box-destaque {
        background-color: #ebf8ff;
        border-left: 4px solid #3182ce;
        padding: 15px;
        border-radius: 6px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Barra Lateral
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Coat_of_arms_of_Brazil.svg/200px-Coat_of_arms_of_Brazil.svg.png", width=60)
st.sidebar.title("Precedentes TRF4")
st.sidebar.caption("Inteligência Jurisprudencial Previdenciária (2ª Instância & Turmas Recursais)")

st.sidebar.divider()

# Atualização Semanal
st.sidebar.subheader("🔄 Sincronização Semanal")
st.sidebar.write("Coleta os acórdãos recém-publicados nas Turmas do Tribunal (5ª, 6ª, 9ª, 10ª) e Turmas Recursais.")
dias_atualizacao = st.sidebar.slider("Dias retroativos:", min_value=7, max_value=60, value=15, step=7)

if st.sidebar.button("🚀 Sincronizar Novos Julgados", use_container_width=True):
    with st.spinner("Conectando ao eproc do TRF4 e sincronizando..."):
        res = atualizar_semanalmente_previdenciario(dias_atras=dias_atualizacao)
        st.sidebar.success(f"Concluído! {res['total_novos']} novos acórdãos cadastrados.")
        for d in res['detalhes']:
            st.sidebar.caption(d)

st.sidebar.divider()

# Configuração de IA Opcional
st.sidebar.subheader("🤖 IA Generativa (Opcional)")
api_key = st.sidebar.text_input("Chave da API Gemini:", type="password", help="Opcional. Se informada, gera parecer analítico e recomendações de peticionamento com LLM.")

st.sidebar.divider()
st.sidebar.info("💡 **Cobertura:** 5ª, 6ª, 9ª e 10ª Turmas do Tribunal (2ª Instância) + Turmas Recursais (RS, SC, PR) + TRU4.")

# Cabeçalho Principal
st.markdown('<div class="main-title">⚖️ Base de Precedentes Previdenciários — TRF4</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Confronto de teses da 2ª Instância (5ª, 6ª, 9ª e 10ª Turmas), Turmas Recursais e TRU4, com mapeamento da Prova Emprestada e Pautas de Sessões.</div>', unsafe_allow_html=True)

# Métricas da Base
stats = obter_estatisticas()
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total no Acervo", stats['total'])
with col2:
    st.metric("Tribunal (2ª Instância)", stats['por_uf'].get('TRF4 (2ª Instância)', 0))
with col3:
    st.metric("Turmas RS", stats['por_uf'].get('RS', 0))
with col4:
    st.metric("Turmas SC", stats['por_uf'].get('SC', 0))
with col5:
    st.metric("Turmas PR", stats['por_uf'].get('PR', 0))

# Abas da Aplicação
tab_prova_emprestada, tab_pesquisa, tab_sessoes, tab_acervo, tab_sobre = st.tabs([
    "🔬 Mapeamento: Prova Emprestada",
    "🔍 Pesquisar & Comparar Teses",
    "📅 Sessões de Julgamento (Pautas & Ementas)",
    "📚 Acervo Local",
    "⚙️ Como Funciona"
])

# ----------------- ABA 1: MAPEAMENTO ESPECIAL: PROVA EMPRESTADA -----------------
with tab_prova_emprestada:
    st.subheader("🔬 Valoração da Prova Emprestada nas Turmas Previdenciárias do TRF4")
    
    st.markdown("""
    <div class="box-destaque">
        <strong>Ponto Central da Divergência:</strong> A admissibilidade de laudos periciais emprestados ou por similaridade 
        (Súmula 106 do TRF4 e Tema 208 da TNU) divide os colegiados da 4ª Região quanto ao rigor na exigência de empresa ativa, 
        identidade de maquinário e tipo de agente nocivo (ruído vs agentes químicos).
    </div>
    """, unsafe_allow_html=True)

    col_btn_pe, col_origem_pe = st.columns([1, 2])
    with col_btn_pe:
        btn_carregar_pe = st.button("🔎 Analisar Julgados de Prova Emprestada", type="primary", use_container_width=True)
    with col_origem_pe:
        instancia_pe = st.selectbox(
            "Abrangência:",
            ["Todas as Turmas Previdenciárias (2ª Instância + Turmas Recursais)", "Apenas 2ª Instância (5ª, 6ª, 9ª e 10ª Turmas)", "Apenas Turmas Recursais (JEFs)"]
        )

    origem_cod = "todas"
    if "2ª Instância" in instancia_pe: origem_cod = "1"
    elif "Turmas Recursais" in instancia_pe: origem_cod = "3"

    # Quadro comparativo fixo com a doutrina consolidada do TRF4
    st.markdown("### 📊 Matriz Comparativa: Valoração da Prova Emprestada por Colegiado")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("#### 🏛️ 5ª e 6ª Turmas (Tribunal)")
        st.markdown("""
        * **Postura:** **Mais Rigorosa na Prova Direta**.
        * **Empresa Ativa:** Se a empresa empregadora estiver formalmente ativa, **não admitem de pronto** o laudo similar/emprestado. Exigem que o segurado comprove ter esgotado a busca pelo PPP ou requerido intimação judicial da empresa.
        * **Extinção:** Havendo inércia, aplicam extinção sem resolução do mérito por falta de interesse/prova (Tema 629/STJ).
        * **Ruído:** Inadmissível por similaridade genérica.
        """)
    with c2:
        st.markdown("#### 🏛️ 9ª e 10ª Turmas (Tribunal)")
        st.markdown("""
        * **Postura:** **Mais Flexível e Pragmática**.
        * **Empresa Ativa:** Reconhecem que, mesmo estando ativa na Receita, se houve **mudança substancial de layout, maquinário ou fechamento da fábrica local**, a perícia contemporânea é inútil, admitindo o laudo paradigma (Súmula 106).
        * **Agentes Químicos:** Ampla aceitação para hidrocarbonetos, solventes e graxas por similaridade da função.
        * **Ruído:** Exigem demonstração de idêntica máquina/posto.
        """)
    with c3:
        st.markdown("#### ⚖️ Turmas Recursais & TRU4")
        st.markdown("""
        * **Postura:** **Orientada pelo Tema 208 da TNU**.
        * **Tema 208/TNU:** Admite laudo similar mesmo em empresa formalmente ativa se comprovada a inviabilidade da perícia in loco.
        * **Divergência Interna:** A 1ª e 2ª TR/RS e SC exigem identidade estrita de máquinas; já as turmas do PR e 3ª TR/RS aceitam similaridade por função típica do ramo fabril.
        * **Contraditório:** Não exigem que o INSS tenha sido parte no laudo originário (contraditório diferido).
        """)

    st.divider()

    # Se clicou para buscar precedentes reais
    if btn_carregar_pe:
        with st.spinner("Buscando acórdãos reais sobre Prova Emprestada no TRF4..."):
            coleta_pe = coletar_e_salvar(
                termo='previdenciário "prova emprestada"',
                origem=origem_cod
            )
            precedentes_pe = coleta_pe['precedentes']

            if precedentes_pe:
                st.success(f"Foram analisados **{len(precedentes_pe)} acórdãos recentes** sobre Prova Emprestada no TRF4.")
                rel_pe = gerar_analise_comparativa('previdenciário "prova emprestada"', precedentes_pe, api_key_gemini=api_key if api_key else None)

                # Resumo por colegiado
                st.markdown("### 📋 Julgados Reais Encontrados por Órgão")
                for orgao_nome, dados in rel_pe['resumo_orgaos'].items():
                    with st.expander(f"📁 {orgao_nome} ({dados['total']} acórdãos) — Predominância: {dados['posicao_predominante']}"):
                        st.write(f"- Menções a Prova Emprestada / Similaridade: **{dados['mencoes_prova_emprestada']}**")
                        st.write(f"- Menções a Empresa Ativa: **{dados['mencoes_empresa_ativa']}**")
                        for ex in dados['exemplos']:
                            st.markdown(f"**Processo:** `{ex['processo']}` | **Relator(a):** {ex.get('relator', 'N/D')} | **Data:** {ex.get('data_julgamento', 'N/D')}")
                            st.caption(f"{ex['texto_completo'][:320]}...")
                            if ex.get('link_eproc'):
                                st.link_button("🌐 Abrir no eproc TRF4", ex['link_eproc'], key=f"pe_{ex['processo']}")
                            st.divider()
            else:
                st.warning("Nenhum julgado recente retornado. Tente a opção 'Todas as Turmas'.")

# ----------------- ABA 2: PESQUISA E COMPARAÇÃO GERAL -----------------
with tab_pesquisa:
    st.subheader("Pesquisa & Confronto Geral de Teses Previdenciárias")
    
    col_input, col_instancia, col_modo = st.columns([3, 2, 2])
    with col_input:
        termo = st.text_input(
            "Tema ou Controvérsia:",
            value='previdenciário "prova emprestada"',
            placeholder="Ex: aposentadoria especial vigilante, reafirmação da DER, laudo similar Súmula 106..."
        )
    with col_instancia:
        instancia_sel = st.selectbox(
            "Colegiados:",
            ["Todas as Instâncias", "Tribunal (2ª Instância: 5ª, 6ª, 9ª, 10ª Turmas)", "Turmas Recursais (JEFs: RS, SC, PR)", "TRU4 (Uniformização)"]
        )
    with col_modo:
        modo_busca = st.selectbox(
            "Fonte da busca:",
            ["eproc TRF4 (Tempo Real + Salva)", "Acervo Local (Instantâneo)"]
        )

    cod_origem = "todas"
    if "Tribunal" in instancia_sel: cod_origem = "1"
    elif "Turmas Recursais" in instancia_sel: cod_origem = "3"
    elif "TRU4" in instancia_sel: cod_origem = "2"

    if st.button("🔎 Confrontar Entendimentos", type="primary"):
        with st.spinner("Pesquisando acórdãos e confrontando colegiados..."):
            if "eproc" in modo_busca:
                coleta = coletar_e_salvar(termo, origem=cod_origem)
                precedentes = coleta['precedentes']
                if coleta['novos_inseridos'] > 0:
                    st.toast(f"{coleta['novos_inseridos']} novos julgados adicionados à base!")
            else:
                precedentes = buscar_precedentes(termo=termo, limite=50)

            if not precedentes:
                st.warning("Nenhum acórdão localizado com estes termos.")
            else:
                relatorio = gerar_analise_comparativa(termo, precedentes, api_key_gemini=api_key if api_key else None)

                st.divider()
                st.subheader("📊 Diagnóstico Comparativo entre Colegiados")
                if relatorio['divergencia_detectada']:
                    st.warning(f"⚠️ **Divergência Detectada:**\n\n{relatorio['diagnostico']}")
                else:
                    st.success(f"✅ **Alinhamento:**\n\n{relatorio['diagnostico']}")

                if relatorio['temas_vinculantes']:
                    st.markdown("**Temas Vinculantes Invocados:**")
                    st.write(", ".join([f"`{t}`" for t in relatorio['temas_vinculantes']]))

                st.markdown("### 📋 Julgados Detalhados")
                for i, prec in enumerate(precedentes):
                    with st.container():
                        st.markdown(f"""
                        <div class="card-acordao">
                            <span class="turma-tag tag-tribunal">{prec['orgao']}</span>
                            <strong style="margin-left: 8px;">{prec['processo']}</strong>
                            <span style="float: right; color: #718096; font-size: 0.88rem;">
                                Julgado em: {prec.get('data_julgamento', 'N/D')} | Rel: {prec.get('relator', 'N/D')}
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                        with st.expander(f"Ver Ementa / Voto Completo ({prec['processo']})"):
                            st.text_area("Texto Integral:", prec['texto_completo'], height=180, key=f"txt_{i}_{prec['processo']}")
                            c1, c2 = st.columns(2)
                            with c1:
                                if prec.get('link_eproc'):
                                    st.link_button("🌐 Acessar Processo no eproc TRF4", prec['link_eproc'])
                            with c2:
                                if prec.get('link_inteiro_teor'):
                                    st.link_button("📄 Baixar Inteiro Teor / PDF", prec['link_inteiro_teor'])

# ----------------- ABA 3: SESSÕES DE JULGAMENTO (PASSADAS E FUTURAS) -----------------
with tab_sessoes:
    st.subheader("📅 Pautas, Atas & Sessões de Julgamento do TRF4")
    st.caption("Acesse o calendário oficial de sessões passadas ou futuras e extraia as ementas publicadas a partir das pautas.")

    col_mes, col_ano, col_origem_sess = st.columns(3)
    hoje = datetime.now()
    with col_mes:
        mes_escolhido = st.selectbox("Mês:", range(1, 13), index=hoje.month - 1, format_func=lambda m: [
            "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
        ][m-1])
    with col_ano:
        ano_escolhido = st.selectbox("Ano:", [hoje.year - 1, hoje.year, hoje.year + 1], index=1)
    with col_origem_sess:
        uf_sessao = st.selectbox("Filtrar Colegiados:", ["TODAS", "Tribunal / TRU", "RS", "SC", "PR"])

    with st.spinner("Carregando sessões do calendário oficial..."):
        uf_p = None if uf_sessao == "TODAS" else uf_sessao
        sessoes_lista = coletar_sessoes_trf4(uf_filtro=uf_p, mes=mes_escolhido, ano=ano_escolhido)

    if sessoes_lista:
        st.write(f"Total de sessões localizadas em {mes_escolhido}/{ano_escolhido}: **{len(sessoes_lista)}**")
        
        for idx, s in enumerate(sessoes_lista[:20]):
            status_cls = "status-hoje" if s['status'] == 'HOJE' else ("status-passado" if "Passada" in s['status'] or "Realizada" in s['status'] else "status-futuro")
            
            with st.container():
                col_info, col_link, col_ext = st.columns([3, 1.2, 1.8])
                with col_info:
                    st.markdown(f"**{s['orgao_nome']}** ({s['uf']}) — <span class='{status_cls}'>{s['status']}</span>", unsafe_allow_html=True)
                    st.caption(f"🗓️ Sessão: **{s['data_hora']}** | Modalidade: **{s['modalidade']}**")
                with col_link:
                    st.link_button("📜 Pauta/Ata eproc", s['link_pauta'], use_container_width=True)
                with col_ext:
                    # Botão para extrair acórdãos daquela data específica
                    if st.button("📥 Extrair Ementas Publicadas", key=f"btn_ext_{idx}_{s['codigo_orgao']}", use_container_width=True):
                        st.session_state[f"show_acordaos_{idx}"] = True

                # Se o usuário clicou para extrair ementas desta sessão
                if st.session_state.get(f"show_acordaos_{idx}", False):
                    with st.spinner(f"Extraindo acórdãos publicados da sessão de {s['data_apenas']} ({s['orgao_nome']})..."):
                        acordaos_sess = extrair_acordaos_da_sessao(s['orgao_nome'], s['data_apenas'])
                        if acordaos_sess:
                            st.success(f"Encontrados **{len(acordaos_sess)} acórdãos publicados** decorrentes desta sessão:")
                            for ac in acordaos_sess[:5]:
                                st.markdown(f"- **{ac['processo']}** (Rel. {ac['relator']}): *{ac['texto_completo'][:200]}...*")
                                if ac.get('link_eproc'):
                                    st.link_button("Ver no eproc", ac['link_eproc'], key=f"lk_{idx}_{ac['processo']}")
                        else:
                            st.info("Nenhum acórdão com publicação formalizada no eproc localizado para esta data exata (podem estar em fase de elaboração do acórdão).")
                st.divider()
    else:
        st.warning("Nenhuma sessão identificada para o período selecionado.")

# ----------------- ABA 4: ACERVO LOCAL -----------------
with tab_acervo:
    st.subheader("Explorador do Acervo Local")
    filtro_t = st.text_input("Filtrar acervo por palavra-chave:", placeholder="Ex: prova emprestada, similaridade, rural...")
    dados_locais = buscar_precedentes(termo=filtro_t, limite=100)
    if dados_locais:
        df = pd.DataFrame(dados_locais)[['processo', 'orgao', 'uf', 'relator', 'data_julgamento', 'data_coleta']]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Nenhum registro local encontrado.")

# ----------------- ABA 5: COMO FUNCIONA -----------------
with tab_sobre:
    st.subheader("Como Funciona o Sistema")
    st.markdown("""
    1. **Abrangência Completa no TRF4:**
       - **2ª Instância (Tribunal):** 5ª, 6ª, 9ª e 10ª Turmas Especializadas em Previdenciário + 2ª Seção.
       - **Juizados Especiais Federais:** Turmas Recursais do RS, SC e PR.
       - **Uniformização:** Turma Regional de Uniformização da 4ª Região (TRU4).

    2. **Extração a partir de Sessões Passadas:**
       - Na aba de Sessões, você pode selecionar **qualquer mês e ano passado**.
       - O botão **"Extrair Ementas Publicadas"** consulta o eproc diretamente com a data daquela sessão e o respectivo colegiado, capturando os acórdãos formalizados.

    3. **Mapeamento de Prova Emprestada:**
       - Mapeia o confronto entre o rigor formal (5ª/6ª Turmas) e a flexibilidade prática (9ª/10ª Turmas) quanto a empresa ativa, agentes químicos e Súmula 106.
    """)
