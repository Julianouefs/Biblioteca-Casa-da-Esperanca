import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime

# ----------------------
# Autenticação com Google Sheets (uso no Streamlit Cloud)
# ----------------------
try:
    creds_dict = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    client = gspread.authorize(creds)
except Exception as e:
    st.error("Erro ao autenticar com o Google Sheets.")
    st.stop()

# ----------------------
# IDs das planilhas
# ----------------------
ID_PLANILHA_LIVROS = st.secrets["id_planilha_livros"]
ID_PLANILHA_EMPRESTIMOS = st.secrets["id_planilha_emprestimos"]

# ----------------------
# Carregamento de dados
# ----------------------
def carregar_livros():
    try:
        sheet = client.open_by_key(ID_PLANILHA_LIVROS).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        st.error("\u274c Não foi possível carregar o catálogo de livros.")
        return pd.DataFrame()

def carregar_emprestimos():
    try:
        sheet = client.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception:
        st.error("\u274c Não foi possível carregar a lista de empréstimos. Tente novamente mais tarde.")
        return pd.DataFrame()

# ----------------------
# Tela de autenticação
# ----------------------
def autenticar_usuario():
    with st.form("login_form"):
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")

    if submit:
        if user == st.secrets["admin_login"]["usuario"] and senha == st.secrets["admin_login"]["senha"]:
            st.session_state["autenticado"] = True
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos.")

# ----------------------
# Registrar empréstimo
# ----------------------
def registrar_emprestimo():
    st.subheader("Registrar Empréstimo")
    df_livros = carregar_livros()
    if df_livros.empty:
        return

    with st.form("form_emprestimo"):
        codigo = st.text_input("Código do Livro").strip()
        nome_pessoa = st.text_input("Nome da Pessoa").strip()
        data_emprestimo = st.date_input("Data do Empréstimo", value=datetime.today())
        submit = st.form_submit_button("Registrar")

    if submit:
        df_livros["codigo_lower"] = df_livros["codigo"].str.lower()
        livro = df_livros[df_livros["codigo_lower"] == codigo.lower()]

        if not livro.empty:
            quantidade = int(livro.iloc[0]["quantidade"])
            if quantidade > 0:
                try:
                    sheet = client.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
                    sheet.append_row([codigo, nome_pessoa, data_emprestimo.strftime("%d/%m/%Y"), "emprestado"])
                    st.success("Empréstimo registrado com sucesso.")
                except:
                    st.error("Erro ao registrar o empréstimo.")
            else:
                st.warning("Não há exemplares disponíveis para este livro.")
        else:
            st.warning("Livro não encontrado.")

# ----------------------
# Consultar empréstimos
# ----------------------
def consultar_emprestimos():
    st.subheader("Livros Emprestados")
    df = carregar_emprestimos()
    if not df.empty:
        st.dataframe(df)

# ----------------------
# Início do app
# ----------------------
st.title("🏛️ Biblioteca Casa da Esperança")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    autenticar_usuario()
else:
    menu = st.sidebar.radio("Menu", ["Registrar Empréstimo", "Consultar Empréstimos", "Sair"])

    if menu == "Registrar Empréstimo":
        registrar_emprestimo()
    elif menu == "Consultar Empréstimos":
        consultar_emprestimos()
    elif menu == "Sair":
        st.session_state["autenticado"] = False
        st.experimental_rerun()
