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
# EMBEDDING
# =======================

def crear_embedding(texto, tipo="RETRIEVAL_QUERY"):
    try:
        response = client_genai.models.embed_content(
            model="gemini-embedding-001",
            contents=texto,
            config=types.EmbedContentConfig(task_type=tipo),
        )
        return response.embeddings[0].values
    except:
        return None

# =======================
# BUSCAR CONTEXTO (RAG)
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

    except:
        return ""

# =======================
# AGENTE IA
# =======================

def agente(msg):
    contexto = buscar_contexto(msg)

    prompt = f"""
Eres un sommelier experto.

Funciones:
- Recomendar bebidas
- Responder dudas
- Sugerir opciones

Usa SOLO el contexto.

CONTEXTO:
{contexto}

USUARIO:
{msg}
"""

    try:
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return r.text
    except:
        return "Error en IA"

# =======================
# UI
# =======================

st.set_page_config(layout="wide")
st.title("🍷 Verde & Vital")

# 🎨 estilo minimalista
st.markdown("""
<style>
.card {
    background:#111827;
    padding:20px;
    border-radius:15px;
    color:white;
    text-align:center;
}
.sidebar {
    background:#0f172a;
}
</style>
""", unsafe_allow_html=True)

# =======================
# MENÚ BASE
# =======================

menu = [
    {"nombre": "IPA Verde", "precio": 17},
    {"nombre": "Vino Tinto", "precio": 25},
    {"nombre": "Whisky 12 años", "precio": 35},
    {"nombre": "Mojito", "precio": 22},
]

# =======================
# ESTADO
# =======================

if "pedido" not in st.session_state:
    st.session_state.pedido = []

if "chat" not in st.session_state:
    st.session_state.chat = []

# =======================
# SIDEBAR PEDIDOS
# =======================

st.sidebar.title("🧾 Tus pedidos")

total = 0
for p in st.session_state.pedido:
    total += p["precio"]
    st.sidebar.write(f"{p['nombre']} - S/{p['precio']}")

st.sidebar.write("---")
st.sidebar.write(f"**Total: S/{total}**")

if st.sidebar.button("🧹 Limpiar pedido"):
    st.session_state.pedido = []

# =======================
# MENÚ VISUAL
# =======================

st.subheader("Menú")

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
            st.session_state.pedido.append(item)
            st.success("Agregado")

# =======================
# DASHBOARD SIMPLE
# =======================

st.divider()
st.subheader("📊 Resumen de pedido")

if st.session_state.pedido:
    nombres = [p["nombre"] for p in st.session_state.pedido]

    conteo = {}
    for n in nombres:
        conteo[n] = conteo.get(n, 0) + 1

    st.bar_chart(conteo)
else:
    st.info("Sin pedidos aún")

# =======================
# CHAT IA
# =======================

st.divider()
st.subheader("💬 Sommelier IA")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Pregunta sobre bebidas...")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = agente(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})
