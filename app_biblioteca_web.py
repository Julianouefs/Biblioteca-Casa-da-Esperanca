import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import hashlib
import re
import io

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# =====================
# 🔐 Segurança e autenticação
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

LOGIN_CORRETO = st.secrets["admin"]["usuario"]
SENHA_CORRETA_HASH = hash_senha(st.secrets["admin"]["senha"])
ID_PLANILHA_EMPRESTIMOS = st.secrets["google"]["planilha_emprestimos_id"]

# =====================
# Sessão admin
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

# Expiração de sessão após 30 minutos
if st.session_state.get('login_time'):
    if datetime.now() - st.session_state.login_time > timedelta(minutes=30):
        st.session_state.modo_admin = False
        del st.session_state['login_time']
        st.warning("Sessão expirada. Faça login novamente.")

# =====================
# 📄 Planilha local
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"
df = None
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)
    except:
        st.error("Erro ao ler a planilha salva.")
else:
    st.warning("Nenhuma planilha carregada ainda. Acesse a administração para carregar.")

# =====================
# Função para remover acentos
def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto)
                       if unicodedata.category(c) != 'Mn').lower()
    return texto

# =====================
# 🔍 Tela pública de pesquisa
if df is not None:
    st.subheader("🔍 Pesquisa de Livros")
    coluna_busca = st.selectbox("Buscar por:", ["Título do Livro", "Autor", "codigo"])
    termo = st.text_input(f"Digite o termo para buscar em '{coluna_busca}'")

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
# 🔒 Área de administração
with st.expander("🔐 Administrador"):
    if not st.session_state.modo_admin:
        with st.form("login_form"):
            st.write("Área restrita para administradores.")
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar")

            if entrar:
                if usuario == LOGIN_CORRETO and hash_senha(senha) == SENHA_CORRETA_HASH:
                    st.success("Login realizado com sucesso.")
                    st.session_state.modo_admin = True
                    st.session_state.login_time = datetime.now()
                    st.experimental_rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    else:
        # ✅ Área visível só para admin
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
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")

        # 📤 Botão de download
        st.subheader("📤 Baixar planilha atual")
        if df is not None:
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

        # =====================
        # 📘 Registro de Empréstimos
        st.subheader("📘 Registro de Empréstimos")

        # Conecta ao Google Sheets
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
        gc = gspread.authorize(credentials)
        worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1

        # Validação
        def validar_codigo(codigo):
            # Permite letras (com ou sem acento), números, espaços e os símbolos - / . _
            return re.match(r"^[\w\sÁ-ÿçÇ\-/_.]+$", codigo.strip(), re.UNICODE) is not None


        with st.form("form_emprestimo"):
            nome_pessoa = st.text_input("Nome da pessoa")
            codigo_livro = st.text_input("Código do livro")
            data_emprestimo = st.date_input("Data do empréstimo")
            enviar = st.form_submit_button("Registrar Empréstimo")

            if enviar:
                if not nome_pessoa.strip():
                    st.warning("Informe o nome da pessoa.")
                elif not validar_codigo(codigo_livro):
                    st.warning("Código do livro inválido.")
                else:
                    nome_livro = ""
                    if df is not None and "codigo" in df.columns and "Título do Livro" in df.columns:
                        match = df[df["codigo"].astype(str).str.lower().str.strip() == codigo_livro.lower().strip()]
                        if not match.empty:
                            nome_livro = match.iloc[0]["Título do Livro"]

                    if nome_livro == "":
                        st.warning("Código de livro não encontrado na planilha principal.")
                    else:
                        nova_linha = [
                            nome_pessoa.strip(),
                            codigo_livro.strip(),
                            nome_livro,
                            str(data_emprestimo),
                            "",  # data_devolucao
                            "Emprestado"
                        ]
                        worksheet.append_row(nova_linha)
                        st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
