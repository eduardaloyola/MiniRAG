"""Guia Cidadão: app web público de RAG sobre direitos e burocracia (Streamlit).

A chave da API NÃO fica no código: vem de st.secrets (na hospedagem)
ou da variável de ambiente GEMINI_API_KEY (rodando local).
"""
import os
from datetime import date

import streamlit as st

from rag import buscar, carregar_documentos, criar_client, dividir_em_chunks, gerar_embeddings, responder

# ---- Limites para proteger sua cota gratuita ----
MAX_PERGUNTAS_POR_SESSAO = 10
MAX_PERGUNTAS_POR_DIA = 50  # somando todos os visitantes
MAX_CARACTERES = 300

EXEMPLOS = [
    "Qual o limite de faturamento do MEI?",
    "Comprei online e quero devolver. Tenho quantos dias?",
    "Como tirar a nova carteira de identidade (CIN)?",
]

st.set_page_config(page_title="Guia Cidadão", page_icon="⚖️")


def sem_latex(texto: str) -> str:
    return texto.replace("$", "\\$")


def obter_chave() -> str | None:
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.getenv("GEMINI_API_KEY")


@st.cache_resource(show_spinner="Carregando a base de conhecimento...")
def carregar_indice(chave: str):
    """Roda uma vez por servidor: os visitantes reaproveitam o mesmo índice."""
    client = criar_client(chave)
    chunks = dividir_em_chunks(carregar_documentos("docs"))
    vetores = gerar_embeddings(client, chunks, "RETRIEVAL_DOCUMENT")
    return client, chunks, vetores


@st.cache_resource
def contador_global() -> dict:
    return {"dia": date.today(), "n": 0}


def limite_diario_atingido() -> bool:
    c = contador_global()
    if c["dia"] != date.today():
        c["dia"], c["n"] = date.today(), 0
    return c["n"] >= MAX_PERGUNTAS_POR_DIA


def escolher_exemplo(texto: str):
    st.session_state.exemplo = texto


# ---------------- Interface ----------------
st.title("⚖️ Guia Cidadão")
st.caption("Tire dúvidas sobre MEI, direitos do consumidor e documentos básicos. As respostas vêm de uma base de conhecimento com fontes oficiais.")
st.warning(
    "**Informação geral, não substitui orientação profissional.** Para o seu caso, procure o órgão oficial, "
    "um contador, um advogado ou a Defensoria Pública. Valores e prazos mudam: confirme no site oficial. "
    "Base atualizada em setembro de 2026."
)

with st.sidebar:
    st.header("Sobre este projeto")
    st.markdown(
        "Projeto de estudo que usa **RAG** (Retrieval-Augmented Generation):\n\n"
        "1. A base é dividida em **trechos**\n"
        "2. Cada trecho vira um **embedding**\n"
        "3. Sua pergunta também vira embedding\n"
        "4. Os trechos mais **similares** são recuperados\n"
        "5. O **Gemini** responde só com eles"
    )
    st.markdown("**Temas da base:** MEI · Direitos do consumidor · Documentos básicos")
    st.info("⚠️ Não digite dados pessoais ou sensíveis. As perguntas são enviadas à API do Gemini.")
    st.caption(f"Limite: {MAX_PERGUNTAS_POR_SESSAO} perguntas por visita.")

chave = obter_chave()
if not chave:
    st.error("Chave da API não configurada. (Dono do app: defina GEMINI_API_KEY nos Secrets.)")
    st.stop()

try:
    client, chunks, vetores = carregar_indice(chave)
except Exception as e:
    print("ERRO AO INDEXAR:", repr(e))
    st.error("Não consegui carregar a base agora (talvez o limite gratuito da API). Tente em alguns minutos.")
    st.stop()

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []
    st.session_state.usadas = 0

pergunta = st.chat_input("Ex.: Quanto o MEI paga por mês? Como reclamar de um produto com defeito?", max_chars=MAX_CARACTERES)
if "exemplo" in st.session_state:
    pergunta = st.session_state.pop("exemplo")

# Botões de exemplo (só na tela inicial)
if not st.session_state.mensagens and not pergunta:
    st.markdown("**Experimente perguntar:**")
    for ex in EXEMPLOS:
        st.button(ex, on_click=escolher_exemplo, args=(ex,), use_container_width=True)

for m in st.session_state.mensagens:
    with st.chat_message(m["role"]):
        st.markdown(sem_latex(m["content"]))
        if m.get("fontes"):
            with st.expander("Trechos da base usados"):
                for texto, score in m["fontes"]:
                    st.caption(f"similaridade {score:.2f}")
                    st.text(texto)

if pergunta:
    with st.chat_message("user"):
        st.markdown(sem_latex(pergunta))
    st.session_state.mensagens.append({"role": "user", "content": pergunta})

    fontes = None
    if st.session_state.usadas >= MAX_PERGUNTAS_POR_SESSAO:
        resposta = "Você atingiu o limite de perguntas desta visita. 🙂"
    elif limite_diario_atingido():
        resposta = "O limite diário do app foi atingido. Volte amanhã!"
    else:
        with st.spinner("Buscando na base e gerando resposta..."):
            try:
                fontes = buscar(client, pergunta, chunks, vetores)
                resposta = responder(client, pergunta, fontes)
                st.session_state.usadas += 1
                contador_global()["n"] += 1
            except Exception as e:
                print("ERRO REAL:", repr(e))
                fontes = None
                resposta = "Ops, a API está ocupada ou no limite. Tente de novo em instantes."

    with st.chat_message("assistant"):
        st.markdown(sem_latex(resposta))
        if fontes:
            with st.expander("Trechos da base usados"):
                for texto, score in fontes:
                    st.caption(f"similaridade {score:.2f}")
                    st.text(texto)

    st.session_state.mensagens.append({"role": "assistant", "content": resposta, "fontes": fontes})
