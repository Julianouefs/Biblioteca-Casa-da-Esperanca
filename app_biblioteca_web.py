import streamlit as st
import pandas as pd
import os
import unicodedata
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import hashlib
import re
import io

st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# =====================
# 🔐 Segurança e autenticação
def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

LOGIN_CORRETO = st.secrets["admin"]["usuario"]
SENHA_CORRETA_HASH = hash_senha(st.secrets["admin"]["senha"])
ID_PLANILHA_EMPRESTIMOS = st.secrets["google"]["planilha_emprestimos_id"]

# =====================
# Sessão admin
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False

if st.session_state.get('login_time'):
    if datetime.now() - st.session_state.login_time > timedelta(minutes=30):
        st.session_state.modo_admin = False
        del st.session_state['login_time']
        st.warning("Sessão expirada. Faça login novamente.")

# =====================
# Função para carregar empréstimos do Google Sheets
def carregar_emprestimos():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["google_service_account"], scope
        )
        gc = gspread.authorize(credentials)
        worksheet = gc.open_by_key(ID_PLANILHA_EMPRESTIMOS).sheet1
        dados = worksheet.get_all_records()
        return dados, worksheet
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha de empréstimos: {e}")
        return [], None

# =====================
# 📄 Planilha local - lista de livros
ARQUIVO_PLANILHA = "planilha_biblioteca.xlsx"
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
# Carregar empréstimos e worksheet
dados_emprestimos, worksheet = carregar_emprestimos()

# =====================
# Calcular disponibilidade dinamicamente (sem salvar no Excel local)
if df is not None and dados_emprestimos:
    codigos_emprestados = [
        linha["Código do livro"].strip().lower()
        for linha in dados_emprestimos
        if linha.get("Situação", "").lower() == "emprestado"
        and not linha.get("Data de devolução")
    ]

    emprestimos_por_codigo = pd.Series(codigos_emprestados).value_counts().to_dict()

    def calcular_disponibilidade(row):
        total = int(row["quantidade"])
        emprestado = emprestimos_por_codigo.get(str(row["codigo"]).strip().lower(), 0)
        disponivel = total - emprestado
        return f"{disponivel}/{total} disponíveis"

    # Atualiza o DataFrame na memória só para exibição
    df["Situação"] = df.apply(calcular_disponibilidade, axis=1)

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
                if usuario == LOGIN_CORRETO and hash_senha(senha) == SENHA_CORRETA_HASH:
                    st.success("Login realizado com sucesso.")
                    st.session_state.modo_admin = True
                    st.session_state.login_time = datetime.now()
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
        else:
            st.info("Nenhuma planilha disponível para download.")

        # =====================
        # 📘 Registro de Empréstimos

        def validar_codigo(codigo):
            return re.match(r"^[\w\sÁ-ÿçÇ\-/_.]+$", codigo.strip(), re.UNICODE) is not None

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
                        nova_linha = [
                            nome_pessoa.strip(),
                            codigo_livro.strip(),
                            nome_livro,
                            str(data_emprestimo),
                            "",  # Data de devolução vazia
                            "Emprestado"
                        ]
                        try:
                            worksheet.append_row(nova_linha)
                            st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar o empréstimo: {e}")

        # =====================
        # 📗 Registro de Devoluções

        st.subheader("📗 Registrar Devolução")

        try:
            emprestimos_ativos = [linha for linha in dados_emprestimos
                                 if linha.get("Situação", "").lower() == "emprestado"
                                 and not linha.get("Data de devolução")]

            if not emprestimos_ativos:
                st.info("Nenhum empréstimo ativo para devolução.")
            else:
                opcoes = [
                    f"{i+1} - {linha['Nome da pessoa']} - {linha['Título do Livro']} (Código: {linha['Código do livro']}) - Empréstimo: {linha['Data do empréstimo']}"
                    for i, linha in enumerate(emprestimos_ativos)
                ]
                escolha = st.selectbox("Selecione o empréstimo para registrar devolução:", opcoes)

                if st.button("Registrar devolução"):
                    idx = opcoes.index(escolha)
                    linha_devolucao = emprestimos_ativos[idx]

                    all_records = worksheet.get_all_records()
                    linha_para_atualizar = None
                    for i, record in enumerate(all_records, start=2):  # Cabeçalho é linha 1
                        if (record["Nome da pessoa"] == linha_devolucao["Nome da pessoa"] and
                            record["Código do livro"].strip().lower() == linha_devolucao["Código do livro"].strip().lower() and
                            record["Data do empréstimo"] == linha_devolucao["Data do empréstimo"] and
                            (not record.get("Data de devolução"))):
                            linha_para_atualizar = i
                            break

                    if linha_para_atualizar is None:
                        st.error("Não foi possível localizar o empréstimo na planilha para atualizar.")
                    else:
                        data_hoje = datetime.now().strftime("%Y-%m-%d")
                        # Atualiza as colunas "Data de devolução" e "Situação"
                        worksheet.update_cell(linha_para_atualizar, worksheet.find("Data de devolução").col, data_hoje)
                        worksheet.update_cell(linha_para_atualizar, worksheet.find("Situação").col, "Devolvido")
                        st.success(f"Devolução registrada para '{linha_devolucao['Título do Livro']}' com data {data_hoje}.")
                        st.rerun()

        except Exception as e:
            st.error(f"Erro ao carregar dados para devolução: {e}")
