import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")

st.title("📚 Biblioteca Casa da Esperança")

# 🔐 Configurações do admin
LOGIN_CORRETO = "admin"
SENHA_CORRETA = "asdf1234++"
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"

# Sessão para controle do modo administrador
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

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
# Função para remover acentos
def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto)
                       if unicodedata.category(c) != 'Mn').lower()
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
# 🔒 Área de administração (acesso só após login)
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
        # ✅ Área visível só para admin após login
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

        # ✅ Botão de download — SÓ aparece após login
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

# =====================
# 📘 Controle de Empréstimos

st.subheader("📘 Registro de Empréstimos")

# 🔗 Conecta ao Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
gc = gspread.authorize(credentials)

# 📝 ID da planilha de empréstimos no Google Sheets
ID_PLANILHA_EMPRESTIMOS = "1FE4kZWMCxC38giYc_xHy2PZCnq0GJgFlWUVY_htZ5do"  # Substitua pelo seu ID real

# 📄 Abre a planilha de empréstimos
worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1

# 📤 Formulário de registro de novo empréstimo
with st.form("form_emprestimo"):
    nome_pessoa = st.text_input("Nome da pessoa")
    codigo_livro = st.text_input("Código do livro")
    data_emprestimo = st.date_input("Data do empréstimo")

    enviar = st.form_submit_button("Registrar Empréstimo")

    if enviar:
        # Busca nome do livro na planilha local
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
                "",  # data_devolucao vazia ao registrar empréstimo
                "Emprestado"
            ]
            worksheet.append_row(nova_linha)
            st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")

st.divider()
