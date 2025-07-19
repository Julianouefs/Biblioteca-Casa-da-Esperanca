import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# Configurações do admin
LOGIN_CORRETO = st.secrets["admin_login"]
SENHA_CORRETA = st.secrets["admin_senha"]
ID_PLANILHA_EMPRESTIMOS = st.secrets["id_planilha_emprestimos"]
ARQUIVO_PLANILHA = "planilha_livros.xlsx"  # deve estar no mesmo diretório do app

# Função para normalizar strings (ignorar acentos, caixa)
def normalizar(texto):
    return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('ASCII').strip().lower()

# Carrega planilha de livros
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)

        # Verifica situação atual com base nos empréstimos
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                st.secrets["google_service_account"], scope
            )
            gc = gspread.authorize(credentials)
            worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
            dados_emprestimos = worksheet.get_all_records()

            codigos_emprestados = {}
            for linha in dados_emprestimos:
                codigo = str(linha.get("Código do livro", "")).strip().lower()
                situacao = linha.get("Situação", "").strip().lower()
                devolucao = str(linha.get("Data de devolução", "")).strip()

                if situacao == "emprestado" and devolucao == "":
                    codigos_emprestados[codigo] = codigos_emprestados.get(codigo, 0) + 1

            def calcular_disponiveis(row):
                cod = str(row["codigo"]).strip().lower()
                total = int(row.get("quantidade", 1))
                emprestados = codigos_emprestados.get(cod, 0)
                disponiveis = max(0, total - emprestados)
                return f"{disponiveis}/{total} disponíveis"

            df["Situação"] = df.apply(calcular_disponiveis, axis=1)

        except Exception as e:
            st.error(f"Erro ao verificar situação dos livros: {e}")

    except Exception as e:
        st.error(f"Erro ao ler a planilha salva: {e}")
else:
    st.warning("Arquivo da planilha de livros não encontrado.")
    st.stop()

# Interface de busca
st.subheader("🔍 Buscar livros")
coluna_busca = st.selectbox("Buscar por:", ["Título do Livro", "Autor", "codigo"])
texto_busca = st.text_input("Digite o termo de busca:")

if texto_busca:
    resultado = df[df[coluna_busca].apply(lambda x: texto_busca.lower() in str(x).lower())]
else:
    resultado = df.copy()

st.dataframe(resultado[["Título do Livro", "Autor", "codigo", "Situação"]])

# Interface para registrar empréstimo
st.subheader("✍️ Registrar empréstimo")
codigo_inserido = st.text_input("Digite o código do livro:")
nome_pessoa = st.text_input("Nome da pessoa:")
enviar = st.button("Registrar empréstimo")

if enviar:
    if not codigo_inserido or not nome_pessoa:
        st.warning("Preencha todos os campos.")
    else:
        codigo_normalizado = normalizar(codigo_inserido)
        df["codigo_normalizado"] = df["codigo"].apply(normalizar)

        if codigo_normalizado not in df["codigo_normalizado"].values:
            st.error("Código do livro inválido.")
        else:
            nome_livro = df[df["codigo_normalizado"] == codigo_normalizado]["Título do Livro"].values[0]
            hoje = date.today().strftime("%d/%m/%Y")
            nova_linha = [nome_pessoa, nome_livro, codigo_inserido, hoje, "", "emprestado"]

            try:
                worksheet.append_row(nova_linha)
                st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro ao registrar o empréstimo: {e}")
