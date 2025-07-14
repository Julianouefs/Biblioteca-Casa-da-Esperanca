import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")

st.title("📚 Biblioteca Casa da Esperança")

# 🔐 Configurações do admin
LOGIN_CORRETO = "admin"
SENHA_CORRETA = "asdf1234++"
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"

# Sessão para controle do modo administrador
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

# =====================
# 📄 Carrega a planilha salva localmente (última versão)
df = None
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)
    except:
        st.error("Erro ao ler a planilha salva.")
else:
    st.warning("Nenhuma planilha carregada ainda. Acesse a administração para carregar.")

# =====================
# 🔍 Tela pública de pesquisa
if df is not None:
    st.subheader("🔍 Pesquisa de Livros")
    coluna_busca = st.selectbox("Buscar por:", ["Título do Livro", "Autor", "codigo"])
    termo = st.text_input(f"Digite o termo para buscar em '{coluna_busca}'")

    import unicodedata

def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto)
                       if unicodedata.category(c) != 'Mn').lower()
    return texto

import unicodedata

def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto)
                       if unicodedata.category(c) != 'Mn').lower()
    return texto

if termo:
    termo_normalizado = remover_acentos(termo)
    resultado = df[df[coluna_busca].astype(str).apply(remover_acentos).str.contains(termo_normalizado, na=False)]
    st.write(f"🔎 {len(resultado)} resultado(s) encontrado(s):")
    st.dataframe(resultado)
else:
    st.write("📋 Todos os livros:")
    st.dataframe(df)


st.divider()

# =====================
# 🔒 Área de administração (acesso só após login)
with st.expander("🔐 Administrador"):
    if not st.session_state.modo_admin:
        with st.form("login_form"):
            st.write("Área restrita para administradores.")
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar")

            if entrar:
                if usuario == LOGIN_CORRETO and senha == SENHA_CORRETA:
                    st.success("Login realizado com sucesso.")
                    st.session_state.modo_admin = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    else:
        # ✅ Área visível só para admin após login
        st.subheader("🛠️ Upload de nova planilha")
        arquivo_novo = st.file_uploader("Carregar planilha .xlsx", type=["xlsx"])
        if arquivo_novo:
            try:
                df_novo = pd.read_excel(arquivo_novo)
                if not all(col in df_novo.columns for col in ["codigo", "Título do Livro", "Autor"]):
                    st.error("A planilha deve conter as colunas: 'codigo', 'Título do Livro' e 'Autor'")
                else:
                    df_novo.to_excel(ARQUIVO_PLANILHA, index=False)
                    st.success("Planilha atualizada com sucesso!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")

        # ✅ Botão de download — SÓ aparece após login
        st.subheader("📤 Baixar planilha atual")
        if df is not None:
            import io
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)
            st.download_button(
                label="📥 Baixar planilha",
                data=buffer,
                file_name="planilha_biblioteca_backup.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Nenhuma planilha disponível para download.")

