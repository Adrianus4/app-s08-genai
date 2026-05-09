import streamlit as st
import os
import pymongo
import psycopg2
from google import genai

# =========================
# CONFIG
# =========================
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")  # cadena postgres

# =========================
# CLIENTES
# =========================
client_genai = genai.Client(api_key=GOOGLE_API_KEY)

mongo_client = pymongo.MongoClient(MONGODB_URI)
mongo_db = mongo_client["pdf_embeddings_dbADR"]
collection = mongo_db["pdf_vectors"]

pg_conn = psycopg2.connect(SUPABASE_DB_URL)
pg_conn.autocommit = True

# =========================
# FUNCIONES IA
# =========================
def crear_embedding(texto):
    response = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=texto
    )
    return response.embeddings[0].values


def buscar_contexto(pregunta):
    query_embedding = crear_embedding(pregunta)

    resultados = collection.aggregate([
        {
            "$vectorSearch": {
                "queryVector": query_embedding,
                "path": "embedding",
                "numCandidates": 100,
                "limit": 3,
                "index": "vector_index"
            }
        }
    ])

    textos = [doc["texto"] for doc in resultados]
    return "\n".join(textos)


def responder(pregunta):
    contexto = buscar_contexto(pregunta)

    prompt = f"""
    Eres un asistente de restaurante especializado en bebidas alcohólicas.

    CONTEXTO:
    {contexto}

    USUARIO:
    {pregunta}

    Responde de forma clara y amigable.
    """

    response = client_genai.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )

    return response.text


# =========================
# DETECCIÓN DE PEDIDOS
# =========================
def es_pedido(texto):
    palabras = ["quiero", "pedido", "orden", "dame", "comprar"]
    return any(p in texto.lower() for p in palabras)


def guardar_pedido(nombre, bebida, cantidad):
    cursor = pg_conn.cursor()

    query = """
    INSERT INTO restaurant.alcohol_orders 
    (customer_name, drink_name, quantity, unit_price, is_verified_age)
    VALUES (%s, %s, %s, %s, %s)
    """

    # precio fijo demo
    precio = 20.00

    cursor.execute(query, (nombre, bebida, cantidad, precio, True))
    cursor.close()


# =========================
# UI STREAMLIT
# =========================
st.set_page_config(page_title="🍹 Chatbot Restaurante", layout="centered")

st.title("🍹 Chatbot de Bebidas")

if "chat" not in st.session_state:
    st.session_state.chat = []

# Mostrar historial
for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input usuario
user_input = st.chat_input("Escribe tu mensaje...")

if user_input:
    # Mostrar usuario
    st.session_state.chat.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Detectar pedido
    if es_pedido(user_input):
        try:
            guardar_pedido("Cliente Demo", "Cerveza", 1)
            respuesta = "✅ Pedido registrado correctamente 🍺"
        except Exception as e:
            respuesta = f"❌ Error al guardar pedido: {e}"
    else:
        respuesta = responder(user_input)

    # Mostrar respuesta
    st.session_state.chat.append({"role": "assistant", "content": respuesta})
    with st.chat_message("assistant"):
        st.write(respuesta)
