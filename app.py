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
    "password": "TU_PASSWORD_SUPABASE",
    "port": 5432
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
    return psycopg2.connect(**SUPABASE_CONFIG)

def guardar_pedido(pedido):
    conn = get_conn()
    cur = conn.cursor()

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

def interpretar_pedido(msg, contextos):
    contexto = "\n".join([c["texto"] for c in contextos])

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

    r = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    try:
        return json.loads(r.text)
    except:
        return {"accion": "ninguno"}

def responder_natural(msg, pedido):
    prompt = f"""
Eres un mesero experto, amigable.

Pedido actual:
{pedido}

Cliente: {msg}

Responde breve y útil.
"""

    r = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return r.text

# =======================
# UI
# =======================

st.set_page_config(page_title="🍹 Verde & Vital", layout="centered")

st.title("🍹 Verde & Vital")
st.write("Pide fácil con botones o usa el chat 🤖")

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
# ACCIONES PRINCIPALES
# =======================

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🟢 Iniciar pedido"):
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
            st.success("Pedido guardado 🎉")
            st.session_state.pedido = None

# =======================
# BOTONES DEL MENÚ
# =======================

st.subheader("📋 Menú interactivo")

cols = st.columns(len(menu))

for i, item in enumerate(menu):
    with cols[i]:
        st.metric(item["nombre"], f"S/ {item['precio']}")
        if st.button(f"Agregar {item['nombre']}", key=i):
            if not st.session_state.pedido:
                st.warning("Inicia un pedido primero")
            elif not st.session_state.pedido["edad_verificada"]:
                st.warning("Confirma que eres mayor 🔞")
            else:
                st.session_state.pedido["items"].append({
                    "nombre": item["nombre"],
                    "tipo": item["tipo"],
                    "precio": item["precio"],
                    "cantidad": 1
                })
                st.success(f"{item['nombre']} agregado ✅")

# =======================
# CHAT OPCIONAL
# =======================

st.subheader("💬 Chat con IA (opcional)")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Escribe aquí...")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    if not st.session_state.pedido:
        respuesta = "Inicia un pedido primero 🟢"
    else:
        emb = crear_embedding(msg)
        similares = buscar_similares(emb)
        data = interpretar_pedido(msg, similares)

        if data["accion"] == "agregar":
            st.session_state.pedido["items"].append(data)

        respuesta = responder_natural(msg, st.session_state.pedido)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})

# =======================
# PEDIDO
# =======================

if st.session_state.pedido:
    st.subheader("🧾 Tu pedido")

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
