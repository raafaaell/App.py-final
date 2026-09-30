import streamlit as st
import pandas as pd
from pypdf import PdfReader
import io
import re

from criterios import CRITERIOS_DIRETOS, padrao_termo

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Codificador de Instrumentos", layout="wide")

# O SEU DICIONÁRIO DE CRITÉRIOS (ver criterios.py)

def processar_texto_multiplas_categorias(paginas, nome_arquivo):
   """Procura cada termo página a página, como palavra inteira e no singular ou plural.
   O termo conta uma vez por arquivo, com a lista das páginas em que aparece."""
   # Normaliza quebras de linha e espaços do PDF para que termos longos sejam encontrados
   paginas = [re.sub(r"\s+", " ", texto).lower() for texto in paginas]
   registros = []
  
   for chave_categoria, palavras in CRITERIOS_DIRETOS.items():
       # Separa a condição e a categoria (ex: Substantivo e Tesouro)
       if " e " in chave_categoria:
           condicao, subcategoria = chave_categoria.split(" e ", 1)
       else:
           condicao, subcategoria = chave_categoria, "Geral"

       for palavra in palavras:
           padrao = padrao_termo(palavra)
           paginas_com_termo, formas_encontradas = [], set()
           for num, texto in enumerate(paginas, start=1):
               achados = {m.group(0) for m in padrao.finditer(texto)}
               if achados:
                   paginas_com_termo.append(num)
                   formas_encontradas |= achados
           if paginas_com_termo:
               registros.append({
                   "Arquivo": nome_arquivo,
                   "Condição": condicao.capitalize(),  
                   "Categoria": subcategoria.capitalize(),
                   "Termo Encontrado": palavra,
                   "Páginas": ", ".join(str(num) for num in paginas_com_termo),
                   "Formas Encontradas": ", ".join(sorted(formas_encontradas))
               })
   return registros

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
               # Mantém uma entrada por página (mesmo vazia) para a numeração bater com o PDF
               paginas = [p.extract_text() or "" for p in reader.pages]
              
               dados = processar_texto_multiplas_categorias(paginas, uploaded_file.name)
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

