import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import unicodedata

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# URL da planilha de livros (.xlsx) no GitHub
URL_PLANILHA_LIVROS = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/planilha_livros.xlsx"

# Função para normalizar strings
def normalizar(texto):
    if pd.isna(texto):
        return ""
    return unicodedata.normalize("NFKD", str(texto)).encode("ASCII", "ignore").decode("utf-8").lower().strip()

# Carregar planilha de livros do GitHub (.xlsx)
@st.cache_data
def carregar_livros():
    df = pd.read_excel(URL_PLANILHA_LIVROS)
    df["codigo"] = df["codigo"].astype(str)
    df["quantidade"] = df["quantidade"].fillna(0).astype(int)
    return df

# Autenticar com Google Sheets
@st.cache_resource
def autenticar_gsheets():
    escopos = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciais = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], escopos)
    cliente = gspread.authorize(credenciais)
    planilha = cliente.open_by_key(st.secrets["google_sheets_key"])
    aba = planilha.worksheet("emprestimos")
    return aba

# Carregar planilha de empréstimos
def carregar_emprestimos():
    aba = autenticar_gsheets()
    registros = aba.get_all_records()
    return pd.DataFrame(registros)

# Salvar novo empréstimo
def registrar_emprestimo(nome, codigo, titulo):
    aba = autenticar_gsheets()
    hoje = date.today().strftime("%d/%m/%Y")
    nova_linha = [nome, titulo, codigo, hoje, "", "emprestado"]
    aba.append_row(nova_linha)
    st.success("Empréstimo registrado com sucesso!")
    st.rerun()

# Interface de busca
st.subheader("🔎 Buscar livros")

df_livros = carregar_livros()
df_emprestimos = carregar_emprestimos()

filtro = st.selectbox("Buscar por:", ["Título", "Autor", "Código"])
busca = st.text_input("Digite sua busca:")

if busca:
    busca_normalizada = normalizar(busca)
    if filtro == "Título":
        resultado = df_livros[df_livros["Título do Livro"].apply(normalizar).str.contains(busca_normalizada)]
    elif filtro == "Autor":
        resultado = df_livros[df_livros["Autor"].apply(normalizar).str.contains(busca_normalizada)]
    else:
        resultado = df_livros[df_livros["codigo"].apply(normalizar).str.contains(busca_normalizada)]
else:
    resultado = df_livros.copy()

# Cálculo de empréstimos ativos
emprestimos_ativos = df_emprestimos[df_emprestimos["Situação"].str.lower() == "emprestado"]
emprestimos_por_codigo = emprestimos_ativos["Código"].str.lower().value_counts().to_dict()

# Mostrar resultados
for _, linha in resultado.iterrows():
    cod = str(linha["codigo"]).lower().strip()
    total = linha["quantidade"]
    emprestados = emprestimos_por_codigo.get(cod, 0)
    disponiveis = max(total - emprestados, 0)

    with st.expander(f"{linha['Título do Livro']}"):
        st.write(f"**Autor:** {linha['Autor']}")
        st.write(f"**Código:** {linha['codigo']}")
        st.write(f"**Situação:** {disponiveis}/{total} disponíveis")

# Interface de empréstimo
st.subheader("📥 Registrar Empréstimo")

with st.form("form_emprestimo"):
    nome = st.text_input("Nome do leitor")
    codigo_digitado = st.text_input("Código do livro")
    enviar = st.form_submit_button("Registrar empréstimo")

    if enviar:
        codigo_normalizado = normalizar(codigo_digitado)
        livro = df_livros[df_livros["codigo"].apply(normalizar) == codigo_normalizado]

        if not livro.empty:
            titulo_livro = livro.iloc[0]["Título do Livro"]
            total = int(livro.iloc[0]["quantidade"])
            emprestados = emprestimos_por_codigo.get(codigo_normalizado, 0)

            if emprestados < total:
                registrar_emprestimo(nome, codigo_digitado.strip(), titulo_livro)
            else:
                st.error("Não há exemplares disponíveis para empréstimo.")
        else:
            st.error("Código do livro inválido.")
