import streamlit as st
from langchain_openai import ChatOpenAI
import PyPDF2  # Para leer PDFs
from docx import Document  # Para crear archivos Word
from docx.shared import Pt  # Para ajustar el tamaño del texto
from docx.enum.text import WD_ALIGN_PARAGRAPH  # Para alinear texto en celdas
import re  # Para preprocesamiento de texto
import os
from dotenv import load_dotenv

# Cargar variables desde el archivo .env
load_dotenv()
# Preprocesamiento del texto
def preprocess_text(text):
    """Limpia el texto eliminando caracteres extraños y líneas vacías."""
    text = re.sub(r'\s+', ' ', text)  # Elimina espacios múltiples
    text = re.sub(r'[^\w\s|]', '', text)  # Elimina caracteres no alfanuméricos excepto |
    return text.strip()

# Detectar tipo de documento
def detect_document_type(text):
    """Determina si el documento es PCAP, PPT o Desconocido."""
    if "PCAP" in text or "Pliego de Cláusulas Administrativas Particulares" in text:
        return "PCAP"
    elif "PPT" in text or "Pliego de Prescripciones Técnicas" in text:
        return "PPT"
    return "Desconocido"

# Dividir texto en fragmentos
def chunk_text(text, max_length=2000):
    """Divide el texto en fragmentos de longitud máxima."""
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]

# Crear encabezado para secciones
def add_section_header(doc, title):
    """Agrega un encabezado de sección al documento."""
    header = doc.add_paragraph()
    header.add_run(title).bold = True
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    header.style.font.size = Pt(14)

# Crear documento Word con tablas
def create_word_document_with_tables(response_text):
    """
    Crea un archivo Word a partir del texto generado por el chatbot.
    Detecta tablas en el texto y las formatea correctamente.
    """
    doc = Document()
    doc.add_heading("Resumen generado por Solutia", level=1)
    lines = response_text.split("\n")
    table_lines = []
    is_table = False

    for line in lines:
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
            doc.add_paragraph(line)

    if table_lines:
        add_table_to_document(doc, table_lines)

    doc_path = "resumen_generado.docx"
    doc.save(doc_path)
    return doc_path

def add_table_to_document(doc, table_lines):
    """Convierte líneas de texto en formato de tabla y las agrega al documento Word."""
    rows = [line.strip("|").split("|") for line in table_lines]
    table = doc.add_table(rows=1, cols=len(rows[0]))
    table.style = "Table Grid"
    header_cells = table.rows[0].cells
    for i, header in enumerate(rows[0]):
        header_cells[i].text = header.strip()
        header_cells[i].paragraphs[0].runs[0].font.bold = True
        header_cells[i].paragraphs[0].runs[0].font.size = Pt(11)
        header_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for row in rows[1:]:
        cells = table.add_row().cells
        for i, cell in enumerate(row):
            cells[i].text = cell.strip()

# Configuración del modelo
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY")
)
if "messages" not in st.session_state:
    st.session_state.messages = []

# Subir múltiples archivos
uploaded_files = st.file_uploader("Carga uno o más archivos PDF", type=["pdf"], accept_multiple_files=True)

# Procesar archivos subidos
pcap_text, ppt_text = "", ""

def extract_text_from_pdf(file):
    """Extrae texto de un archivo PDF página por página."""
    pdf_reader = PyPDF2.PdfReader(file)
    for page in pdf_reader.pages:
        yield page.extract_text()

if uploaded_files:
    with st.spinner("Procesando archivos..."):
        for uploaded_file in uploaded_files:
            current_file_content = []
            for page_text in extract_text_from_pdf(uploaded_file):
                current_file_content.append(page_text)
            file_text = "\n".join(current_file_content)
            
            # Asignar texto según el nombre del archivo
            if "PCAP" in uploaded_file.name.upper():
                pcap_text += preprocess_text(file_text)
            elif "PPT" in uploaded_file.name.upper():
                ppt_text += preprocess_text(file_text)
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

    input_for_model = f"Tipo de documento: {document_type}\nTexto procesado:\n{input_text[:2000]}\nPregunta: {prompt}"

    messages_for_model = [
        {
            "role": "system",
            "content": """Eres un chatbot AI útil, te llamas Solutia, tienes que hablar como si fueras un asistente, nunca reveles que eres un chatbot.
Rol
Eres un experto en análisis de documentos técnicos y generación de resúmenes estructurados para licitaciones públicas. Tienes años de experiencia analizando pliegos de prescripciones técnicas (PPT) y pliegos de cláusulas administrativas particulares (PCAP) de concursos públicos. Posees habilidades avanzadas para extraer y sintetizar la información más relevante de estos documentos, asegurando que los responsables de buscar licitaciones puedan tomar decisiones rápidamente.

Tarea
Tu objetivo es analizar los documentos adjuntos (PPT, PCAP o ambos) relacionados con un concurso público y generar los siguientes entregables:

Para el PPT: Un resumen claro y detallado de unas 500 palabras con toda la información del documento. Este resumen debe cubrir todos los aspectos clave descritos en el documento, limitándose a una página. La información debe presentarse de manera precisa y comprensible, destacando los puntos más relevantes y estructurándolos por temas.

Para el PCAP: Un resumen detallado de unas 1000 palabras que presente, en formato tabla, los siguientes datos:

Cómo acreditar la solvencia técnica y financiera (especificar si estas aparecen explícitas en el documento o, en su defecto, hacer referencia a los requisitos generales establecidos en la Ley de Contratos del Sector Público (LCSP)).
Los importes máximos de licitación por lote, sin IVA, si los hubiese.
Los criterios de adjudicación, diferenciando entre objetivos (cuantificables mediante fórmulas matemáticas) y subjetivos (juicios de valor), con una descripción detallada de cada uno.
Otros datos relevantes como el presupuesto base, plazos, y garantías si están especificados.
Generar este resumen en un documento Word, estructurando la información en una tabla profesional y clara para facilitar su uso.

Si se reciben ambos documentos, debes elaborar ambos resúmenes de forma independiente, respetando las especificaciones mencionadas para cada uno.

Detalles específicos
Debes garantizar que los resúmenes sean precisos, claros y estructurados, resaltando únicamente la información relevante para los encargados de buscar licitaciones.
Los resúmenes deben estar adaptados al formato solicitado (tabla para PCAP, texto corrido para PPT).
Si alguno de los parámetros clave no aparece en el documento recibido, debes indicarlo claramente en el resumen con una nota, haciendo referencia a las normativas aplicables si corresponde.
Contexto
Solutia es una empresa especializada en identificar y preparar documentación para concursos públicos mediante el uso de inteligencia artificial. Este bot tiene como objetivo optimizar la carga de trabajo de los responsables de licitaciones, proporcionándoles resúmenes estructurados y fáciles de interpretar que les permitan ahorrar tiempo y enfocarse en las oportunidades más relevantes.

Notas
Si el documento adjunto contiene tanto PPT como PCAP, debes generar ambos resúmenes, siguiendo las reglas mencionadas.
Si se adjunta solo uno de los documentos, enfócate únicamente en ese documento.
El formato del documento final debe ser claro y profesional, adecuado para uso interno en la empresa.
Indica cualquier dato que falte o no esté especificado en el documento, añadiendo notas o referencias a posibles normativas que puedan aplicar.
Asegúrate de mencionar cualquier detalle adicional encontrado en el documento que pueda ser relevante para la toma de decisiones.
"""
        },
        {"role": "user", "content": input_for_model},
    ]

    response = llm.invoke(messages_for_model).content
    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})

    if input_text != "No se detectó el tipo de documento solicitado o no se cargó.":
        doc_path = create_word_document_with_tables(response)
        with open(doc_path, "rb") as file:
            st.download_button(
                label=f"Descargar resumen {document_type} en Word",
                data=file,
                file_name=f"resumen_{document_type.lower()}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
