import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
import io
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
from collections import Counter

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")

st.title("📚 Biblioteca Casa da Esperança")

LOGIN_CORRETO = st.secrets["login"]
SENHA_CORRETA = st.secrets["senha"]
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"

if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

def remover_acentos(texto):
    if isinstance(texto, str):
        return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()
    return texto

# Conexão com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["google_service_account"], scope)
gc = gspread.authorize(credentials)
ID_PLANILHA_EMPRESTIMOS = "1FE4kZWMCxC38giYc_xHy2PZCnq0GJgFlWUVY_htZ5do"
worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1

def obter_status_livros(planilha_livros):
    try:
        emprestimos = worksheet.get_all_records()
        total_por_codigo = Counter(l["codigo"] for l in planilha_livros)
        emprestados = Counter(e["codigo_livro"] for e in emprestimos if e["status"] == "Emprestado")
        status = {}
        for cod in total_por_codigo:
            disp = total_por_codigo[cod] - emprestados.get(cod, 0)
            status[cod] = f"{disp}/{total_por_codigo[cod]} disponíveis"
        return status
    except:
        return {}

# Carrega planilha local
df = None
if os.path.exists(ARQUIVO_PLANILHA):
    try:
        df = pd.read_excel(ARQUIVO_PLANILHA)
        status_map = obter_status_livros(df.to_dict(orient="records"))
        df["status"] = df["codigo"].astype(str).map(status_map)
    except:
        st.error("Erro ao ler a planilha salva.")
else:
    st.warning("Nenhuma planilha carregada ainda. Acesse a administração para carregar.")

# Busca pública
if df is not None:
    st.subheader("🔍 Pesquisa de Livros")
    coluna_busca = st.selectbox("Buscar por:", ["Título do Livro", "Autor", "codigo"])
    termo = st.text_input(f"Digite o termo para buscar em '{coluna_busca}'")

    if coluna_busca not in df.columns:
        st.error(f"Coluna '{coluna_busca}' não encontrada na planilha.")
    elif termo:
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
                if not all(col in df_novo.columns for col in ["codigo", "Título do Livro", "Autor"]):
                    st.error("A planilha deve conter as colunas: 'codigo', 'Título do Livro' e 'Autor'")
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
            st.download_button(
                label="📅 Baixar planilha",
                data=buffer,
                file_name="planilha_biblioteca_backup.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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
                        "",
                        "Emprestado"
                    ]
                    worksheet.append_row(nova_linha)
                    st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
                    st.rerun()

        st.subheader("📅 Baixa de Devolução")
        dados = worksheet.get_all_records()
        emprestimos_abertos = [l for l in dados if l["status"] == "Emprestado"]

        if emprestimos_abertos:
            opcoes = [f"{l['codigo_livro']} - {l['nome_livro']} ({l['nome_pessoa']})" for l in emprestimos_abertos]
            escolha = st.selectbox("Selecione um empréstimo para dar baixa:", opcoes)
            confirmar = st.button("Confirmar Devolução")

            if confirmar:
                index = opcoes.index(escolha)
                original = emprestimos_abertos[index]
                todas_linhas = worksheet.get_all_values()
                for i, l in enumerate(todas_linhas):
                    if i == 0:
                        continue
                    if (l[0] == original['nome_pessoa'] and
                        l[1] == original['codigo_livro'] and
                        l[2] == original['nome_livro'] and
                        l[5] == 'Emprestado'):
                        worksheet.update_cell(i+1, 5, str(date.today()))
                        worksheet.update_cell(i+1, 6, "Devolvido")
                        st.success("📗 Devolução registrada com sucesso.")
                        st.rerun()
                        break
        else:
            st.info("Nenhum empréstimo ativo encontrado.")

st.divider()
