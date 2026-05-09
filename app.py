import streamlit as st
import pymongo
from google import genai
from google.genai import types

# =======================
# CONFIG
# =======================

GOOGLE_API_KEY = "TU_API_KEY"
MONGODB_URI = "TU_MONGO_URI"

client_genai = genai.Client(api_key=GOOGLE_API_KEY)
client_mongo = pymongo.MongoClient(MONGODB_URI)

db = client_mongo.pdf_embeddings_dbADR
collection = db.pdf_vectors

# =======================
# EMBEDDINGS
# =======================

def crear_embedding(texto, tipo="RETRIEVAL_QUERY"):
    try:
        response = client_genai.models.embed_content(
            model="gemini-embedding-001",
            contents=texto,
            config=types.EmbedContentConfig(
                task_type=tipo
            ),
        )
        return response.embeddings[0].values
    except Exception as e:
        print("Error embedding:", e)
        return None

# =======================
# BUSQUEDA VECTORIAL
# =======================

def buscar_en_mongo(pregunta):
    emb = crear_embedding(pregunta)

    if emb is None:
        return []

    try:
        resultados = collection.aggregate([
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": emb,
                    "numCandidates": 50,
                    "limit": 5
                }
            }
        ])

        return [r["texto"] for r in resultados]

    except Exception as e:
        print("Error Mongo:", e)
        return []

# =======================
# 🧠 AGENTE (CEREBRO)
# =======================

def agente_responder(pregunta):
    # 1. Buscar contexto en Mongo
    contextos = buscar_en_mongo(pregunta)

    contexto = "\n".join(contextos)

    # 2. Construir prompt inteligente
    prompt = f"""
Eres un sommelier experto en bebidas de restaurante.

Tu trabajo:
- Responder preguntas del usuario
- Recomendar bebidas
- Usar SOLO la información del contexto

Si no encuentras la respuesta en el contexto:
di claramente "No tengo esa información en el menú"

====================
CONTEXTO:
{contexto}
====================

USUARIO:
{pregunta}
"""

    try:
        response = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:
        return f"Error IA: {e}"

# =======================
# UI
# =======================

st.set_page_config(layout="wide")
st.title("🍷 Verde & Vital - Sommelier IA")

# =======================
# ESTADO
# =======================

if "chat" not in st.session_state:
    st.session_state.chat = []

# =======================
# CHAT UI
# =======================

st.subheader("💬 Chat inteligente (con PDF + MongoDB)")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Ej: ¿qué vinos recomiendas?")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = agente_responder(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})
