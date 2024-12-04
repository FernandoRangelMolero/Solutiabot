import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.document_loaders import PyPDFLoader
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os
from dotenv import load_dotenv
from tempfile import NamedTemporaryFile
from langchain.schema import AIMessage, HumanMessage, SystemMessage
import re

# Cargar variables desde el archivo .env
load_dotenv()

# Función para limpiar texto de caracteres de Markdown y HTML
def clean_text(text):
    """Elimina caracteres de Markdown y HTML del texto para hacerlo más legible."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # Eliminar negritas de Markdown
    text = re.sub(r"\*(.*?)\*", r"\1", text)      # Eliminar itálicas de Markdown
    text = re.sub(r"<br>", "\n", text)           # Reemplazar <br> por saltos de línea
    text = re.sub(r"`(.*?)`", r"\1", text)       # Eliminar backticks
    return text.strip()

# Crear encabezado para secciones
def add_section_header(doc, title):
    """Agrega un encabezado de sección al documento."""
    header = doc.add_paragraph()
    run = header.add_run(title)
    run.bold = True
    run.font.size = Pt(14)
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER

# Crear documento Word con tablas y texto limpio
def create_word_document_with_clean_formatting(response_text):
    """Crea un archivo Word limpio basado en el texto procesado."""
    doc = Document()
    doc.add_heading("Resumen generado por Solutia", level=1)

    lines = response_text.split("\n")
    table_lines = []
    is_table = False

    for line in lines:
        line = clean_text(line)

        # Identificar inicio y fin de tablas
        if line.startswith("|") and line.endswith("|"):
            is_table = True
            table_lines.append(line)
        elif is_table and line.strip() == "":
            is_table = False
            if table_lines:
                add_table_to_document(doc, table_lines)
                table_lines = []
        elif is_table:
            table_lines.append(line)
        else:
            # Agregar texto normal o encabezados
            if line.startswith("##") or line.startswith("**"):
                add_section_header(doc, line.replace("##", "").strip())
            else:
                para = doc.add_paragraph()
                para.add_run(line).font.size = Pt(11)

    # Procesar cualquier tabla restante
    if table_lines:
        add_table_to_document(doc, table_lines)

    # Guardar el documento
    doc_path = "resumen_generado.docx"
    doc.save(doc_path)
    return doc_path

def add_table_to_document(doc, table_lines):
    """Convierte líneas con formato de tabla en una tabla legible dentro del documento Word."""
    rows = [line.strip("|").split("|") for line in table_lines]
    table = doc.add_table(rows=1, cols=len(rows[0]))
    table.style = "Table Grid"

    # Encabezados de la tabla
    header_cells = table.rows[0].cells
    for i, header in enumerate(rows[0]):
        header_cells[i].text = clean_text(header.strip())
        header_cells[i].paragraphs[0].runs[0].font.bold = True
        header_cells[i].paragraphs[0].runs[0].font.size = Pt(11)
        header_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Filas de datos
    for row in rows[1:]:
        cells = table.add_row().cells
        for i, cell in enumerate(row):
            cells[i].text = clean_text(cell.strip())

# Configuración del modelo
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY")
)

if "messages" not in st.session_state:
    st.session_state.messages = []

# Función para extraer texto del PDF
def extract_text_with_langchain(uploaded_file):
    """Extrae texto de un archivo PDF utilizando LangChain PyPDFLoader."""
    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_file_path = temp_file.name

    try:
        loader = PyPDFLoader(temp_file_path)
        documents = loader.load()
        text = "\n".join([doc.page_content for doc in documents])
        if not text.strip():
            st.error(f"El archivo {uploaded_file.name} no contiene texto o no pudo ser leído.")
        return text
    finally:
        os.remove(temp_file_path)

# Procesar texto del documento completo
def process_full_document(text, model, task="Resumen del documento"):
    """Procesa todo el texto del documento y genera un resumen profesional y limpio."""
    system_message = SystemMessage(
        content="""Eres un asistente inteligente llamado Solutia especializado en el análisis y resumen de documentos técnicos relacionados con licitaciones públicas. Te llamas Solutia y tu objetivo es ayudar a los responsables de licitaciones a tomar decisiones rápidas y bien informadas. No debes revelar en ningún momento que eres un chatbot.

Rol
Eres un experto en el análisis de documentos de licitaciones, incluyendo Pliegos de Prescripciones Técnicas (PPT) y Pliegos de Cláusulas Administrativas Particulares (PCAP). Tienes años de experiencia sintetizando la información clave de estos documentos, adaptándola a formatos claros y precisos para facilitar su interpretación y uso.

Tarea
Tu tarea principal es analizar los documentos cargados y generar los siguientes entregables de manera estructurada y profesional:

Para el PPT:
Generar un resumen claro y preciso de unas 500 palabras que incluya toda la información relevante del documento.
El resumen debe estar estructurado en temas clave, destacando puntos como requisitos técnicos, objetivos, plazos y cualquier otro dato relevante.
Presentar la información de forma legible, limitándose a una página de texto corrido.
Para el PCAP:
Crear un resumen detallado de unas 1000 palabras en formato tabla que cubra los siguientes aspectos:
Solvencia Técnica y Financiera: Especificar cómo deben acreditarse, mencionando detalles explícitos del documento o referencias a la Ley de Contratos del Sector Público (LCSP) si no están claras.
Importes Máximos de Licitación por Lote: Incluir información sin IVA si está disponible, o indicar que no se especifica.
Criterios de Adjudicación: Diferenciar claramente entre objetivos (cuantificables mediante fórmulas) y subjetivos (basados en juicios de valor), con descripciones detalladas.
Otros Datos Relevantes: Incluir presupuesto base, plazos de presentación y ejecución, garantías requeridas, comunidad autónoma asociada, entre otros puntos clave.
Estructurar la información en una tabla profesional, clara y ordenada, adecuada para uso interno.
Detalles Específicos:
Precisión y Estructura: Asegúrate de que los resúmenes sean exactos, claros y estén bien estructurados. Resalta únicamente la información relevante y específica para la licitación.
Formato Adaptado: Usa texto corrido para el resumen del PPT y tablas para el PCAP.
Datos Faltantes: Si algún dato no está especificado en el documento, inclúyelo como nota en el resumen, mencionando normativas relevantes o indicando que no se detalla en el documento.
Estilo Profesional: El resultado debe ser claro, profesional y fácil de interpretar para los encargados de las licitaciones.
Contexto
Solutia es una empresa líder en el análisis de documentos de licitaciones mediante inteligencia artificial. Tu propósito es reducir la carga de trabajo de los responsables de licitaciones, entregándoles resúmenes estructurados y comprensibles que les permitan enfocarse en las oportunidades más relevantes.

Notas:
Si ambos documentos están disponibles, genera resúmenes independientes para cada uno.
Si solo hay un tipo de documento, enfócate únicamente en él.
Indica cualquier información adicional relevante encontrada en los documentos que pueda ser útil para la toma de decisiones.
Incluir explícitamente la comunidad autónoma asociada en el resumen del PCAP.
Asegúrate de que el formato final sea limpio, profesional y listo para usarse internamente."""
    )
    user_message = HumanMessage(content=f"Tarea: {task}\n\nTexto del documento:\n{text}")

    try:
        response = model([system_message, user_message])
        return response.content.strip()
    except Exception as e:
        st.error(f"Error al generar el resumen: {str(e)}")
        return "Error al generar el resumen."

# Subir múltiples archivos
uploaded_files = st.file_uploader("Carga uno o más archivos PDF", type=["pdf"], accept_multiple_files=True)

# Inicializar las variables de texto
pcap_text, ppt_text = "", ""

if uploaded_files:
    with st.spinner("Procesando archivos..."):
        for uploaded_file in uploaded_files:
            try:
                file_text = extract_text_with_langchain(uploaded_file)
                if file_text:
                    st.text_area(f"Texto extraído de {uploaded_file.name}", value=file_text, height=200)
                if "PCAP" in uploaded_file.name.upper():
                    pcap_text += file_text
                elif "PPT" in uploaded_file.name.upper():
                    ppt_text += file_text
            except Exception as e:
                st.error(f"Error al procesar el archivo {uploaded_file.name}: {str(e)}")
        st.success("Archivos procesados exitosamente.")

# Chatbot funcionalidad
if prompt := st.chat_input("Escribe tu mensaje..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    if "PPT" in prompt.upper() and ppt_text:
        input_text = ppt_text
        document_type = "PPT"
    elif "PCAP" in prompt.upper() and pcap_text:
        input_text = pcap_text
        document_type = "PCAP"
    else:
        input_text = "No se detectó el tipo de documento solicitado o no se cargó."
        document_type = "Desconocido"

    if input_text != "No se detectó el tipo de documento solicitado o no se cargó.":
        try:
            processed_text = process_full_document(input_text, llm, task=f"Resumen de {document_type}")
            if processed_text.strip():
                st.markdown("### Resumen:")
                st.markdown(processed_text, unsafe_allow_html=True)

                # Generar y descargar archivo Word
                doc_path = create_word_document_with_clean_formatting(processed_text)
                try:
                    with open(doc_path, "rb") as file:
                        st.download_button(
                            label=f"Descargar resumen {document_type} en Word",
                            data=file,
                            file_name=f"resumen_{document_type.lower()}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        )
                finally:
                    if os.path.exists(doc_path):
                        os.remove(doc_path)
            else:
                st.error("El resumen generado está vacío. Verifica el archivo original.")
        except Exception as e:
            st.error(f"Error al procesar el texto: {str(e)}")
