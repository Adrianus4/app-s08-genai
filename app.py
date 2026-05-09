import streamlit as st
import pymongo
import psycopg2
from google import genai
from google.genai import types
import json

# =======================
# CONFIG
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
    try:
        client = pymongo.MongoClient(MONGODB_URI)
        return client["pdf_embeddings_dbADR"]["pdf_vectors"]
    except:
        return None

client_genai = get_genai_client()
collection = get_mongo()

# =======================
# DB
# =======================

def get_conn():
    try:
        return psycopg2.connect(**SUPABASE_CONFIG)
    except Exception as e:
        st.error("❌ Error DB")
        st.text(str(e))
        return None

def guardar_pedido(pedido):
    conn = get_conn()
    if not conn:
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
        st.success("🎉 Pedido guardado correctamente")

    except Exception as e:
        st.error("❌ Error guardando")
        st.text(str(e))

    finally:
        cur.close()
        conn.close()

# =======================
# IA SEGURA
# =======================

def crear_embedding(texto):
    try:
        response = client_genai.models.embed_content(
            model="gemini-embedding-001",
            contents=texto,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY"),
        )
        return response.embeddings[0].values
    except:
        return None

def detectar_menu_local(msg, menu):
    msg = msg.lower()
    for item in menu:
        if item["nombre"].lower() in msg:
            return {
                "accion": "agregar",
                "nombre": item["nombre"],
                "tipo": item["tipo"],
                "precio": item["precio"],
                "cantidad": 1
            }
    return {"accion": "ninguno"}

def interpretar_pedido(msg, contextos):
    try:
        contexto = "\n".join([c.get("texto", "") for c in contextos])

        prompt = f"""
Extrae pedido en JSON:

Usuario: {msg}

Formato:
{{
"accion": "agregar" o "ninguno",
"nombre": "",
"tipo": "",
"precio": 0,
"cantidad": 1
}}
"""
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return json.loads(r.text)

    except:
        return {"accion": "ninguno"}

def responder_natural(msg):
    try:
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Responde como mesero amigable: {msg}"
        )
        return r.text
    except:
        return "🤖 ¿Deseas ver el menú o agregar una bebida?"

# =======================
# UI
# =======================

st.set_page_config(page_title="🍹 Verde & Vital", layout="wide")

st.markdown("""
<style>
.card {
    padding:15px;
    border-radius:15px;
    background:#1e1e1e;
    color:white;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)

st.title("🍹 Verde & Vital")
st.caption("Tu bar inteligente 🍸")

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
# CONTROLES
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
            st.session_state.pedido = None

# =======================
# MENÚ VISUAL
# =======================

st.subheader("📋 Menú")

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
            if not st.session_state.pedido:
                st.warning("Inicia pedido")
            elif not st.session_state.pedido["edad_verificada"]:
                st.warning("Confirma edad")
            else:
                st.session_state.pedido["items"].append({
                    "nombre": item["nombre"],
                    "tipo": item["tipo"],
                    "precio": item["precio"],
                    "cantidad": 1
                })
                st.success("Agregado")

# =======================
# CHAT
# =======================

st.subheader("💬 Chat")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Ej: 2 mojitos")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    if not st.session_state.pedido:
        respuesta = "Inicia pedido primero 🟢"
    else:
        emb = crear_embedding(msg)

        if emb and collection:
            similares = buscar_similares(emb)
            data = interpretar_pedido(msg, similares)
        else:
            data = detectar_menu_local(msg, menu)

        if data["accion"] == "agregar" and st.session_state.pedido["edad_verificada"]:
            st.session_state.pedido["items"].append(data)

        respuesta = responder_natural(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})

# =======================
# PEDIDO BONITO
# =======================

if st.session_state.pedido:
    st.subheader("🧾 Tu pedido")

    total = 0

    for item in st.session_state.pedido["items"]:
        subtotal = item["precio"] * item["cantidad"]
        total += subtotal

        st.markdown(f"""
        🥤 **{item['nombre']}**  
        Cantidad: {item['cantidad']}  
        Subtotal: S/ {subtotal}
        ---
        """)

    servicio = total * 0.10
    total_final = total + servicio

    col1, col2, col3 = st.columns(3)

    col1.metric("Subtotal", f"S/ {total}")
    col2.metric("Servicio", f"S/ {servicio:.2f}")
    col3.metric("Total", f"S/ {total_final:.2f}")
