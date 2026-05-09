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
# EMBEDDING (QUERY)
# =======================

def crear_embedding(texto):
    try:
        response = client_genai.models.embed_content(
            model="gemini-embedding-001",
            contents=texto,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY"
            ),
        )
        return response.embeddings[0].values
    except Exception as e:
        print("Error embedding:", e)
        return None

# =======================
# BUSCAR EN MONGO (RAG)
# =======================

def buscar_contexto(pregunta):
    emb = crear_embedding(pregunta)

    if emb is None:
        return ""

    try:
        resultados = collection.aggregate([
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": emb,
                    "numCandidates": 50,
                    "limit": 3
                }
            }
        ])

        textos = [r["texto"] for r in resultados]
        return "\n".join(textos)

    except Exception as e:
        print("Error Mongo:", e)
        return ""

# =======================
# CHAT IA (USA PDF)
# =======================

def responder_chat(msg):
    contexto = buscar_contexto(msg)

    if not contexto:
        return "No encontré información en el menú, pero puedo ayudarte con recomendaciones 🍷"

    prompt = f"""
Eres un sommelier experto en bebidas.

Responde SOLO usando la información del contexto.
Si no está en el contexto, di que no tienes esa información.

CONTEXTO:
{contexto}

PREGUNTA:
{msg}
"""

    try:
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return r.text
    except Exception as e:
        return f"Error IA: {e}"

# =======================
# UI
# =======================

st.set_page_config(layout="wide")
st.title("🍷 Verde & Vital")

st.markdown("""
<style>
.card {
    padding:20px;
    border-radius:15px;
    background:#111827;
    color:white;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)

# =======================
# MENÚ LOCAL (PEDIDOS)
# =======================

menu = [
    {"nombre": "IPA Verde", "precio": 17, "tipo": "cerveza"},
    {"nombre": "Vino Tinto Reserva", "precio": 25, "tipo": "vino"},
    {"nombre": "Whisky 12 años", "precio": 35, "tipo": "whisky"},
    {"nombre": "Mojito", "precio": 22, "tipo": "cocktail"},
]

# =======================
# ESTADO
# =======================

if "pedido" not in st.session_state:
    st.session_state.pedido = {"items": [], "edad": False}

if "chat" not in st.session_state:
    st.session_state.chat = []

# =======================
# SIDEBAR PEDIDO
# =======================

st.sidebar.title("🧾 Tu pedido")

total = 0
for item in st.session_state.pedido["items"]:
    subtotal = item["precio"]
    total += subtotal
    st.sidebar.write(f"{item['nombre']} — S/{subtotal}")

st.sidebar.write(f"**Total: S/{total}**")

if st.sidebar.button("Confirmar edad 🔞"):
    st.session_state.pedido["edad"] = True

# =======================
# MENÚ VISUAL
# =======================

cols = st.columns(len(menu))

for i, item in enumerate(menu):
    with cols[i]:
        st.markdown(f"""
        <div class="card">
        <h3>{item['nombre']}</h3>
        <p>S/ {item['precio']}</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Agregar", key=i):
            if not st.session_state.pedido["edad"]:
                st.warning("Confirma edad 🔞")
            else:
                st.session_state.pedido["items"].append(item)
                st.success("Agregado")

# =======================
# CHAT RAG
# =======================

st.divider()
st.subheader("💬 Sommelier IA")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Pregunta sobre bebidas...")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = responder_chat(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})
