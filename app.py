import streamlit as st
import pymongo
from google import genai
from google.genai import types

# =======================
# CONFIGURACIÓN
# =======================

GOOGLE_API_KEY = st.secrets["app"]["GOOGLE_API_KEY"]
MONGODB_URI = st.secrets["app"]["MONGODB_URI"]

if not GOOGLE_API_KEY or not MONGODB_URI:
    st.error("❌ Faltan las variables de entorno GOOGLE_API_KEY o MONGODB_URI")
    st.stop()

# =======================
# CLIENTES (cacheados)
# =======================

@st.cache_resource
def get_genai_client():
    return genai.Client(api_key=GOOGLE_API_KEY)

@st.cache_resource
def get_mongo_collection():
    client = pymongo.MongoClient(MONGODB_URI)
    db = client["pdf_embeddings_db"]
    return db["pdf_vectors"]

client_genai = get_genai_client()
collection = get_mongo_collection()

# =======================
# FUNCIONES RAG
# =======================

def crear_embedding(texto: str):
    """
    Genera embedding para la query del usuario.
    Usa task_type='RETRIEVAL_QUERY' (los documentos se indexaron con 'RETRIEVAL_DOCUMENT').
    """
    response = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=texto,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
        ),
    )
    return response.embeddings[0].values


def buscar_similares(embedding, k=5):
    """
    Busca los fragmentos más relevantes en MongoDB Atlas Vector Search.
    Requiere el índice 'vector_index' sobre el campo 'embedding'.
    """
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 100,
                "limit": k,
            }
        },
        {
            "$project": {
                "_id": 0,
                "texto": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(collection.aggregate(pipeline))


def generar_respuesta(pregunta: str, contextos: list[dict], historial: list[dict]) -> str:
    """
    Genera una respuesta usando Gemini con contexto RAG e historial de conversación.
    El agente tiene personalidad de experto en criptomonedas.
    """
    contexto = "\n\n".join([c["texto"] for c in contextos])

    # Construir historial como texto para incluir en el prompt
    historial_texto = ""
    if historial:
        for msg in historial[-6:]:  # últimos 3 turnos (usuario + bot)
            rol = "Usuario" if msg["rol"] == "usuario" else "CryptoBot"
            historial_texto += f"{rol}: {msg['texto']}\n"

    prompt = f"""Eres CryptoBot, un asistente experto en criptomonedas, blockchain y activos digitales. \
Tu conocimiento proviene exclusivamente de "Tu Primera Guía de Criptomonedas". \
Esta guía está orientada a personas que se inician en el mundo crypto, por lo que respondes de forma \
clara, didáctica y accesible, sin asumir conocimientos previos, pero usando términos técnicos cuando \
sea necesario y siempre explicándolos. Si la respuesta no está en el contexto de la guía, indícalo \
honestamente y sugiere al usuario que reformule su pregunta.

Contexto de la guía:
{contexto}

{'Historial reciente de la conversación:' + chr(10) + historial_texto if historial_texto else ''}

Pregunta actual del usuario: {pregunta}

Responde en español de forma concisa, clara y útil. Si es relevante, usa viñetas o pasos numerados \
para estructurar mejor la respuesta."""

    response = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text


# =======================
# INTERFAZ STREAMLIT
# =======================

st.set_page_config(
    page_title="CryptoBot — Tu Primera Guía de Criptomonedas",
    page_icon="₿",
    layout="centered",
)

# ---- CSS personalizado ----
st.markdown("""
<style>
    /* Fondo oscuro estilo crypto */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #0d1b2a 50%, #0a0e1a 100%);
    }

    /* Header principal */
    .crypto-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .crypto-header h1 {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #f7931a, #f5c518, #00d4ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .crypto-header p {
        color: #8892a4;
        font-size: 0.9rem;
        margin-top: 0.3rem;
    }

    /* Badge de estado */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(0, 212, 255, 0.1);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.75rem;
        color: #00d4ff;
        margin-top: 0.5rem;
    }
    .status-dot {
        width: 7px;
        height: 7px;
        background: #00d4ff;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }

    /* Área de chat */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }

    /* Botón limpiar */
    .stButton > button {
        background: rgba(247, 147, 26, 0.15);
        border: 1px solid rgba(247, 147, 26, 0.4);
        color: #f7931a;
        border-radius: 8px;
        font-size: 0.8rem;
        padding: 0.3rem 0.8rem;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: rgba(247, 147, 26, 0.3);
        border-color: #f7931a;
        color: #fff;
    }

    /* Input de chat */
    .stChatInputContainer {
        border-top: 1px solid rgba(255,255,255,0.08);
        padding-top: 0.5rem;
    }

    /* Expander de fuentes */
    .streamlit-expanderHeader {
        font-size: 0.8rem;
        color: #8892a4 !important;
    }

    /* Divisor */
    hr {
        border-color: rgba(255,255,255,0.06);
    }
</style>
""", unsafe_allow_html=True)

# ---- Header ----
st.markdown("""
<div class="crypto-header">
    <h1>₿ CryptoBot</h1>
    <p>Basado en <em>Tu Primera Guía de Criptomonedas</em></p>
    <div class="status-badge">
        <div class="status-dot"></div>
        Tu Primera Guía de Criptomonedas — cargada
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ---- Inicializar historial ----
if "historial" not in st.session_state:
    st.session_state.historial = []

# ---- Sidebar con info y controles ----
with st.sidebar:
    st.markdown("### 🤖 Sobre CryptoBot")
    st.markdown("""
    Soy un agente RAG entrenado con **Tu Primera Guía de Criptomonedas**.
    Ideal para quienes están comenzando. Puedo responder preguntas sobre:
    - 🪙 Bitcoin, Ethereum y altcoins
    - 🔗 Blockchain y tecnología DLT
    - 💼 Wallets y exchanges
    - 📈 Trading y estrategias
    - 🔐 Seguridad y custodia
    - 🌐 DeFi, NFTs y Web3
    """)
    st.markdown("---")
    st.markdown("### ⚙️ Configuración")
    k_resultados = st.slider("Fragmentos a recuperar", min_value=3, max_value=10, value=5,
                              help="Número de fragmentos del PDF a usar como contexto")
    st.markdown("---")
    if st.button("🗑️ Limpiar conversación"):
        st.session_state.historial = []
        st.rerun()

    st.markdown("---")
    st.markdown("""
    <div style='font-size:0.75rem; color:#8892a4; text-align:center;'>
        Powered by<br>
        <strong style='color:#f7931a'>Gemini 2.5 Flash</strong> + 
        <strong style='color:#00d4ff'>MongoDB Atlas</strong>
    </div>
    """, unsafe_allow_html=True)

# ---- Mensaje de bienvenida (solo si no hay historial) ----
if not st.session_state.historial:
    with st.chat_message("assistant"):
        st.markdown("""
        👋 ¡Hola! Soy **CryptoBot**, tu guía en el mundo de las criptomonedas.

        Estoy entrenado con **Tu Primera Guía de Criptomonedas**, perfecta para quienes están \
dando sus primeros pasos. Puedes preguntarme sobre:
        - *¿Qué es Bitcoin y cómo funciona?*
        - *¿Cómo puedo comprar mis primeras criptomonedas de forma segura?*
        - *¿Qué diferencia hay entre una wallet caliente y una fría?*

        ¡Escribe tu pregunta abajo! 👇
        """)

# ---- Mostrar historial ----
for msg in st.session_state.historial:
    if msg["rol"] == "usuario":
        st.chat_message("user").write(msg["texto"])
    else:
        st.chat_message("assistant").write(msg["texto"])

# ---- Input del usuario ----
pregunta = st.chat_input("Pregúntame sobre criptomonedas, blockchain, wallets...")

if pregunta:
    # Mostrar pregunta del usuario inmediatamente
    st.chat_message("user").write(pregunta)
    st.session_state.historial.append({"rol": "usuario", "texto": pregunta})

    with st.chat_message("assistant"):
        with st.spinner("🔍 Buscando en la guía..."):
            try:
                emb = crear_embedding(pregunta)
                similares = buscar_similares(emb, k=k_resultados)

                if not similares:
                    respuesta = (
                        "⚠️ No encontré información relevante en la guía para esa pregunta. "
                        "Intenta reformularla o pregunta algo más específico sobre criptomonedas."
                    )
                else:
                    respuesta = generar_respuesta(
                        pregunta,
                        similares,
                        st.session_state.historial[:-1]  # historial sin la pregunta actual
                    )
            except Exception as e:
                respuesta = f"⚠️ Ocurrió un error al procesar tu pregunta: {e}"

        st.write(respuesta)

        # Fragmentos recuperados (colapsados)
        if 'similares' in locals() and similares:
            with st.expander(f"📄 Ver {len(similares)} fragmentos de 'Tu Primera Guía de Criptomonedas'"):
                for i, c in enumerate(similares, 1):
                    score_color = "#00d4ff" if c['score'] > 0.8 else "#f5c518" if c['score'] > 0.6 else "#8892a4"
                    st.markdown(
                        f"**Fragmento {i}** — "
                        f"<span style='color:{score_color}'>relevancia: `{c['score']:.4f}`</span>",
                        unsafe_allow_html=True
                    )
                    st.write(c["texto"][:500] + ("…" if len(c["texto"]) > 500 else ""))
                    st.divider()

    st.session_state.historial.append({"rol": "bot", "texto": respuesta})
