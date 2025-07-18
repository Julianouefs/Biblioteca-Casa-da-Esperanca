import streamlit as st
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")

# URL do arquivo no GitHub
URL_PLANILHA_LIVROS = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/planilha_biblioteca.xlsx"

# ID da planilha de empréstimos no Google Sheets
ID_PLANILHA_EMPRESTIMOS = "1FE4kZWMCxC38giYc_xHy2PZCnq0GJgFlWUVY_htZ5do"

# Função para carregar a planilha de livros do GitHub
@st.cache_data
def carregar_livros():
    try:
        df = pd.read_excel(https://docs.google.com/spreadsheets/d/1FE4kZWMCxC38giYc_xHy2PZCnq0GJgFlWUVY_htZ5do/edit?gid=0#gid=0)
        df["codigo"] = df["codigo"].astype(str).str.lower()
        df["quantidade"] = df["quantidade"].fillna(0).astype(int)
        return df
    except Exception as e:
        st.error("❌ Erro ao carregar a lista de livros.")
        return pd.DataFrame()

# Função para autenticar e acessar a planilha de empréstimos
@st.cache_resource
def conectar_google_sheets():
    try:
        escopo = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credenciais = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], escopo
        )
        cliente = gspread.authorize(credenciais)
        planilha = cliente.open_by_key(ID_PLANILHA_EMPRESTIMOS)
        return planilha.worksheet("emprestimos")
    except Exception:
        st.error("❌ Erro ao autenticar com o Google Sheets.")
        return None

# Função para buscar os empréstimos
def carregar_emprestimos():
    aba = conectar_google_sheets()
    if aba:
        registros = aba.get_all_records()
        return pd.DataFrame(registros)
    return pd.DataFrame()

# Função para registrar empréstimo
def registrar_emprestimo(codigo, nome, data):
    aba = conectar_google_sheets()
    if aba:
        aba.append_row([codigo.lower(), nome, str(data), ""])
        st.success("✅ Empréstimo registrado com sucesso!")

# Função para registrar devolução
def registrar_devolucao(codigo, nome):
    aba = conectar_google_sheets()
    if aba:
        valores = aba.get_all_values()
        for i, linha in enumerate(valores[1:], start=2):  # pula o cabeçalho
            if linha[0].strip().lower() == codigo.lower() and linha[1].strip().lower() == nome.lower() and not linha[3]:
                aba.update_cell(i, 4, str(datetime.date.today()))
                st.success("✅ Devolução registrada!")
                return
        st.warning("⚠️ Empréstimo não encontrado ou já devolvido.")

# Função de login simples
def autenticar_usuario():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    with st.form("login"):
        st.write("🔐 Área do Administrador")
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

        if entrar:
            if user == st.secrets["admin_login"]["usuario"] and senha == st.secrets["admin_login"]["senha"]:
                st.session_state.autenticado = True
                st.success("✅ Login realizado com sucesso!")
                st.experimental_rerun()
            else:
                st.error("❌ Usuário ou senha incorretos.")

# Interface Principal
def main():
    st.title("📚 Biblioteca Casa da Esperança")

    menu = ["Buscar Livros", "Registrar Empréstimo", "Registrar Devolução", "Administrador"]
    escolha = st.sidebar.selectbox("Menu", menu)

    df_livros = carregar_livros()
    df_emprestimos = carregar_emprestimos()

    if escolha == "Buscar Livros":
        st.subheader("🔎 Buscar Livro")
        busca = st.text_input("Digite o título ou código do livro").strip().lower()
        if busca:
            resultado = df_livros[df_livros["codigo"].str.contains(busca) | df_livros["Título do Livro"].str.lower().str.contains(busca)]
            for _, row in resultado.iterrows():
                num_emprestimos = df_emprestimos[(df_emprestimos["Código"].str.lower() == row["codigo"]) & (df_emprestimos["Data da Devolução"] == "")].shape[0]
                disponivel = row["quantidade"] - num_emprestimos
                status = "Disponível" if disponivel > 0 else "Emprestado"
                st.markdown(f"""
                    **📘 Título:** {row['Título do Livro']}  
                    **✍️ Autor:** {row['Autor']}  
                    **🔢 Código:** `{row['codigo']}`  
                    **📦 Quantidade:** {row['quantidade']}  
                    **📌 Status:** :{'green' if status == "Disponível" else 'red'}[{status}]
                    ---
                """)

    elif escolha == "Registrar Empréstimo":
        st.subheader("📥 Registrar Empréstimo")
        codigo = st.text_input("Código do Livro")
        nome = st.text_input("Nome do Usuário")
        data = st.date_input("Data do Empréstimo", value=datetime.date.today())
        if st.button("Registrar"):
            if codigo and nome:
                registrar_emprestimo(codigo, nome, data)
            else:
                st.warning("Preencha todos os campos.")

    elif escolha == "Registrar Devolução":
        st.subheader("📤 Registrar Devolução")
        codigo = st.text_input("Código do Livro para devolução")
        nome = st.text_input("Nome do Usuário que fez o empréstimo")
        if st.button("Confirmar Devolução"):
            if codigo and nome:
                registrar_devolucao(codigo, nome)
            else:
                st.warning("Preencha todos os campos.")

    elif escolha == "Administrador":
        if not st.session_state.get("autenticado", False):
            autenticar_usuario()
        else:
            st.success("Bem-vindo, administrador!")
            st.dataframe(df_emprestimos)

# Execução do app
if __name__ == "__main__":
    main()
