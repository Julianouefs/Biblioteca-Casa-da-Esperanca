import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import date
import unicodedata
import io
import requests

# CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Biblioteca Casa da Esperança", layout="centered")
st.title("📚 Biblioteca Casa da Esperança")

# URL do arquivo da planilha base de livros (GitHub)
URL_PLANILHA_LIVROS = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPOSITORIO/main/planilha_livros.xlsx"

# Função para normalizar e padronizar texto
def normalizar_texto(texto):
    return unicodedata.normalize("NFKD", str(texto).strip().lower()).encode("ASCII", "ignore").decode("utf-8")

# Carregar planilha de livros do GitHub (formato .xlsx)
@st.cache_data
def carregar_livros():
    try:
        resposta = requests.get(URL_PLANILHA_LIVROS)
        if resposta.status_code == 200:
            df = pd.read_excel(io.BytesIO(resposta.content))
            df.columns = df.columns.str.strip()
            return df
        else:
            st.error("Erro ao carregar a planilha de livros do GitHub.")
            return None
    except Exception as e:
        st.error(f"Erro ao carregar a planilha: {e}")
        return None

# Conectar à planilha de empréstimos no Google Sheets
def conectar_planilha_google():
    try:
        escopos = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        credenciais = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], escopos)
        cliente = gspread.authorize(credenciais)
        planilha = cliente.open_by_key(st.secrets["planilha_emprestimos_key"])
        aba = planilha.worksheet("Página1")
        return aba
    except Exception as e:
        st.error("Erro ao autenticar com o Google Sheets.")
        return None

# Carregar dados da planilha de empréstimos
def carregar_emprestimos():
    try:
        aba = conectar_planilha_google()
        if aba:
            registros = aba.get_all_records()
            return registros, aba
        return [], None
    except Exception as e:
        st.error(f"Erro ao carregar empréstimos: {e}")
        return [], None

# Validar código do livro
def validar_codigo(codigo):
    return isinstance(codigo, str) and codigo.strip() != ""

# ============================
# INÍCIO DA APLICAÇÃO
# ============================

df = carregar_livros()
dados_emprestimos, worksheet = carregar_emprestimos()

aba_busca = st.sidebar.selectbox("Escolha a opção", ["Buscar Livro", "Registrar Empréstimo"])

if aba_busca == "Buscar Livro":
    st.subheader("🔍 Buscar Livro")
    campo_busca = st.selectbox("Buscar por", ["Título", "Autor", "Código"])
    texto_busca = st.text_input("Digite o texto da busca:")

    if texto_busca:
        texto_busca_normalizado = normalizar_texto(texto_busca)

        if campo_busca == "Título":
            df_filtrado = df[df["Título do Livro"].apply(normalizar_texto).str.contains(texto_busca_normalizado)]
        elif campo_busca == "Autor":
            df_filtrado = df[df["Autor"].apply(normalizar_texto).str.contains(texto_busca_normalizado)]
        else:  # Código
            df_filtrado = df[df["codigo"].apply(str).str.lower().str.strip() == texto_busca_normalizado.strip()]

        if not df_filtrado.empty:
            for _, row in df_filtrado.iterrows():
                st.markdown(f"**Título:** {row['Título do Livro']}")
                st.markdown(f"**Autor:** {row['Autor']}")
                st.markdown(f"**Gênero:** {row['Gênero']}")
                st.markdown(f"**Código:** `{row['codigo']}`")

                # Cálculo da disponibilidade
                total = int(row["quantidade"])
                emprestados = sum(
                    1 for emprestimo in dados_emprestimos
                    if emprestimo.get("Código do livro", "").strip().lower() == str(row["codigo"]).strip().lower()
                    and emprestimo.get("Situação", "").lower() == "emprestado"
                    and not emprestimo.get("Data de devolução")
                )
                disponivel = total - emprestados
                st.markdown(f"**Disponibilidade:** {disponivel}/{total} disponíveis")
                st.markdown("---")
        else:
            st.warning("Nenhum livro encontrado com esse critério.")

elif aba_busca == "Registrar Empréstimo":
    st.subheader("📥 Registrar Empréstimo")

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
                        "",  # Data de devolução
                        "Emprestado"
                    ]
                    try:
                        worksheet.append_row(nova_linha)

                        # Recarregar os dados de empréstimos após salvar
                        dados_emprestimos, worksheet = carregar_emprestimos()

                        # Cálculo de disponibilidade atual
                        emprestimos_ativos = sum(
                            1 for linha in dados_emprestimos
                            if linha.get("Código do livro", "").strip().lower() == codigo_livro.lower().strip()
                            and linha.get("Situação", "").lower() == "emprestado"
                            and not linha.get("Data de devolução")
                        )
                        quantidade_total = int(match.iloc[0]["quantidade"])
                        disponivel = quantidade_total - emprestimos_ativos

                        st.success(f"✅ Empréstimo de '{nome_livro}' registrado com sucesso.")
                        st.info(f"Disponibilidade atual para o livro '{nome_livro}': {disponivel}/{quantidade_total} disponíveis.")

                        st.experimental_rerun()
                    except Exception as e:
                        st.error(f"Erro ao registrar o empréstimo: {e}")
