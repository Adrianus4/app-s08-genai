import streamlit as st
import pymongo
import psycopg2
from google import genai
from google.genai import types

# =======================
# CONFIG (IGUAL QUE TU NOTEBOOK)
# =======================
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
MONGODB_URI = st.secrets["MONGODB_URI"]
SUPABASE_DB_URL = st.secrets["SUPABASE_DB_URL"]

if not GOOGLE_API_KEY or not MONGODB_URI:
    st.error("Faltan credenciales")
    st.stop()

# =======================
# CLIENTES
# =======================
client_genai = genai.Client(api_key=GOOGLE_API_KEY)

client_mongo = pymongo.MongoClient(MONGODB_URI)
db = client_mongo.pdf_embeddings_db
collection = db.pdf_vectors

pg_conn = psycopg2.connect(SUPABASE_DB_URL)
pg_conn.autocommit = True

# =======================
# EMBEDDING (MISMA LÓGICA)
# =======================
def crear_embedding(texto, task_type="RETRIEVAL_QUERY"):
    response = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=texto,
        config=types.EmbedContentConfig(
            task_type=task_type,
        ),
    )
    return response.embeddings[0].values


# =======================
# BÚSQUEDA VECTORIAL
# =======================
def buscar_contexto(pregunta):
    emb = crear_embedding(pregunta)

    resultados = collection.aggregate([
        {
            "$vectorSearch": {
                "queryVector": emb,
                "path": "embedding",
                "numCandidates": 100,
                "limit": 3,
                "index": "vector_index"
            }
        }
    ])

    textos = [doc["texto"] for doc in resultados]
    return "\n".join(textos)


# =======================
# RESPUESTA IA
# =======================
def responder(pregunta):
    contexto = buscar_contexto(pregunta)

    prompt = f"""
    Eres un asistente de restaurante especializado en bebidas alcohólicas.

    CONTEXTO:
    {contexto}

    USUARIO:
    {pregunta}

    Responde claro y amigable.
    """

    response = client_genai.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )

    return response.text


# =======================
# PEDIDOS
# =======================
def es_pedido(texto):
    return any(p in texto.lower() for p in ["quiero", "pedido", "dame", "orden"])


def guardar_pedido():
    cursor = pg_conn.cursor()
    cursor.execute("""
        INSERT INTO restaurant.alcohol_orders
        (customer_name, drink_name, quantity, unit_price, is_verified_age)
        VALUES (%s, %s, %s, %s, %s)
    """, ("Cliente Demo", "Cerveza", 1, 20.0, True))
    cursor.close()


# =======================
# UI
# =======================
st.title("🍹 Chatbot Restaurante")

if "chat" not in st.session_state:
    st.session_state.chat = []

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_input = st.chat_input("Escribe tu mensaje...")

if user_input:
    st.session_state.chat.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    if es_pedido(user_input):
        guardar_pedido()
        respuesta = "✅ Pedido registrado 🍺"
    else:
        respuesta = responder(user_input)

    st.session_state.chat.append({"role": "assistant", "content": respuesta})
    with st.chat_message("assistant"):
        st.write(respuesta)
