import streamlit as st
import psycopg2
from pymongo import MongoClient
from google import genai
import re

# ==============================
# CONFIG
# ==============================

st.set_page_config(page_title="🍹 Verde & Vital", layout="centered")

st.markdown("""
# 🍹 Verde & Vital
### Asistente inteligente de bebidas
---
""")

# ==============================
# SECRETS
# ==============================

SUPABASE_CONFIG = {
    "host": st.secrets["SUPABASE_HOST"],
    "database": st.secrets["SUPABASE_DB"],
    "user": st.secrets["SUPABASE_USER"],
    "password": st.secrets["SUPABASE_PASSWORD"],
    "port": st.secrets["SUPABASE_PORT"]
}

MONGO_URI = st.secrets["MONGODB_URI"]
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]

# ==============================
# CONEXIONES
# ==============================

# Supabase (Postgres)
def get_conn():
    return psycopg2.connect(**SUPABASE_CONFIG)

# MongoDB
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["rag_restaurante"]
collection = mongo_db["bebidas"]

# Gemini
client_genai = genai.Client(api_key=GOOGLE_API_KEY)

# ==============================
# ESTADO
# ==============================

if "pedido" not in st.session_state:
    st.session_state.pedido = None

if "chat" not in st.session_state:
    st.session_state.chat = []

# ==============================
# FUNCIONES
# ==============================

def detectar_bebida(mensaje):
    """Detecta bebida básica desde texto"""
    mensaje = mensaje.lower()

    catalogo = [
        {"nombre": "IPA Verde", "tipo": "cerveza", "precio": 17},
        {"nombre": "Vino Tinto Reserva", "tipo": "vino", "precio": 25},
        {"nombre": "Whisky 12 años", "tipo": "whisky", "precio": 35},
        {"nombre": "Mojito", "tipo": "coctel", "precio": 22}
    ]

    for bebida in catalogo:
        if bebida["nombre"].lower() in mensaje:
            cantidad = 1
            match = re.search(r"\d+", mensaje)
            if match:
                cantidad = int(match.group())

            return {
                "nombre": bebida["nombre"],
                "tipo": bebida["tipo"],
                "precio": bebida["precio"],
                "cantidad": cantidad
            }

    return None


def generar_respuesta_natural(user_msg, estado_pedido):
    prompt = f"""
Eres un asistente de restaurante amigable.

Estado del pedido:
{estado_pedido}

Usuario: {user_msg}

Responde de forma natural, breve y útil.
"""

    try:
        response = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except:
        return "Estoy teniendo problemas para responder ahora 😅"


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

# ==============================
# BOTONES UX
# ==============================

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
    if st.button("🔞 Soy mayor de edad"):
        if st.session_state.pedido:
            st.session_state.pedido["edad_verificada"] = True
            st.success("Edad verificada ✅")

with col3:
    if st.button("✅ Finalizar pedido"):
        if st.session_state.pedido:
            guardar_pedido(st.session_state.pedido)
            st.success("Pedido guardado 🎉")
            st.session_state.pedido = None

# ==============================
# CHAT
# ==============================

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("Escribe tu pedido...")

if user_input:
    st.session_state.chat.append({"role": "user", "content": user_input})

    if not st.session_state.pedido:
        respuesta = "Primero inicia un pedido con el botón 🟢"
    else:
        data = detectar_bebida(user_input)

        if data:
            if not st.session_state.pedido["edad_verificada"]:
                respuesta = "⚠️ Debes confirmar que eres mayor de edad"
            else:
                st.session_state.pedido["items"].append(data)
                respuesta = generar_respuesta_natural(user_input, st.session_state.pedido)
        else:
            respuesta = generar_respuesta_natural(user_input, st.session_state.pedido)

    st.session_state.chat.append({"role": "assistant", "content": respuesta})

    with st.chat_message("assistant"):
        st.markdown(respuesta)

# ==============================
# MOSTRAR PEDIDO
# ==============================

if st.session_state.pedido:
    st.markdown("## 🧾 Tu pedido")

    total = 0
    for item in st.session_state.pedido["items"]:
        subtotal = item["precio"] * item["cantidad"]
        total += subtotal

        st.markdown(f"""
**{item['nombre']}**  
Cantidad: {item['cantidad']}  
Subtotal: S/{subtotal:.2f}
---
""")

    servicio = total * 0.10
    total_final = total + servicio

    st.markdown(f"💰 Subtotal: S/{total:.2f}")
    st.markdown(f"🧾 Servicio (10%): S/{servicio:.2f}")
    st.markdown(f"## Total: S/{total_final:.2f}")
