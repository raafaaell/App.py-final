import streamlit as st
import altair as alt
import pandas as pd
from pypdf import PdfReader
import io
import re

from criterios import CRITERIOS_DIRETOS

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Codificador de Instrumentos", layout="wide")

# O SEU DICIONÁRIO DE CRITÉRIOS (ver criterios.py)

def processar_texto_multiplas_categorias(texto, nome_arquivo):
   """Sua lógica original de análise adaptada para o Streamlit"""
   # Normaliza quebras de linha e espaços do PDF para que termos longos sejam encontrados
   texto = re.sub(r"\s+", " ", texto).lower()
   registros = []
  
   for chave_categoria, palavras in CRITERIOS_DIRETOS.items():
       # Separa a condição e a categoria (ex: Substantivo e Tesouro)
       if " e " in chave_categoria:
           condicao, subcategoria = chave_categoria.split(" e ", 1)
       else:
           condicao, subcategoria = chave_categoria, "Geral"

       for palavra in palavras:
           contagem = texto.count(palavra.lower())
           if contagem > 0:
               registros.append({
                   "Arquivo": nome_arquivo,
                   "Condição": condicao.capitalize(),  
                   "Categoria": subcategoria.capitalize(),
                   "Termo Encontrado": palavra,
                   "Contagem": contagem
               })
   return registros

# --- GRÁFICOS ---
COR_BARRA = "#2a78d6"
CORES_CLASSE = {"Substantivo": "#2a78d6", "Procedimental": "#eb6834"}

def grafico_barras(resumo, campo, titulo):
   """Gráfico de barras horizontais com o total de cada valor de `campo`."""
   base = alt.Chart(resumo).encode(
       y=alt.Y(f"{campo}:N", sort="-x", title=None),
       x=alt.X("Total:Q", title="Termos identificados"),
       tooltip=[alt.Tooltip(f"{campo}:N"), alt.Tooltip("Total:Q")],
   )
   barras = base.mark_bar(color=COR_BARRA, cornerRadiusEnd=4, size=22)
   rotulos = base.mark_text(align="left", dx=4).encode(text="Total:Q")
   return (barras + rotulos).properties(title=titulo, height=alt.Step(34))

def grafico_cruzado(resumo_cruzado):
   """Barras agrupadas: tipos no eixo X, uma barra por classe em cada tipo."""
   base = alt.Chart(resumo_cruzado).encode(
       x=alt.X("Categoria:N", title="Tipo", axis=alt.Axis(labelAngle=0)),
       xOffset=alt.XOffset("Condição:N", sort=list(CORES_CLASSE)),
       y=alt.Y("Quantidade:Q", title="Termos identificados"),
       tooltip=[alt.Tooltip("Condição:N", title="Classe"),
                alt.Tooltip("Categoria:N", title="Tipo"),
                alt.Tooltip("Quantidade:Q")],
   )
   barras = base.mark_bar(cornerRadiusEnd=4, stroke="white", strokeWidth=2).encode(
       color=alt.Color("Condição:N", title="Classe",
                       scale=alt.Scale(domain=list(CORES_CLASSE), range=list(CORES_CLASSE.values())),
                       legend=alt.Legend(orient="top")),
   )
   rotulos = base.mark_text(dy=-6).encode(text="Quantidade:Q")
   return (barras + rotulos).properties(title="Classes × Tipos", height=320)

# --- INTERFACE VISUAL ---
st.title("Codificador de Instrumentos")
st.write("Selecione os arquivos PDF para codificar os instrumentos de acordo com a classe (substantivo ou procedimental) e o tipo (nodalidade, autoridade, tesouro ou organização).")
st.write("Ferramenta desenvolvida pelo Projeto Estruturante 4 - Entendendo as políticas públicas de forma abrangente e comparável: proposta de automatização da avaliação dos elementos do desenho de políticas do Instituto Nacional de Ciência e Tecnologia Qualidade de Governo e Políticas para o Desenvolvimento Sustentável (QualiGov).")
st.write("Desenvolvido por: Dr. Rafael Barbosa de Aguiar")
st.write("Validação das condições por: Dra. Luciana Leite Lima e Dr. Lizandro Lui")


# Seletor de arquivos
uploaded_files = st.file_uploader("Suba seus arquivos PDF aqui", type="pdf", accept_multiple_files=True)

if uploaded_files:
   if st.button("Iniciar Análise"):
       resultados_gerais = []
      
       # Barra de progresso visual
       progresso = st.progress(0)
      
       for i, uploaded_file in enumerate(uploaded_files):
           try:
               reader = PdfReader(uploaded_file)
               texto = " ".join([p.extract_text() for p in reader.pages if p.extract_text()])
              
               dados = processar_texto_multiplas_categorias(texto, uploaded_file.name)
               if dados:
                   resultados_gerais.extend(dados)
              
               progresso.progress((i + 1) / len(uploaded_files))
              
           except Exception as e:
               st.error(f"Erro ao ler {uploaded_file.name}: {e}")

       # --- EXIBIÇÃO DOS RESULTADOS ---
       if resultados_gerais:
           df = pd.DataFrame(resultados_gerais)
          
           st.divider()
           st.success(f"✅ Análise concluída! {len(df)} termos identificados no total.")

           # --- CÁLCULO DAS ESTATÍSTICAS ---
           # 1. Contagem por Condição (Substantivo vs Procedimental)
           resumo_condicao = df['Condição'].value_counts().reset_index()
           resumo_condicao.columns = ['Condição', 'Total']

           # 2. Contagem por Categoria (Nodalidade, Autoridade, Tesouro, Organização)
           resumo_categoria = df['Categoria'].value_counts().reset_index()
           resumo_categoria.columns = ['Tipo (Categoria)', 'Total']

           # 3. Contagem Cruzada (Matriz Condição x Categoria)
           resumo_cruzado = df.groupby(['Condição', 'Categoria']).size().reset_index(name='Quantidade')

           # --- EXIBIÇÃO NA TELA EM COLUNAS ---
           col1, col2, col3 = st.columns(3)

           with col1:
               st.subheader("Por Classe")
               st.dataframe(resumo_condicao, use_container_width=True, hide_index=True)

           with col2:
               st.subheader("Por Tipo")
               st.dataframe(resumo_categoria, use_container_width=True, hide_index=True)

           with col3:
               st.subheader("Cruzamento")
               st.dataframe(resumo_cruzado, use_container_width=True, hide_index=True)

           # --- GRÁFICOS ---
           st.divider()
           st.subheader("📊 Gráficos")

           graf1, graf2 = st.columns(2)
           with graf1:
               st.altair_chart(grafico_barras(resumo_condicao, "Condição", "Por Classe"), use_container_width=True)
           with graf2:
               st.altair_chart(grafico_barras(resumo_categoria, "Tipo (Categoria)", "Por Tipo"), use_container_width=True)

           st.altair_chart(grafico_cruzado(resumo_cruzado), use_container_width=True)

           # --- DOWNLOAD DO EXCEL ---
           st.divider()
           st.subheader("💾 Exportar Resultados")
           
           output = io.BytesIO()
           with pd.ExcelWriter(output, engine='openpyxl') as writer:
               df.to_excel(writer, sheet_name="Dados Detalhados", index=False)
               resumo_condicao.to_excel(writer, sheet_name="Resumo Condição", index=False)
               resumo_categoria.to_excel(writer, sheet_name="Resumo Tipos", index=False)
               resumo_cruzado.to_excel(writer, sheet_name="Matriz Cruzada", index=False)
          
           st.download_button(
               label="📥 Baixar Relatório Excel Completo",
               data=output.getvalue(),
               file_name="Relatorio_Codificacao_Instrumentos.xlsx",
               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
           )
           
           # Mostrar os dados brutos no final para conferência
           with st.expander("Ver lista completa de termos encontrados"):
               st.write(df)
       else:
           st.warning("Nenhum termo dos critérios foi encontrado nos arquivos enviados.")

