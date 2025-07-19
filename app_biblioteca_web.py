import streamlit as st
import pandas as pd
import datetime
import gspread
import io
import os
import unicodedata
from oauth2client.service_account import ServiceAccountCredentials

# CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# Função para normalizar strings (remover acentos e deixar minúsculo)
def normalizar(texto):
    if isinstance(texto, str):
        return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower().strip()
    return texto

# URL da planilha de livros no GitHub
URL_PLANILHA_LIVROS = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/planilha_livros.xlsx"

# ID da planilha de empréstimos no Google Sheets
ID_PLANILHA_EMPRESTIMOS = "SEU_ID_DA_PLANILHA"

# Carregar planilha de livros do GitHub
@st.cache_data
def carregar_livros():
    df = pd.read_excel(URL_PLANILHA_LIVROS)
    df = df.dropna(subset=["codigo"]).copy()
    df["codigo"] = df["codigo"].astype(str).apply(normalizar)
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors='coerce').fillna(1).astype(int)
    return df

# Carregar registros de empréstimos do Google Sheets
def carregar_emprestimos():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["google_service_account"], scope
    )
    gc = gspread.authorize(credentials)
    worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
    dados = worksheet.get_all_records()
    return pd.DataFrame(dados)

# Registrar novo empréstimo no Google Sheets
def registrar_emprestimo(dados):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["google_service_account"], scope
    )
    gc = gspread.authorize(credentials)
    worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
    worksheet.append_row(dados)

# Interface
aba = st.sidebar.radio("Escolha uma opção", ["Buscar livro", "Registrar empréstimo"])

df_livros = carregar_livros()
df_emprestimos = carregar_emprestimos()

# Calcular situação dos livros
emprestimos_ativos = df_emprestimos[(df_emprestimos["Situação"].str.lower() == "emprestado") & (df_emprestimos["Data de devolução"] == "")]
codigos_emprestados = emprestimos_ativos["Código do livro"].str.lower().value_counts().to_dict()

def calcular_situacao(row):
    codigo = str(row["codigo"]).strip().lower()
    total = int(row["quantidade"])
    emprestados = codigos_emprestados.get(codigo, 0)
    disponiveis = max(0, total - emprestados)
    return f"{disponiveis}/{total} disponíveis"

df_livros["Situação"] = df_livros.apply(calcular_situacao, axis=1)

if aba == "Buscar livro":
    campo = st.selectbox("Buscar por", ["Título do Livro", "Autor", "codigo"])
    termo = st.text_input("Digite o termo de busca")

    if termo:
        termo_normalizado = normalizar(termo)
        df_filtrado = df_livros[df_livros[campo].astype(str).apply(normalizar).str.contains(termo_normalizado)]
        st.write(f"{len(df_filtrado)} resultado(s) encontrado(s):")
        st.dataframe(df_filtrado[["Título do Livro", "Autor", "codigo", "Situação"]])

elif aba == "Registrar empréstimo":
    st.subheader("Registrar novo empréstimo")
    nome = st.text_input("Nome do leitor")
    codigo = st.text_input("Código do livro")
    data_hoje = datetime.date.today().strftime("%d/%m/%Y")

    if st.button("Registrar"):
        if not nome or not codigo:
            st.warning("Preencha todos os campos.")
        else:
            codigo_normalizado = normalizar(codigo)
            livro_encontrado = df_livros[df_livros["codigo"] == codigo_normalizado]

            if livro_encontrado.empty:
                st.error("Código do livro inválido.")
            else:
                total = int(livro_encontrado.iloc[0]["quantidade"])
                emprestados = codigos_emprestados.get(codigo_normalizado, 0)
                if emprestados >= total:
                    st.error("Não há exemplares disponíveis para empréstimo.")
                else:
                    dados = [nome, codigo_normalizado, data_hoje, "", "emprestado"]
                    registrar_emprestimo(dados)
                    st.success("Empréstimo registrado com sucesso!")
