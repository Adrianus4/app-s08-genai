import streamlit as st
import pymongo
import psycopg2
from google import genai
from google.genai import types
import json

# =======================
# 🔐 CONFIG
# =======================

GOOGLE_API_KEY = "TU_GOOGLE_API_KEY"
MONGODB_URI = "TU_MONGODB_URI"

SUPABASE_CONFIG = {
    "host": "db.lbytbevfclnpefshnxrw.supabase.co",
    "dbname": "postgres",
    "user": "postgres",
    "password": "TU_PASSWORD_REAL",
    "port": 5432,
    "sslmode": "require"
}

# =======================
# CLIENTES
# =======================

@st.cache_resource
def get_genai_client():
    return genai.Client(api_key=GOOGLE_API_KEY)

@st.cache_resource
def get_mongo():
    client = pymongo.MongoClient(MONGODB_URI)
    return client["pdf_embeddings_dbADR"]["pdf_vectors"]

client_genai = get_genai_client()
collection = get_mongo()

# =======================
# DB
# =======================

def get_conn():
    try:
        conn = psycopg2.connect(**SUPABASE_CONFIG)
        return conn
    except Exception as e:
        st.error("❌ Error conectando a Supabase")
        st.text(str(e))
        return None

def guardar_pedido(pedido):
    conn = get_conn()

    if conn is None:
        return

    cur = conn.cursor()

    try:
        for item in pedido["items"]:
            cur.execute("""
            INSERT INTO restaurant.alcohol_orders
            (customer_name, drink_name, drink_type, quantity, unit_price, order_status, is_verified_age, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                pedido["cliente"],
                item["nombre"],
                item["tipo"],
                item["cantidad"],
                item["precio"],
                "pendiente",
                pedido["edad_verificada"],
                pedido["notes"]
            ))

        conn.commit()
        st.success("✅ Pedido guardado en Supabase")

    except Exception as e:
        st.error("❌ Error al guardar pedido")
        st.text(str(e))

    finally:
        cur.close()
        conn.close()

# =======================
# IA
# =======================

def crear_embedding(texto):
    response = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=texto,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return response.embeddings[0].values

def buscar_similares(embedding):
    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": embedding,
                    "numCandidates": 50,
                    "limit": 3,
                }
            }
        ]
        return list(collection.aggregate(pipeline))
    except:
        return []

def interpretar_pedido(msg, contextos):
    contexto = "\n".join([c.get("texto", "") for c in contextos])

    prompt = f"""
Eres un asistente de restaurante.

MENÚ:
{contexto}

Devuelve JSON:
{{
"accion": "agregar" o "ninguno",
"nombre": "",
"tipo": "",
"precio": 0,
"cantidad": 1
}}

Usuario: {msg}
"""

    try:
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return json.loads(r.text)
    except:
        return {"accion": "ninguno"}

def responder_natural(msg, pedido):
    try:
        prompt = f"""
Eres un mesero experto y amigable.

Pedido actual:
{pedido}

Cliente: {msg}

Responde breve.
"""
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return r.text
    except:
        return "🤖 Estoy aquí para ayudarte con tu pedido."

# =======================
# UI
# =======================

st.set_page_config(page_title="🍹 Verde & Vital", layout="centered")

st.title("🍹 Verde & Vital")
st.write("Pide con botones o usa el chat 🤖")

# =======================
# MENÚ
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
    st.session_state.pedido = None

if "chat" not in st.session_state:
    st.session_state.chat = []

# =======================
# BOTONES PRINCIPALES
# =======================

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🟢 Iniciar"):
        st.session_state.pedido = {
            "cliente": "Cliente Demo",
            "items": [],
            "edad_verificada": False,
            "notes": ""
        }

with col2:
    if st.button("🔞 Soy mayor"):
        if st.session_state.pedido:
            st.session_state.pedido["edad_verificada"] = True
            st.success("Edad verificada")

with col3:
    if st.button("✅ Finalizar"):
        if st.session_state.pedido:
            guardar_pedido(st.session_state.pedido)
            st.session_state.pedido = None

with col4:
    if st.button("🔌 Test DB"):
        conn = get_conn()
        if conn:
            st.success("Conexión OK")
            conn.close()

# =======================
# MENÚ INTERACTIVO
# =======================

st.subheader("📋 Menú")

cols = st.columns(len(menu))

for i, item in enumerate(menu):
    with cols[i]:
        st.metric(item["nombre"], f"S/ {item['precio']}")
        if st.button(f"Agregar", key=f"btn_{i}"):
            if not st.session_state.pedido:
                st.warning("Inicia pedido primero")
            elif not st.session_state.pedido["edad_verificada"]:
                st.warning("Confirma edad 🔞")
            else:
                st.session_state.pedido["items"].append({
                    "nombre": item["nombre"],
                    "tipo": item["tipo"],
                    "precio": item["precio"],
                    "cantidad": 1
                })
                st.success(f"{item['nombre']} agregado")

# =======================
# CHAT
# =======================

st.subheader("💬 Chat IA")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Escribe tu pedido...")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    if not st.session_state.pedido:
        respuesta = "Inicia pedido primero 🟢"
    else:
        emb = crear_embedding(msg)
        similares = buscar_similares(emb)
        data = interpretar_pedido(msg, similares)

        if data.get("accion") == "agregar" and st.session_state.pedido["edad_verificada"]:
            st.session_state.pedido["items"].append(data)

        respuesta = responder_natural(msg, st.session_state.pedido)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})

# =======================
# PEDIDO
# =======================

if st.session_state.pedido:
    st.subheader("🧾 Pedido")

    total = 0
    for item in st.session_state.pedido["items"]:
        subtotal = item["precio"] * item["cantidad"]
        total += subtotal
        st.write(f"{item['nombre']} x{item['cantidad']} → S/{subtotal}")

    servicio = total * 0.10
    total_final = total + servicio

    st.write(f"Subtotal: S/{total}")
    st.write(f"Servicio: S/{servicio}")
    st.write(f"Total: S/{total_final}")
