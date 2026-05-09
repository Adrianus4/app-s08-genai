import streamlit as st
import pymongo
import psycopg2
from google import genai
from google.genai import types

# =======================
# 🔐 CONFIG (TODO AQUÍ)
# =======================

GOOGLE_API_KEY = "AIzaSyAW2Tr51sSd39GO-iRAJAEyr_rdXJKFoKU"
MONGODB_URI = "mongodb+srv://benjaminjimenez0924_db_user:ADR123adr123@s05lab2.3pi8vwq.mongodb.net/"

SUPABASE_CONFIG = {
    "host": "db.lbytbevfclnpefshnxrw.supabase.co",
    "dbname": "postgres",
    "user": "postgres",
    "password": "TU_PASSWORD_AQUI",
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
        st.error(f"❌ Error Supabase: {e}")
        return None

def guardar_pedido_db(items):
    conn = get_conn()
    if not conn:
        return

    cur = conn.cursor()

    try:
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
        st.success("✅ Pedido guardado")

    except Exception as e:
        st.error(f"❌ Error guardando pedido: {e}")

    finally:
        cur.close()
        conn.close()

def obtener_pedidos():
    conn = get_conn()
    if not conn:
        return []

    cur = conn.cursor()

    try:
        cur.execute("""
        SELECT drink_name, quantity, total_price, created_at
        FROM restaurant.alcohol_orders
        ORDER BY created_at DESC
        LIMIT 20
        """)
        return cur.fetchall()
    except Exception as e:
        st.error(f"❌ Error consultando pedidos: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# =======================
# EMBEDDINGS
# =======================

def crear_embedding(texto):
    try:
        response = client_genai.models.embed_content(
            model="gemini-embedding-001",
            contents=texto,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return response.embeddings[0].values
    except Exception as e:
        st.warning(f"⚠️ Error embedding: {e}")
        return None

# =======================
# RAG
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

        textos = [r.get("texto", "") for r in resultados]
        return "\n".join(textos)

    except Exception as e:
        st.warning(f"⚠️ Error Mongo: {e}")
        return ""

# =======================
# 🤖 AGENTE IA (ARREGLADO)
# =======================

def agente(msg):
    contexto = buscar_contexto(msg)

    prompt = f"""
Eres un sommelier experto en bebidas alcohólicas.

Responde claro, profesional y útil.

Si no hay contexto suficiente, responde con conocimiento general.

CONTEXTO:
{contexto}

PREGUNTA:
{msg}
"""

    try:
        response = client_genai.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        return response.text if hasattr(response, "text") else "Sin respuesta"

    except Exception as e:
        return f"❌ Error IA: {e}"

# =======================
# 🎨 UI ELEGANTE
# =======================

st.set_page_config(layout="wide")

st.markdown("""
<style>
body {
    background-color: #0f172a;
}
.card {
    background:#1e293b;
    padding:20px;
    border-radius:20px;
    color:white;
    text-align:center;
    transition:0.3s;
}
.card:hover {
    transform: scale(1.05);
    background:#334155;
}
</style>
""", unsafe_allow_html=True)

st.title("🍷 Verde & Vital")

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

total = sum(p["precio"] for p in st.session_state.pedido)

for p in st.session_state.pedido:
    st.sidebar.write(f"{p['nombre']} - S/{p['precio']}")

st.sidebar.write(f"**Total: S/{total}**")

if st.sidebar.button("Guardar pedido"):
    guardar_pedido_db(st.session_state.pedido)
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
# HISTORIAL ELEGANTE
# =======================

st.divider()
st.subheader("📊 Historial de pedidos")

pedidos = obtener_pedidos()

if pedidos:
    conteo = {}
    for p in pedidos:
        conteo[p[0]] = conteo.get(p[0], 0) + 1

    st.bar_chart(conteo)

    for p in pedidos:
        st.markdown(f"""
        <div class="card">
        🍸 {p[0]} | Cantidad: {p[1]} | Total: S/{p[2]}
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("Sin pedidos aún")

# =======================
# CHAT IA
# =======================

st.divider()
st.subheader("💬 Sommelier IA")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Ej: ¿Qué vino recomiendas con carne?")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = agente(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})
