import streamlit as st
import pymongo
import psycopg2
from google import genai
from google.genai import types

# =======================
# 🔐 CONFIG (TODO AQUÍ)
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
def get_mongo_collection():
    client = pymongo.MongoClient(MONGODB_URI)
    return client["pdf_embeddings_dbADR"]["pdf_vectors"]

client_genai = get_genai_client()
collection = get_mongo_collection()

# =======================
# SUPABASE (POSTGRES)
# =======================

def get_pg_connection():
    return psycopg2.connect(**SUPABASE_CONFIG)

def guardar_pedido(pedido):
    conn = get_pg_connection()
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
# IA + EMBEDDINGS
# =======================

def crear_embedding(texto):
    response = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=texto,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
    )
    return response.embeddings[0].values

def buscar_similares(embedding, k=3):
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 50,
                "limit": k,
            }
        }
    ]
    return list(collection.aggregate(pipeline))

def interpretar_pedido(user_msg, contextos):
    contexto = "\n".join([c["texto"] for c in contextos])

    prompt = f"""
Eres un asistente de restaurante.

MENÚ:
{contexto}

Extrae si el usuario quiere pedir una bebida.
Responde SOLO en JSON:

{{
"accion": "agregar" o "ninguno",
"nombre": "",
"tipo": "",
"precio": 0,
"cantidad": 1
}}

Usuario: {user_msg}
"""

    response = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    try:
        import json
        return json.loads(response.text)
    except:
        return {"accion": "ninguno"}

# =======================
# UI
# =======================

st.set_page_config(page_title="Bot Restaurante IA", page_icon="🍹")
st.title("🍹 Restaurante Inteligente")

# Estado
if "pedido" not in st.session_state:
    st.session_state.pedido = None

if "chat" not in st.session_state:
    st.session_state.chat = []

# Mostrar chat
for msg in st.session_state.chat:
    st.chat_message(msg["rol"]).write(msg["texto"])

msg = st.chat_input("Escribe...")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = ""

    # =======================
    # FLUJO DEL NEGOCIO
    # =======================

    if "iniciar pedido" in msg.lower():
        st.session_state.pedido = {
            "cliente": "Cliente Demo",
            "items": [],
            "edad_verificada": False,
            "notes": ""
        }
        respuesta = "✅ Pedido iniciado. ¿Qué bebida deseas?"

    elif st.session_state.pedido is None:
        respuesta = "⚠️ Primero escribe: 'iniciar pedido'"

    elif "soy mayor" in msg.lower():
        st.session_state.pedido["edad_verificada"] = True
        respuesta = "✅ Edad verificada"

    elif "finalizar" in msg.lower():
        if not st.session_state.pedido["items"]:
            respuesta = "❌ No hay productos en el pedido"
        elif not st.session_state.pedido["edad_verificada"]:
            respuesta = "⚠️ Debes confirmar que eres mayor de edad"
        else:
            guardar_pedido(st.session_state.pedido)
            respuesta = "🎉 Pedido guardado en Supabase"
            st.session_state.pedido = None

    else:
        emb = crear_embedding(msg)
        similares = buscar_similares(emb)

        data = interpretar_pedido(msg, similares)

        if data["accion"] == "agregar":
            st.session_state.pedido["items"].append({
                "nombre": data["nombre"],
                "tipo": data["tipo"],
                "precio": data["precio"],
                "cantidad": data["cantidad"]
            })

            respuesta = f"🍺 Agregado: {data['nombre']} x{data['cantidad']}"
        else:
            respuesta = "🤖 Puedo ayudarte a elegir bebidas o tomar tu pedido."

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})

# =======================
# SIDEBAR PEDIDO
# =======================

if st.session_state.pedido:
    st.sidebar.title("🧾 Pedido actual")

    total = 0
    for item in st.session_state.pedido["items"]:
        subtotal = item["precio"] * item["cantidad"]
        total += subtotal
        st.sidebar.write(f"{item['nombre']} x{item['cantidad']} - S/{subtotal}")

    st.sidebar.write("---")
    st.sidebar.write(f"Total: S/{total}")
