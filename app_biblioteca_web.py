import streamlit as st
import pandas as pd
import gspread
import io
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import requests

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# CONFIGURAÇÕES DO ADMIN
LOGIN_CORRETO = st.secrets["admin"]["login"]
SENHA_CORRETA = st.secrets["admin"]["senha"]

# PLANILHA LIVROS DO GITHUB (formato .xlsx)
URL_PLANILHA_LIVROS = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/planilha_livros.xlsx"

# GOOGLE SHEETS
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CRED_FILE = "credenciais.json"
PLANILHA_EMPRESTIMOS = "NOME_DA_PLANILHA"

def carregar_livros():
    try:
        resposta = requests.get(URL_PLANILHA_LIVROS)
        if resposta.status_code != 200:
            st.error("Erro ao carregar a planilha de livros do GitHub.")
            return None
        dados = resposta.content
        df = pd.read_excel(io.BytesIO(dados))
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar a planilha de livros: {e}")
        return None

def autenticar_google_sheets():
    try:
        credenciais = ServiceAccountCredentials.from_json_keyfile_name(CRED_FILE, SCOPE)
        cliente = gspread.authorize(credenciais)
        return cliente
    except Exception as e:
        st.error("Erro ao autenticar com o Google Sheets.")
        return None

def carregar_emprestimos():
    cliente = autenticar_google_sheets()
    if cliente:
        planilha = cliente.open(PLANILHA_EMPRESTIMOS)
        aba = planilha.sheet1
        dados = aba.get_all_records()
        return dados, aba
    return [], None

df = carregar_livros()
dados_emprestimos, worksheet = carregar_emprestimos()

st.sidebar.subheader("🔍 Buscar livro")
opcao_busca = st.sidebar.selectbox("Buscar por", ["Título", "Autor", "Código"])
entrada = st.sidebar.text_input(f"{opcao_busca}")

def filtrar_df(campo, texto):
    if df is None or campo not in df.columns:
        return pd.DataFrame()
    return df[df[campo].astype(str).str.lower().str.contains(texto.lower())]

if entrada:
    if opcao_busca == "Título":
        resultado = filtrar_df("Título do Livro", entrada)
    elif opcao_busca == "Autor":
        resultado = filtrar_df("Autor", entrada)
    else:
        resultado = filtrar_df("codigo", entrada)

    if not resultado.empty:
        st.write("### Resultados da busca:")
        for _, row in resultado.iterrows():
            codigo_livro = row['codigo']
            total = int(row['quantidade'])

            emprestimos_ativos = sum(
                1 for linha in dados_emprestimos
                if linha.get("Código do livro", "").strip().lower() == str(codigo_livro).lower()
                and linha.get("Situação", "").lower() == "emprestado"
                and not linha.get("Data de devolução")
            )
            disponivel = total - emprestimos_ativos
            st.markdown(f"**{row['Título do Livro']}**  \nAutor: {row['Autor']}  \nCódigo: `{codigo_livro}`  \n📦 Disponibilidade: `{disponivel}/{total}`")
            st.markdown("---")
    else:
        st.warning("Nenhum livro encontrado com esse termo.")

st.subheader("📋 Registrar Empréstimo")

def validar_codigo(codigo):
    return codigo.lower().strip() in df['codigo'].astype(str).str.lower().str.strip().values

with st.form("form_emprestimo"):
    nome_pessoa = st.text_input("Nome da pessoa")
    codigo_livro = st.text_input("Código do livro")
    data_emprestimo = st.date_input("Data do empréstimo", value=date.today())
    enviar = st.form_submit_button("Registrar Empréstimo")

    if enviar:
        if not nome_pessoa.strip():
            st.warning("Informe o nome da pessoa.")
        elif not validar_codigo(codigo_livro):
            st.warning("Código do livro inválido.")
        else:
            nome_livro = ""
            match = df[df["codigo"].astype(str).str.lower().str.strip() == codigo_livro.lower().strip()]
            if not match.empty:
                nome_livro = match.iloc[0]["Título do Livro"]

            if nome_livro == "":
                st.warning("Código de livro não encontrado.")
            else:
                nova_linha = [
                    nome_pessoa.strip(),
                    codigo_livro.strip(),
                    nome_livro,
                    str(data_emprestimo),
                    "",  # Data devolução
                    "Emprestado"
                ]
                try:
                    worksheet.append_row(nova_linha)

                    # Atualiza dados
                    dados_emprestimos, _ = carregar_emprestimos()
                    total = int(match.iloc[0]["quantidade"])

                    emprestimos_ativos = sum(
                        1 for linha in dados_emprestimos
                        if linha.get("Código do livro", "").strip().lower() == codigo_livro.lower().strip()
                        and linha.get("Situação", "").lower() == "emprestado"
                        and not linha.get("Data de devolução")
                    )
                    disponivel = total - emprestimos_ativos

                    st.success(f"✅ Empréstimo registrado com sucesso.")
                    st.info(f"📦 Disponibilidade atual para '{nome_livro}': {disponivel}/{total} disponíveis.")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Erro ao registrar o empréstimo: {e}")
