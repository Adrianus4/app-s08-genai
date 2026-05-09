import streamlit as st
import pymongo
import psycopg2
from google import genai
from google.genai import types

# =======================
# CONFIG
# =======================

GOOGLE_API_KEY = "TU_API_KEY"

MONGODB_URI = "TU_MONGO_URI"

SUPABASE_CONFIG = {
    "host": "db.lbytbevfclnpefshnxrw.supabase.co",
    "dbname": "postgres",
    "user": "postgres",
    "password": "TU_PASSWORD",
    "port": 5432,
    "sslmode": "require"
}

# =======================
# CLIENTES
# =======================

client_genai = genai.Client(api_key=GOOGLE_API_KEY)

client_mongo = pymongo.MongoClient(MONGODB_URI)
db = client_mongo.pdf_embeddings_dbADR
collection = db.pdf_vectors

# =======================
# POSTGRES
# =======================

def get_conn():
    try:
        return psycopg2.connect(**SUPABASE_CONFIG)
    except Exception as e:
        print(e)
        return None

def guardar_pedido_db(items):
    conn = get_conn()
    if not conn:
        st.error("Error conectando a Supabase")
        return

    cur = conn.cursor()

    for item in items:
        cur.execute("""
        INSERT INTO restaurant.alcohol_orders
        (customer_name, drink_name, drink_type, quantity, unit_price, is_verified_age)
        VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            "Cliente Web",
            item["nombre"],
            item.get("tipo", "general"),
            1,
            item["precio"],
            True
        ))

    conn.commit()
    cur.close()
    conn.close()

def obtener_pedidos():
    conn = get_conn()
    if not conn:
        return []

    cur = conn.cursor()
    cur.execute("""
    SELECT drink_name, quantity, total_price, created_at
    FROM restaurant.alcohol_orders
    ORDER BY created_at DESC
    LIMIT 20
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# =======================
# EMBEDDINGS
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
    except:
        return None

# =======================
# RAG MONGO
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
- Ser claro y breve

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
        return "Error IA"

# =======================
# UI
# =======================

st.set_page_config(layout="wide")
st.title("🍷 Verde & Vital")

# 🎨 estilo
st.markdown("""
<style>
.card {
    background:#111827;
    padding:20px;
    border-radius:15px;
    color:white;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)

# =======================
# MENÚ
# =======================

menu = [
    {"nombre": "IPA Verde", "precio": 17, "tipo": "cerveza"},
    {"nombre": "Vino Tinto", "precio": 25, "tipo": "vino"},
    {"nombre": "Whisky 12 años", "precio": 35, "tipo": "whisky"},
    {"nombre": "Mojito", "precio": 22, "tipo": "cocktail"},
]

# =======================
# ESTADO
# =======================

if "pedido" not in st.session_state:
    st.session_state.pedido = []

if "chat" not in st.session_state:
    st.session_state.chat = []

# =======================
# SIDEBAR
# =======================

st.sidebar.title("🧾 Tu pedido")

total = 0
for p in st.session_state.pedido:
    total += p["precio"]
    st.sidebar.write(f"{p['nombre']} - S/{p['precio']}")

st.sidebar.write(f"**Total: S/{total}**")

if st.sidebar.button("✅ Guardar pedido"):
    guardar_pedido_db(st.session_state.pedido)
    st.sidebar.success("Pedido guardado en Supabase 🎉")
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

# =======================
# HISTORIAL (DB REAL)
# =======================

st.divider()
st.subheader("📊 Pedidos recientes")

pedidos = obtener_pedidos()

if pedidos:
    nombres = [p[0] for p in pedidos]

    conteo = {}
    for n in nombres:
        conteo[n] = conteo.get(n, 0) + 1

    st.bar_chart(conteo)

    for p in pedidos:
        st.write(f"{p[0]} | Cantidad: {p[1]} | S/{p[2]}")
else:
    st.info("Sin pedidos aún")

# =======================
# CHAT IA
# =======================

st.divider()
st.subheader("💬 Sommelier IA")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Ej: ¿qué vino recomiendas?")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = agente(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})
