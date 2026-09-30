import streamlit as st
import altair as alt
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
   Cada termo gera uma linha por arquivo, com o total de ocorrências e as páginas em que aparece."""
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
           paginas_com_termo, formas_encontradas, contagem = [], set(), 0
           for num, texto in enumerate(paginas, start=1):
               achados = [m.group(0) for m in padrao.finditer(texto)]
               if achados:
                   paginas_com_termo.append(num)
                   formas_encontradas.update(achados)
                   contagem += len(achados)
           if paginas_com_termo:
               registros.append({
                   "Arquivo": nome_arquivo,
                   "Condição": condicao.capitalize(),  
                   "Categoria": subcategoria.capitalize(),
                   "Termo Encontrado": palavra,
                   "Contagem": contagem,
                   "Páginas": ", ".join(str(num) for num in paginas_com_termo),
                   "Formas Encontradas": ", ".join(sorted(formas_encontradas))
               })
   return registros

# --- GRÁFICOS ---
# Paleta em tons terrosos, validada para daltonismo e contraste (skill dataviz);
# o texto nunca usa a cor da série.
CORES_CLASSE = {"Substantivo": "#4a650c", "Procedimental": "#d27543"}  # verde oliva · terracota
COR_BARRA = "#a8692c"  # damasco queimado
# Areia -> pêssego -> damasco -> terracota -> marrom (mais escuro = mais termos)
RAMPA_TERROSA = ["#f5e3cf", "#f0c9a6", "#eaab7e", "#e08c59", "#d27543", "#a95631", "#733820"]
ORDEM_TIPOS = ["Nodalidade", "Autoridade", "Tesouro", "Organização"]
COR_TEXTO = "#2f2a22"
COR_TEXTO_SECUNDARIO = "#6b5f50"
COR_GRADE = "#e8dfd0"
COR_FUNDO = "#faf6ef"
FONTE = '"Source Sans", "Source Sans Pro", sans-serif'

def estilizar(grafico):
   """Aplica o mesmo visual a todos os gráficos: grade leve, sem bordas, títulos à esquerda."""
   return (
       grafico.configure(background=COR_FUNDO, font=FONTE, padding={"left": 4, "right": 12, "top": 4, "bottom": 4})
       .configure_view(stroke=None)
       .configure_axis(labelColor=COR_TEXTO_SECUNDARIO, titleColor=COR_TEXTO_SECUNDARIO, labelFontSize=13,
                       titleFontSize=12, titleFontWeight="normal", gridColor=COR_GRADE, gridWidth=1,
                       domain=False, ticks=False, labelPadding=6)
       .configure_title(color=COR_TEXTO, fontSize=16, fontWeight=600, anchor="start", offset=14,
                        subtitleColor=COR_TEXTO_SECUNDARIO, subtitleFontSize=12, subtitlePadding=4)
       .configure_legend(labelColor=COR_TEXTO_SECUNDARIO, titleColor=COR_TEXTO_SECUNDARIO, labelFontSize=12,
                         titleFontSize=12, titleFontWeight="normal", symbolType="circle", symbolSize=110)
   )

def grafico_classes(resumo_condicao):
   """Barras horizontais por classe, na mesma cor usada para a classe nos outros gráficos."""
   dados = resumo_condicao.copy()
   dados["Percentual"] = dados["Total"] / dados["Total"].sum()
   dados["Rótulo"] = dados.apply(lambda l: f"{l['Total']}  ({l['Percentual']:.0%})", axis=1)
   base = alt.Chart(dados).encode(
       y=alt.Y("Condição:N", sort=list(CORES_CLASSE), title=None),
       x=alt.X("Total:Q", title=None, axis=alt.Axis(tickMinStep=1)),
       tooltip=[alt.Tooltip("Condição:N", title="Classe"), alt.Tooltip("Total:Q", title="Termos"),
                alt.Tooltip("Percentual:Q", format=".0%")],
   )
   barras = base.mark_bar(cornerRadiusEnd=4, size=24).encode(
       color=alt.Color("Condição:N", scale=alt.Scale(domain=list(CORES_CLASSE), range=list(CORES_CLASSE.values())),
                       legend=None),
   )
   rotulos = base.mark_text(align="left", dx=6, color=COR_TEXTO, fontSize=13).encode(text="Rótulo:N")
   return estilizar((barras + rotulos).properties(
       title=alt.Title("Por classe", subtitle="Termos identificados"), height=alt.Step(44)))

def grafico_tipos(resumo_categoria):
   """Barras horizontais por tipo, da maior para a menor."""
   base = alt.Chart(resumo_categoria).encode(
       y=alt.Y("Tipo (Categoria):N", sort="-x", title=None),
       x=alt.X("Total:Q", title=None, axis=alt.Axis(tickMinStep=1)),
       tooltip=[alt.Tooltip("Tipo (Categoria):N", title="Tipo"), alt.Tooltip("Total:Q", title="Termos")],
   )
   barras = base.mark_bar(color=COR_BARRA, cornerRadiusEnd=4, size=24)
   rotulos = base.mark_text(align="left", dx=6, color=COR_TEXTO, fontSize=13).encode(text="Total:Q")
   return estilizar((barras + rotulos).properties(
       title=alt.Title("Por tipo", subtitle="Termos identificados"), height=alt.Step(44)))

def matriz_completa(resumo_cruzado):
   """Todas as combinações Classe × Tipo, com zero onde não houve termo."""
   indice = pd.MultiIndex.from_product([list(CORES_CLASSE), ORDEM_TIPOS], names=["Condição", "Categoria"])
   return (resumo_cruzado.set_index(["Condição", "Categoria"])["Quantidade"]
           .reindex(indice, fill_value=0).reset_index())

def grafico_cruzado(resumo_cruzado):
   """Colunas agrupadas: tipos no eixo X, uma coluna por classe em cada tipo."""
   dados = matriz_completa(resumo_cruzado)
   # Folga acima da coluna mais alta para o rótulo não encostar na legenda
   teto = max(int(dados["Quantidade"].max()), 1) * 1.15
   base = alt.Chart(dados).encode(
       x=alt.X("Categoria:N", sort=ORDEM_TIPOS, title=None, axis=alt.Axis(labelAngle=0),
               scale=alt.Scale(paddingInner=0.25)),
       xOffset=alt.XOffset("Condição:N", sort=list(CORES_CLASSE), scale=alt.Scale(paddingInner=0.08)),
       y=alt.Y("Quantidade:Q", title=None, axis=alt.Axis(tickMinStep=1), scale=alt.Scale(domain=[0, teto], nice=False)),
       tooltip=[alt.Tooltip("Condição:N", title="Classe"), alt.Tooltip("Categoria:N", title="Tipo"),
                alt.Tooltip("Quantidade:Q", title="Termos")],
   )
   barras = base.mark_bar(cornerRadiusEnd=4).encode(
       color=alt.Color("Condição:N", title=None,
                       scale=alt.Scale(domain=list(CORES_CLASSE), range=list(CORES_CLASSE.values())),
                       legend=alt.Legend(orient="top", direction="horizontal", offset=4)),
   )
   rotulos = base.mark_text(dy=-8, color=COR_TEXTO, fontSize=12).encode(text="Quantidade:Q")
   return estilizar((barras + rotulos).properties(
       title=alt.Title("Classes × tipos", subtitle="Termos identificados em cada combinação"), height=300))

def grafico_mapa_calor(resumo_cruzado):
   """Mapa de calor Classe × Tipo: quanto mais escuro, mais termos."""
   dados = matriz_completa(resumo_cruzado)
   maximo = max(int(dados["Quantidade"].max()), 1)
   base = alt.Chart(dados).encode(
       x=alt.X("Categoria:N", sort=ORDEM_TIPOS, title=None, axis=alt.Axis(labelAngle=0, orient="top", grid=False, labelFontSize=12)),
       y=alt.Y("Condição:N", sort=list(CORES_CLASSE), title=None, axis=alt.Axis(grid=False)),
       tooltip=[alt.Tooltip("Condição:N", title="Classe"), alt.Tooltip("Categoria:N", title="Tipo"),
                alt.Tooltip("Quantidade:Q", title="Termos")],
   )
   celulas = base.mark_rect(cornerRadius=4, stroke=COR_FUNDO, strokeWidth=2).encode(
       color=alt.Color("Quantidade:Q", scale=alt.Scale(domain=[0, maximo], range=RAMPA_TERROSA), legend=None),
   )
   # Texto branco nas células escuras e preto nas claras, para manter o contraste
   rotulos = base.mark_text(fontSize=16, fontWeight=600).encode(
       text="Quantidade:Q",
       color=alt.condition(alt.datum.Quantidade > maximo * 0.7, alt.value("#ffffff"), alt.value(COR_TEXTO)),
   )
   return estilizar((celulas + rotulos).properties(
       title=alt.Title("Mapa de calor", subtitle="Mais escuro = mais termos"), height=alt.Step(64)))

def mostrar_resultados(df):
   """Cartões de números, tabelas de resumo, gráficos e exportação."""
   # --- CÁLCULO DAS ESTATÍSTICAS ---
   # 1. Contagem por Condição (Substantivo vs Procedimental)
   resumo_condicao = df['Condição'].value_counts().reset_index()
   resumo_condicao.columns = ['Condição', 'Total']

   # 2. Contagem por Categoria (Nodalidade, Autoridade, Tesouro, Organização)
   resumo_categoria = df['Categoria'].value_counts().reset_index()
   resumo_categoria.columns = ['Tipo (Categoria)', 'Total']

   # 3. Contagem Cruzada (Matriz Condição x Categoria)
   resumo_cruzado = df.groupby(['Condição', 'Categoria']).size().reset_index(name='Quantidade')

   # --- CARTÕES DE NÚMEROS ---
   total_termos = len(df)
   por_classe = df['Condição'].value_counts()
   tipo_principal = resumo_categoria.iloc[0]
   card1, card2, card3, card4, card5 = st.columns(5)
   card1.metric("Arquivos analisados", df['Arquivo'].nunique(), border=True)
   card2.metric("Termos identificados", total_termos, border=True)
   card3.metric("Ocorrências no texto", f"{int(df['Contagem'].sum()):,}".replace(",", "."), border=True)
   card4.metric("Substantivo · Procedimental",
                f"{por_classe.get('Substantivo', 0) / total_termos:.0%} · {por_classe.get('Procedimental', 0) / total_termos:.0%}",
                border=True)
   card5.metric("Tipo mais frequente", tipo_principal['Tipo (Categoria)'],
                help=f"{tipo_principal['Total']} termos ({tipo_principal['Total'] / total_termos:.0%})", border=True)

   # --- GRÁFICOS ---
   st.subheader("Gráficos")
   graf1, graf2 = st.columns(2, gap="large")
   with graf1:
       st.altair_chart(grafico_classes(resumo_condicao), use_container_width=True, theme=None)
   with graf2:
       st.altair_chart(grafico_tipos(resumo_categoria), use_container_width=True, theme=None)

   graf3, graf4 = st.columns([3, 2], gap="large")
   with graf3:
       st.altair_chart(grafico_cruzado(resumo_cruzado), use_container_width=True, theme=None)
   with graf4:
       st.altair_chart(grafico_mapa_calor(resumo_cruzado), use_container_width=True, theme=None)

   # --- TABELAS DE RESUMO ---
   st.subheader("Tabelas de resumo")
   col1, col2, col3 = st.columns(3)

   with col1:
       st.markdown("**Por Classe**")
       st.dataframe(resumo_condicao, use_container_width=True, hide_index=True)

   with col2:
       st.markdown("**Por Tipo**")
       st.dataframe(resumo_categoria, use_container_width=True, hide_index=True)

   with col3:
       st.markdown("**Cruzamento**")
       st.dataframe(resumo_cruzado, use_container_width=True, hide_index=True)

   # Mostrar os dados brutos para conferência
   with st.expander("Ver lista completa de termos encontrados"):
       st.dataframe(df, use_container_width=True, hide_index=True)

   # --- DOWNLOAD DO EXCEL ---
   output = io.BytesIO()
   with pd.ExcelWriter(output, engine='openpyxl') as writer:
       df.to_excel(writer, sheet_name="Dados Detalhados", index=False)
       resumo_condicao.to_excel(writer, sheet_name="Resumo Condição", index=False)
       resumo_categoria.to_excel(writer, sheet_name="Resumo Tipos", index=False)
       resumo_cruzado.to_excel(writer, sheet_name="Matriz Cruzada", index=False)

   st.download_button(
       label="Baixar relatório Excel completo",
       icon=":material/download:",
       data=output.getvalue(),
       file_name="Relatorio_Codificacao_Instrumentos.xlsx",
       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
       type="primary",
       on_click="ignore",  # baixar o arquivo não recarrega a página
   )

# --- INTERFACE VISUAL ---
st.title("Codificador de Instrumentos")
st.markdown("Selecione os arquivos PDF para codificar os instrumentos de acordo com a classe (substantivo ou procedimental) e o tipo (nodalidade, autoridade, tesouro ou organização).")

with st.container(border=True):
   st.caption("Ferramenta desenvolvida pelo Projeto Estruturante 4 - Entendendo as políticas públicas de forma abrangente e comparável: proposta de automatização da avaliação dos elementos do desenho de políticas do Instituto Nacional de Ciência e Tecnologia Qualidade de Governo e Políticas para o Desenvolvimento Sustentável (QualiGov).")
   st.caption("**Desenvolvido por:** Dr. Rafael Barbosa de Aguiar  \n**Validação das condições por:** Dra. Luciana Leite Lima e Dr. Lizandro Lui")

# Seletor de arquivos
uploaded_files = st.file_uploader("Suba seus arquivos PDF aqui", type="pdf", accept_multiple_files=True)

if uploaded_files:
   # Se os arquivos mudarem, o resultado anterior deixa de valer
   assinatura = tuple((f.name, f.size) for f in uploaded_files)
   if st.session_state.get("assinatura") != assinatura:
       st.session_state.pop("resultados", None)

   if st.button("Iniciar Análise", type="primary", icon=":material/play_arrow:"):
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

       progresso.empty()

       # Guarda o resultado na sessão para ele continuar na tela depois do download
       st.session_state["assinatura"] = assinatura
       st.session_state["resultados"] = pd.DataFrame(resultados_gerais)

   # --- EXIBIÇÃO DOS RESULTADOS ---
   if "resultados" in st.session_state:
       if not st.session_state["resultados"].empty:
           st.divider()
           mostrar_resultados(st.session_state["resultados"])
       else:
           st.warning("Nenhum termo dos critérios foi encontrado nos arquivos enviados.")
else:
   st.session_state.pop("resultados", None)
