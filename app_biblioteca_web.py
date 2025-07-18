import streamlit as st
import pandas as pd
import unicodedata
import os
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import hashlib
import io

# Configuração da página
st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# Configurações de acesso admin via secrets.toml
LOGIN_CORRETO = st.secrets["admin"]["usuario"]
SENHA_CORRETA_HASH = hashlib.sha256(st.secrets["admin"]["senha"].encode()).hexdigest()
ID_PLANILHA_EMPRESTIMOS = st.secrets["google"]["planilha_emprestimos_id"]

# Nome do arquivo local da planilha de livros
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"

# --- Sessão para controle do modo administrador e tempo de login (30 min) ---
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

if st.session_state.get('login_time'):
    if datetime.now() - st.session_state.login_time > timedelta(minutes=30):
        st.session_state.modo_admin = False
        del st.session_state['login_time']
        st.warning("Sessão expirada. Faça login novamente.")

# --- Função para remover acentos (busca)
def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto)
                       if unicodedata.category(c) != 'Mn').lower()
    return texto

# --- Função para validar código do livro
def validar_codigo(codigo):
    # aceita letras com acento, números, espaço, hífen, barra, underline, ponto
    return re.match(r"^[\w\sÁ-ÿçÇ\-/_.]+$", codigo.strip(), re.UNICODE) is not None

# --- Carregar planilha local de livros (xlsx)
df = None
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)
        df["codigo"] = df["codigo"].astype(str).str.strip()
        df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0).astype(int)
    except:
        st.error("Erro ao ler a planilha salva.")
else:
    st.warning("Nenhuma planilha carregada ainda. Acesse a administração para carregar.")

# --- Se planilha carregada, conectar no Google Sheets para status de empréstimos
if df is not None:
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
        gc = gspread.authorize(credentials)
        worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
        dados_emprestimos = worksheet.get_all_records()

        # Códigos de exemplares emprestados (sem devolução)
        codigos_emprestados = {
            linha["Código do livro"].strip().lower()
            for linha in dados_emprestimos
            if linha.get("Situação", "").lower() == "emprestado" and not linha.get("Data de devolução")
        }

        # Contar empréstimos por código base (considera códigos que começam com o código do título)
        df["codigo_lower"] = df["codigo"].str.lower().str.strip()
        df["emprestados"] = df["codigo_lower"].apply(
            lambda cod: sum(1 for c in codigos_emprestados if c.startswith(cod))
        )
        df["disponiveis"] = df["quantidade"] - df["emprestados"]
        df["disponiveis"] = df["disponiveis"].apply(lambda x: x if x >= 0 else 0)

        # Coluna Situação: ex "1/2 disponíveis"
        df["Situação"] = df["disponiveis"].astype(str) + "/" + df["quantidade"].astype(str) + " disponíveis"

        # Resultado final (uma linha por título)
        df_resultado = df[["Título do Livro", "Autor", "codigo", "Situação"]]

    except Exception as e:
        st.error(f"Erro ao carregar situação dos livros: {e}")
        df_resultado = df[["Título do Livro", "Autor", "codigo"]]
        df_resultado["Situação"] = "Erro ao carregar"
else:
    df_resultado = pd.DataFrame(columns=["Título do Livro", "Autor", "codigo", "Situação"])

# --- Tela pública de busca
st.subheader("🔍 Buscar Livros")
busca = st.text_input("Digite parte do título, autor ou código do livro:")

if busca:
    termo = remover_acentos(busca)
    resultado = df_resultado[
        df_resultado.apply(lambda row:
            termo in remover_acentos(str(row["Título do Livro"])) or
            termo in remover_acentos(str(row["Autor"])) or
            termo in remover_acentos(str(row["codigo"])),
            axis=1)
    ]
    st.dataframe(resultado)
else:
    st.dataframe(df_resultado)

st.divider()

# --- Área administrativa ---
with st.expander("🔐 Administrador"):
    if not st.session_state.modo_admin:
        with st.form("login_form"):
            st.write("Área restrita para administradores.")
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar")

            if entrar:
                if usuario == LOGIN_CORRETO and hashlib.sha256(senha.encode()).hexdigest() == SENHA_CORRETA_HASH:
                    st.success("Login realizado com sucesso.")
                    st.session_state.modo_admin = True
                    st.session_state.login_time = datetime.now()
                    st.experimental_rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    else:
        # Upload nova planilha
        st.subheader("🛠️ Upload de nova planilha")
        arquivo_novo = st.file_uploader("Carregar planilha .xlsx", type=["xlsx"])
        if arquivo_novo:
            try:
                df_novo = pd.read_excel(arquivo_novo)
                # Validar colunas obrigatórias
                if not all(col in df_novo.columns for col in ["codigo", "Título do Livro", "Autor", "quantidade"]):
                    st.error("A planilha deve conter as colunas: 'codigo', 'Título do Livro', 'Autor' e 'quantidade'")
                else:
                    df_novo.to_excel(ARQUIVO_PLANILHA, index=False)
                    st.success("Planilha atualizada com sucesso!")
                    st.experimental_rerun()
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")

        # Download da planilha
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

        # Registro de empréstimos
        st.subheader("📘 Registro de Empréstimos")

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
                        # Verificar se há exemplares disponíveis antes de registrar
                        linha_livro = df[df["codigo"].astype(str).str.lower().str.strip() == codigo_livro.lower().strip()]
                        if not linha_livro.empty:
                            disponiveis = linha_livro.iloc[0]["disponiveis"]
                            if disponiveis <= 0:
                                st.warning(f"Não há exemplares disponíveis para o código '{codigo_livro}'.")
                            else:
                                nova_linha = [
                                    nome_pessoa.strip(),
                                    codigo_livro.strip(),
                                    nome_livro,
                                    str(data_emprestimo),
                                    "",  # data_devolucao vazia
                                    "Emprestado"
                                ]
                                try:
                                    worksheet.append_row(nova_linha)
                                    st.experimental_rerun()
                                    st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
                                    st.experimental_rerun()
                                except Exception as e:
                                    st.error(f"Erro ao registrar o empréstimo: {e}")
                        else:
                            st.warning("Erro ao localizar o livro para verificar disponibilidade.")
