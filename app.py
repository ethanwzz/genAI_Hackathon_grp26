import streamlit as st
from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient
import fitz  # PyMuPDF
import io

# ──────────────────────────────
# 📄 Configuration de la page
# ──────────────────────────────
st.set_page_config(page_title="Chat IA PDF Azure", layout="wide")

# ──────────────────────────────
# Azure OpenAI
# ──────────────────────────────
client = AzureOpenAI(
    api_key=st.secrets["AZURE_OPENAI_KEY"],
    api_version="2023-12-01-preview",
    azure_endpoint=st.secrets["AZURE_OPENAI_ENDPOINT"]
)
DEPLOYMENT_NAME = st.secrets["AZURE_OPENAI_DEPLOYMENT"]

# ──────────────────────────────
# Azure Blob
# ──────────────────────────────
blob_service_client = BlobServiceClient.from_connection_string(st.secrets["AZURE_BLOB_CONNECTION_STRING"])
container_client = blob_service_client.get_container_client(st.secrets["AZURE_BLOB_CONTAINER_NAME"])

# ──────────────────────────────
# Fonction : extraire texte d'un PDF du blob
# ──────────────────────────────
def extract_text_from_blob_pdf(blob_client):
    pdf_bytes = blob_client.download_blob().readall()
    pdf_stream = io.BytesIO(pdf_bytes)
    text = ""
    with fitz.open(stream=pdf_stream, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

# ──────────────────────────────
# Barre latérale : Upload de PDF
# ──────────────────────────────
st.sidebar.markdown("### 📤 Uploader un nouveau PDF :")
uploaded_file = st.sidebar.file_uploader("Choisir un fichier PDF", type=["pdf"])

if uploaded_file is not None:
    blob_client = container_client.get_blob_client(uploaded_file.name)
    blob_client.upload_blob(uploaded_file.read(), overwrite=True)
    st.sidebar.success(f"✅ Fichier '{uploaded_file.name}' envoyé avec succès !")

    if st.sidebar.button("🔄 Recharger les documents"):
        st.experimental_rerun()

# ──────────────────────────────
# Lecture et extraction de tous les fichiers PDF
# ──────────────────────────────
pdf_contexts = []
st.sidebar.markdown("### 📄 PDF dans le conteneur :")
for blob in container_client.list_blobs():
    if blob.name.endswith(".pdf"):
        st.sidebar.write("•", blob.name)
        blob_client = container_client.get_blob_client(blob.name)
        try:
            pdf_text = extract_text_from_blob_pdf(blob_client)
            pdf_contexts.append(f"📄 **{blob.name}**\n{pdf_text.strip()}")
        except Exception as e:
            st.sidebar.error(f"Erreur sur {blob.name} : {str(e)}")

# Regrouper tous les contenus extraits
combined_context = "\n\n".join(pdf_contexts)

# ──────────────────────────────
# Interface principale du Chat
# ──────────────────────────────
st.title("🧠 Chat Azure OpenAI")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "Tu es un assistant IA. Réponds uniquement à partir des documents PDF fournis."},
        {"role": "user", "content": f"Voici les documents extraits depuis Azure Blob :\n\n{combined_context}"},
        {"role": "assistant", "content": "Merci. J’ai lu les documents. Pose-moi une question et je répondrai en m’appuyant sur leur contenu."}
    ]

# Affichage de la conversation (hors messages système/initiaux)
for msg in st.session_state.messages[3:]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# Entrée utilisateur
if prompt := st.chat_input("Pose ta question liée aux PDF..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("Réflexion en cours..."):
        response = client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=st.session_state.messages
        )
        reply = response.choices[0].message.content

    st.chat_message("assistant").markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
