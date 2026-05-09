import streamlit as st
import psycopg2
from google import genai
import json

# =======================
# CONFIG
# =======================

GOOGLE_API_KEY = "TU_GOOGLE_API_KEY"

SUPABASE_CONFIG = {
    "host": "db.lbytbevfclnpefshnxrw.supabase.co",
    "dbname": "postgres",
    "user": "postgres",
    "password": "TU_PASSWORD_REAL",
    "port": 5432,
    "sslmode": "require"
}

client_genai = genai.Client(api_key=GOOGLE_API_KEY)

# =======================
# DB
# =======================

def get_conn():
    try:
        return psycopg2.connect(**SUPABASE_CONFIG)
    except:
        return None

def guardar_pedido(pedido):
    conn = get_conn()
    if not conn:
        st.error("Error DB")
        return

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
# IA (solo para chat)
# =======================

def responder_chat(msg):
    try:
        r = client_genai.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Eres un mesero elegante. Responde breve: {msg}"
        )
        return r.text
    except:
        return "¿Te ayudo con alguna bebida del menú?"

# =======================
# UI BASE
# =======================

st.set_page_config(page_title="Verde & Vital", layout="wide")

# 🎨 estilo minimalista
st.markdown("""
<style>
body { background-color: #0f172a; }
.card {
    padding:20px;
    border-radius:16px;
    background:#111827;
    color:white;
    text-align:center;
    transition:0.2s;
}
.card:hover {
    transform: scale(1.03);
}
</style>
""", unsafe_allow_html=True)

st.title("🍹 Verde & Vital")
st.caption("Experiencia simple. Elegante. Inteligente.")

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
    st.session_state.pedido = {
        "cliente": "Cliente",
        "items": [],
        "edad_verificada": False,
        "notes": ""
    }

if "chat" not in st.session_state:
    st.session_state.chat = []

# =======================
# SIDEBAR (PEDIDO)
# =======================

st.sidebar.title("🧾 Tu pedido")

total = 0

for item in st.session_state.pedido["items"]:
    subtotal = item["precio"] * item["cantidad"]
    total += subtotal
    st.sidebar.write(f"{item['nombre']} x{item['cantidad']} — S/{subtotal}")

st.sidebar.write("---")
st.sidebar.write(f"**Total: S/{total}**")

if st.sidebar.button("🔞 Confirmar edad"):
    st.session_state.pedido["edad_verificada"] = True

if st.sidebar.button("✅ Finalizar pedido"):
    if not st.session_state.pedido["items"]:
        st.sidebar.warning("Sin productos")
    elif not st.session_state.pedido["edad_verificada"]:
        st.sidebar.warning("Confirma edad")
    else:
        guardar_pedido(st.session_state.pedido)
        st.sidebar.success("Pedido enviado 🎉")
        st.session_state.pedido["items"] = []

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
            if not st.session_state.pedido["edad_verificada"]:
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
# CHAT (SOLO DUDAS)
# =======================

st.divider()
st.subheader("💬 ¿Tienes dudas?")

for m in st.session_state.chat:
    st.chat_message(m["rol"]).write(m["texto"])

msg = st.chat_input("Ej: ¿qué me recomiendas?")

if msg:
    st.chat_message("user").write(msg)
    st.session_state.chat.append({"rol": "user", "texto": msg})

    respuesta = responder_chat(msg)

    st.chat_message("assistant").write(respuesta)
    st.session_state.chat.append({"rol": "assistant", "texto": respuesta})
