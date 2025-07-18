import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from unidecode import unidecode
from datetime import datetime

# === CONFIGURAÇÕES ===

# ID da planilha Google Sheets que guarda os empréstimos.
# Substitua pelo ID real da sua planilha no Google Sheets.
ID_PLANILHA_EMPRESTIMOS = "COLOQUE_AQUI_O_ID_REAL_DA_PLANILHA_EMPRESTIMOS"

# Escopos de acesso para a API Google Sheets e Drive
SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# Carregamento das credenciais da conta de serviço armazenadas no st.secrets
credentials = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPE)
gc = gspread.authorize(credentials)

# === FUNÇÕES AUXILIARES ===

def remover_acentos(txt):
    return unidecode(str(txt)).lower()

# Carregar catálogo dos livros do arquivo Excel local
def carregar_livros():
    # O arquivo planilha_biblioteca.xlsx deve estar no mesmo diretório do app
    return pd.read_excel("planilha_biblioteca.xlsx")

# Carregar empréstimos da planilha Google Sheets
def carregar_emprestimos():
    try:
        planilha = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS)
        dados = planilha.sheet1.get_all_records()
        return pd.DataFrame(dados)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ Não foi possível encontrar a planilha de empréstimos no Google Sheets. "
                 "Verifique se o ID está correto e se a conta de serviço tem acesso.")
        return pd.DataFrame()  # Retorna DataFrame vazio para evitar que o app quebre

def atualizar_status_livros(df_livros, df_emprestimos):
    if df_emprestimos.empty:
        # Se não carregou empréstimos, mostra tudo disponível
        df_livros['Status'] = df_livros['Quantidade'].astype(str) + '/' + df_livros['Quantidade'].astype(str) + ' disponíveis'
        return df_livros

    df_emprestimos = df_emprestimos[df_emprestimos['Data de Devolução'] == '']
    status = df_emprestimos['Código do Livro'].value_counts()

    def status_livro(cod):
        total = df_livros[df_livros['Código'] == cod]['Quantidade'].values[0]
        emprestados = status.get(cod, 0)
        return f"{total - emprestados}/{total} disponíveis"

    df_livros['Status'] = df_livros['Código'].apply(status_livro)
    return df_livros

def registrar_emprestimo(nome_usuario, codigo_livro):
    df_livros = carregar_livros()
    df_livros['Código_upper'] = df_livros['Código'].str.upper()

    codigo_livro_upper = codigo_livro.strip().upper()

    if codigo_livro_upper not in df_livros['Código_upper'].values:
        st.error("❌ Código de livro não encontrado no catálogo.")
        return

    livro_info = df_livros[df_livros['Código_upper'] == codigo_livro_upper].iloc[0]
    codigo_real = livro_info['Código']
    total_exemplares = int(livro_info['Quantidade'])

    df_emprestimos = carregar_emprestimos()
    if df_emprestimos.empty:
        # Se não conseguiu carregar empréstimos, avisa e não registra
        st.error("❌ Não foi possível carregar a lista de empréstimos. Tente novamente mais tarde.")
        return

    emprestados = df_emprestimos[
        (df_emprestimos['Código do Livro'].str.upper() == codigo_livro_upper) &
        (df_emprestimos['Data de Devolução'] == '')
    ]
    
    if len(emprestados) >= total_exemplares:
        st.warning("⚠️ Todos os exemplares estão emprestados.")
        return

    planilha = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS)
    sheet = planilha.sheet1
    nova_linha = [datetime.now().strftime("%d/%m/%Y"), nome_usuario, codigo_real, ""]
    sheet.append_row(nova_linha)
    st.success("✅ Empréstimo registrado com sucesso!")

def registrar_devolucao(codigo_livro):
    df_emprestimos = carregar_emprestimos()
    if df_emprestimos.empty:
        st.error("❌ Não foi possível carregar a lista de empréstimos. Tente novamente mais tarde.")
        return

    codigo_livro_upper = codigo_livro.strip().upper()
    df_emprestimos['Código_upper'] = df_emprestimos['Código do Livro'].str.upper()
    idxs = df_emprestimos[
        (df_emprestimos['Código_upper'] == codigo_livro_upper) &
        (df_emprestimos['Data de Devolução'] == '')
    ].index

    if idxs.empty:
        st.warning("⚠️ Nenhum empréstimo ativo encontrado para este código.")
        return

    planilha = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS)
    sheet = planilha.sheet1
    for idx in idxs:
        cell_row = idx + 2  # Pular o cabeçalho da planilha
        sheet.update_cell(cell_row, 4, datetime.now().strftime("%d/%m/%Y"))
    st.success("📚 Devolução registrada com sucesso!")

# === LOGIN ===
def autenticar_usuario():
    with st.sidebar:
        st.subheader("🔐 Login")
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if user == st.secrets["admin_login"]["usuario"] and senha == st.secrets["admin_login"]["senha"]:
                st.session_state["autenticado"] = True
                st.experimental_rerun()
            else:
                st.error("Usuário ou senha inválidos.")

# === INTERFACE ===
st.set_page_config(page_title="📖 Biblioteca Comunitária", layout="centered")

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

st.title("📚 Biblioteca Casa da Esperança")

aba = st.sidebar.radio("Navegar", ["🔎 Buscar Livros", "👩‍💼 Administrador"])

# === ABA BUSCA ===
if aba == "🔎 Buscar Livros":
    df_livros = carregar_livros()
    df_emprestimos = carregar_emprestimos()
    df_livros = atualizar_status_livros(df_livros, df_emprestimos)

    termo = st.text_input("Buscar por título, autor ou código:")
    termo_proc = remover_acentos(termo)

    if termo:
        filtro = df_livros.apply(lambda row: termo_proc in remover_acentos(" ".join(map(str, row))), axis=1)
        resultados = df_livros[filtro]
        st.write(f"🔍 {len(resultados)} resultado(s) encontrado(s):")
        st.dataframe(resultados[["Título", "Autor", "Código", "Status"]])
    else:
        st.dataframe(df_livros[["Título", "Autor", "Código", "Status"]])

# === ABA ADMIN ===
elif aba == "👩‍💼 Administrador":
    if not st.session_state["autenticado"]:
        autenticar_usuario()
    else:
        st.success("✅ Acesso de administrador concedido.")
        acao = st.radio("Escolha a ação:", ["📥 Registrar Empréstimo", "📤 Registrar Devolução"])

        if acao == "📥 Registrar Empréstimo":
            nome_usuario = st.text_input("Nome do Usuário")
            codigo_livro = st.text_input("Código do Livro")
            if st.button("Registrar Empréstimo"):
                if nome_usuario and codigo_livro:
                    registrar_emprestimo(nome_usuario, codigo_livro)
                else:
                    st.warning("Preencha todos os campos.")

        elif acao == "📤 Registrar Devolução":
            codigo_livro = st.text_input("Código do Livro")
            if st.button("Registrar Devolução"):
                if codigo_livro:
                    registrar_devolucao(codigo_livro)
                else:
                    st.warning("Informe o código do livro.")
