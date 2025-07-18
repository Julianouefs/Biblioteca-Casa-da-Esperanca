import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ------------------ CONFIGURAÇÕES ------------------

# IDs das planilhas
ID_PLANILHA_LIVROS = "COLE AQUI O ID DA PLANILHA DE LIVROS"
ID_PLANILHA_EMPRESTIMOS = "COLE AQUI O ID DA PLANILHA DE EMPRÉSTIMOS"

# Escopos para acesso ao Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Autenticando com credenciais
@st.cache_resource

def conectar_gspread():
    try:
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error("Erro ao autenticar com o Google Sheets.")
        st.stop()

# ------------------ CARREGAMENTO DOS DADOS ------------------

@st.cache_data(ttl=300)
def carregar_livros():
    try:
        sh = conectar_gspread().open_by_key(ID_PLANILHA_LIVROS)
        worksheet = sh.sheet1
        dados = worksheet.get_all_records()
        return pd.DataFrame(dados)
    except:
        st.error("❌ Não foi possível carregar a lista de livros.")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def carregar_emprestimos():
    try:
        sh = conectar_gspread().open_by_key(ID_PLANILHA_EMPRESTIMOS)
        worksheet = sh.sheet1
        dados = worksheet.get_all_records()
        return pd.DataFrame(dados)
    except:
        st.error("❌ Não foi possível carregar a lista de empréstimos. Tente novamente mais tarde.")
        return pd.DataFrame()

# ------------------ INTERFACE DO USUÁRIO ------------------

def pagina_principal():
    st.title("📚 Biblioteca Casa da Esperança")
    st.write("Busque um livro ou registre um empréstimo")

    df_livros = carregar_livros()

    if df_livros.empty:
        st.warning("Nenhum livro encontrado.")
        return

    termo_busca = st.text_input("Buscar por título, autor ou código")
    if termo_busca:
        termo_busca = termo_busca.strip().lower()
        df_livros = df_livros[df_livros.apply(lambda row: termo_busca in str(row.values).lower(), axis=1)]

    if not df_livros.empty:
        st.dataframe(df_livros["Título Autor Código Status".split()])
    else:
        st.info("Nenhum livro encontrado com esse critério.")

# ------------------ LOGIN DO ADMINISTRADOR ------------------

def autenticar_usuario():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if st.session_state.autenticado:
        exibir_area_admin()
        return

    st.subheader("🔐 Login do administrador")
    user = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if (
            user == st.secrets["admin_login"]["usuario"]
            and senha == st.secrets["admin_login"]["senha"]
        ):
            st.session_state.autenticado = True
            st.success("✅ Login realizado com sucesso!")
        else:
            st.error("❌ Usuário ou senha inválidos.")

# ------------------ ÁREA ADMIN ------------------

def exibir_area_admin():
    st.header("🔧 Painel do Administrador")
    aba = st.radio("Escolha a opção:", ["Ver empréstimos", "Registrar novo empréstimo"])

    if aba == "Ver empréstimos":
        df = carregar_emprestimos()
        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("Nenhum empréstimo registrado.")

    elif aba == "Registrar novo empréstimo":
        st.subheader("📥 Registrar empréstimo")
        nome = st.text_input("Nome do leitor")
        codigo_livro = st.text_input("Código do livro")

        if st.button("Registrar"):
            if nome and codigo_livro:
                try:
                    sh = conectar_gspread().open_by_key(ID_PLANILHA_EMPRESTIMOS)
                    worksheet = sh.sheet1
                    data = datetime.now().strftime("%d/%m/%Y")
                    worksheet.append_row([nome, codigo_livro, data])
                    st.success("✅ Empréstimo registrado com sucesso!")
                except:
                    st.error("Erro ao registrar o empréstimo.")
            else:
                st.warning("Preencha todos os campos.")

# ------------------ EXECUÇÃO ------------------

menu = st.sidebar.selectbox("Menu", ["Início", "Admin"])
if menu == "Início":
    pagina_principal()
else:
    autenticar_usuario()
