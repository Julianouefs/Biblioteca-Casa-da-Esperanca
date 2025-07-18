import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
import io
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# Configurações do admin
LOGIN_CORRETO = st.secrets["login"]
SENHA_CORRETA = st.secrets["senha"]
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"

if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    return texto

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
gc = gspread.authorize(credentials)
ID_PLANILHA_EMPRESTIMOS = "1FE4kZWMCxC38giYc_xHy2PZCnq0GJgFlWUVY_htZ5do"
worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1

def obter_codigos_emprestados():
    try:
        dados = worksheet.get_all_records()
        contagem = {}
        for linha in dados:
            if linha["status"] == "Emprestado":
                cod = linha["codigo_livro"]
                contagem[cod] = contagem.get(cod, 0) + 1
        return contagem
    except:
        return {}

codigos_emprestados = obter_codigos_emprestados()

# Carrega planilha local
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)
        if "codigo" in df.columns and "quantidade" in df.columns:
            df["codigo"] = df["codigo"].astype(str)
            df["status"] = df.apply(lambda row: f"{row['quantidade'] - codigos_emprestados.get(str(row['codigo']), 0)}/{row['quantidade']} Disponível", axis=1)
        else:
            st.error("A planilha deve conter as colunas 'codigo', 'Título do Livro', 'Autor', e 'quantidade'")
            df = None
    except:
        df = None
        st.error("Erro ao ler a planilha local.")
else:
    df = None
    st.warning("Nenhuma planilha local encontrada.")

# Tela pública de busca
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

# Admin
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
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    else:
        st.subheader("🛠️ Upload de nova planilha")
        arquivo_novo = st.file_uploader("Carregar planilha .xlsx", type=["xlsx"])
        if arquivo_novo:
            try:
                df_novo = pd.read_excel(arquivo_novo)
                if not all(col in df_novo.columns for col in ["codigo", "Título do Livro", "Autor", "quantidade"]):
                    st.error("A planilha deve conter as colunas: 'codigo', 'Título do Livro', 'Autor', 'quantidade'")
                else:
                    df_novo.to_excel(ARQUIVO_PLANILHA, index=False)
                    st.success("Planilha atualizada com sucesso!")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")

        st.subheader("📄 Baixar planilha atual")
        if df is not None:
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)
            st.download_button("📥 Baixar planilha", data=buffer, file_name="planilha_biblioteca_backup.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # Registro de Empréstimos
        st.subheader("📘 Registro de Empréstimos")
        with st.form("form_emprestimo"):
            nome_pessoa = st.text_input("Nome da pessoa")
            codigo_livro = st.text_input("Código do livro")
            data_emprestimo = st.date_input("Data do empréstimo", value=date.today())
            enviar = st.form_submit_button("Registrar Empréstimo")

            if enviar:
                nome_livro = ""
                if df is not None and "codigo" in df.columns and "Título do Livro" in df.columns:
                    match = df[df["codigo"].astype(str) == codigo_livro.strip()]
                    if not match.empty:
                        nome_livro = match.iloc[0]["Título do Livro"]
                        quantidade_total = int(match.iloc[0]["quantidade"])

                        emprestimos_ativos = sum(
                            1 for linha in worksheet.get_all_records()
                            if linha["codigo_livro"] == codigo_livro.strip() and linha["status"] == "Emprestado"
                        )

                        if emprestimos_ativos >= quantidade_total:
                            st.warning(f"❌ Todos os exemplares de '{nome_livro}' já estão emprestados.")
                        elif not nome_pessoa.strip():
                            st.warning("Informe o nome da pessoa.")
                        else:
                            nova_linha = [
                                nome_pessoa.strip(),
                                codigo_livro.strip(),
                                nome_livro,
                                str(data_emprestimo),
                                "",
                                "Emprestado"
                            ]
                            worksheet.append_row(nova_linha)
                            st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
                            st.rerun()
                    else:
                        st.warning("Código de livro não encontrado na planilha principal.")

        # Baixa de Devolução
        st.subheader("📅 Baixa de Devolução")
        dados = worksheet.get_all_records()
        emprestimos_abertos = [linha for linha in dados if linha["status"] == "Emprestado"]

        if emprestimos_abertos:
            opcoes = [f"{linha['codigo_livro']} - {linha['nome_livro']} ({linha['nome_pessoa']})" for linha in emprestimos_abertos]
            escolha = st.selectbox("Selecione um empréstimo para dar baixa:", opcoes)
            confirmar = st.button("Confirmar Devolução")

            if confirmar:
                index = opcoes.index(escolha)
                linha_original = emprestimos_abertos[index]
                todas_linhas = worksheet.get_all_values()

                for i, linha in enumerate(todas_linhas):
                    if i == 0:
                        continue
                    if (linha[0] == linha_original['nome_pessoa'] and
                        linha[1] == linha_original['codigo_livro'] and
                        linha[2] == linha_original['nome_livro'] and
                        linha[5] == 'Emprestado'):
                        worksheet.update_cell(i+1, 5, str(date.today()))
                        worksheet.update_cell(i+1, 6, "Devolvido")
                        st.success("📗 Devolução registrada com sucesso.")
                        st.rerun()
                        break
        else:
            st.info("Nenhum empréstimo ativo encontrado.")

st.divider()
