import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")

st.title("📚 Biblioteca Casa da Esperança")

# 🔐 Configurações do admin
LOGIN_CORRETO = "admin"
SENHA_CORRETA = "asdf1234++"
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"
ID_PLANILHA_EMPRESTIMOS = "1FE4kZWMCxC38giYc_xHy2PZCnq0GJgFlWUVY_htZ5do"  # Substitua pelo seu ID

# Sessão para controle do modo administrador
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

# =====================
# 🔗 Conecta ao Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
gc = gspread.authorize(credentials)
worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1

# =====================
# 📄 Carrega a planilha salva localmente (última versão)
df = None
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)
    except:
        st.error("Erro ao ler a planilha salva.")
else:
    st.warning("Nenhuma planilha carregada ainda. Acesse a administração para carregar.")

# =====================
# 📥 Carrega a planilha de empréstimos
df_emprestimos = pd.DataFrame(worksheet.get_all_records())

# =====================
# Adiciona coluna de status na planilha principal
if df is not None:
    df["Status"] = "Disponível"
    if not df_emprestimos.empty:
        codigos_emprestados = df_emprestimos[df_emprestimos["data_devolucao"] == ""]["codigo_livro"].astype(str).tolist()
        df["codigo"] = df["codigo"].astype(str)
        df.loc[df["codigo"].isin(codigos_emprestados), "Status"] = "Emprestado"

# =====================
# Função para remover acentos
def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
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
                if usuario == LOGIN_CORRETO and senha == SENHA_CORRETA:
                    st.success("Login realizado com sucesso.")
                    st.session_state.modo_admin = True
                    st.experimental_rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    else:
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

        st.subheader("📤 Baixar planilha atual")
        if df is not None:
            import io
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

        st.subheader("📘 Registro de Empréstimos")
        with st.form("form_emprestimo"):
            nome_pessoa = st.text_input("Nome da pessoa")
            codigo_livro = st.text_input("Código do livro")
            data_emprestimo = st.date_input("Data do empréstimo")

            enviar = st.form_submit_button("Registrar Empréstimo")

            if enviar:
                nome_livro = ""
                if df is not None and "codigo" in df.columns and "Título do Livro" in df.columns:
                    match = df[df["codigo"].astype(str) == codigo_livro.strip()]
                    if not match.empty:
                        nome_livro = match.iloc[0]["Título do Livro"]

                if nome_livro == "":
                    st.warning("Código de livro não encontrado na planilha principal.")
                elif not nome_pessoa.strip():
                    st.warning("Informe o nome da pessoa.")
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

        st.subheader("📗 Baixa de Devolução")
        codigos_em_aberto = df_emprestimos[df_emprestimos["data_devolucao"] == ""]

        if not codigos_em_aberto.empty:
            codigo_baixa = st.selectbox("Selecione um empréstimo para dar baixa:", codigos_em_aberto["codigo_livro"] + " - " + codigos_em_aberto["nome_pessoa"])
            if st.button("Confirmar Baixa de Devolução"):
                idx = codigos_em_aberto.index[codigos_em_aberto["codigo_livro"] == codigo_baixa.split(" - ")[0]]
                if not idx.empty:
                    worksheet.update_cell(idx[0] + 2, 5, datetime.today().strftime("%Y-%m-%d"))  # coluna E (data_devolucao)
                    worksheet.update_cell(idx[0] + 2, 6, "Devolvido")  # coluna F (status)
                    st.success("📗 Devolução registrada com sucesso. Atualize a página para ver a mudança.")
