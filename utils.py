# utils.py
import streamlit as st
from deep_translator import GoogleTranslator
from gtts import gTTS
from io import BytesIO
import time
from langdetect import detect
from auth import initialize_firebase, render_login_signup # Import auth functions

# ----------------- Session State Init -----------------
def init_session_state():
    if "lang" not in st.session_state:
        st.session_state.lang = "English"

# ----------------- Global CSS -----------------
def apply_custom_css():
    init_session_state()
    st.markdown("""
    <style>
    /* --- (FIX) Force background image on main container --- */
    .stApp {
        background: url("https://images.unsplash.com/photo-1500595046743-cd271d6942ee?q=80&w=2074&auto.format&fit=crop") no-repeat center center fixed;
        background-size: cover;
    }
    .stApp::before {
        content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: linear-gradient(135deg, rgba(0,100,0,0.5), rgba(0,0,0,0.3));
        z-index: -1;
    }
    /* --- (FIX) Force ALL text (including login) to be dark green --- */
    h1, h2, h3, h4, p, li, span, div, label, .st-emotion-cache-16txtl3, .st-emotion-cache-1jicfl2, .st-emotion-cache-6qob1r { 
        color: #1B5E20 !important; 
        text-shadow: 0 1px 2px rgba(0,0,0,0.1); 
    }
    /* --- (FIX) Force sidebar text to be dark green --- */
    [data-testid="stSidebar"] { 
        background-color: rgba(230, 245, 230, 0.8) !important;
        backdrop-filter: blur(5px);
    }
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label {
        color: #1B5E20 !important;
    }
    /* --- (FIX) Style the Login/Signup tabs --- */
    div[data-testid="stTabs"] button[role="tab"] {
        color: #1B5E20 !important;
        font-weight: 600;
    }
    /* (Rest of your UI is unchanged) */
    [data-testid="stChatContainer"] {
        background-color: rgba(255, 255, 255, 0.9);
        border-radius: 15px;
    }
    .stButton>button{
        background:linear-gradient(45deg,#2E7D32,#4CAF50);
        color:white;border:none;border-radius:30px;
        padding:12px 24px;font-weight:600;font-size:16px;
    }
    .streamlit-expanderHeader {
        background: linear-gradient(45deg, #2E7D32, #4CAF50) !important;
        color: white !important;
    }
    .streamlit-expanderContent {
        background: rgba(255,255,255,0.95) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ----------------- Global Translator -----------------
@st.cache_data
def t(text, lang="en"):
    if lang == "English": return text
    if lang == "Kannada":
        try: return GoogleTranslator(source='en', target='kn').translate(text)
        except: return text
    return text

# ----------------- Global Language Toggle -----------------
def language_toggle():
    init_session_state()
    lang_options = ["English", "Kannada"]
    current_index = 1 if st.session_state.lang == "Kannada" else 0
    new_lang = st.selectbox(
        label="Language / ಭాಷೆ", options=lang_options,
        index=current_index, key="lang_select_sidebar"
    )
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()

# ----------------- Global Audio Byte Generator -----------------
def get_kannada_audio_bytes(text: str):
    if not text: return None
    try:
        tts = gTTS(text=text, lang='kn', slow=False)
        audio_bytes_io = BytesIO()
        tts.write_to_fp(audio_bytes_io)
        audio_bytes_io.seek(0)
        return audio_bytes_io.read()
    except Exception as e:
        print(f"gTTS Error: {e}")
        return None

# ----------------- Translation Helpers -----------------
def translate_to_english(text):
    try:
        lang = detect(text)
        if lang == "en": return text, "en"
        return GoogleTranslator(source=lang, target="en").translate(text), lang
    except:
        return text, "kn" 

def translate_back(text, target_lang):
    try:
        if target_lang == "en": return text
        return GoogleTranslator(source="en", target=target_lang).translate(text)
    except:
        return text

# ----------------- (NEW) Login Check -----------------
def check_login():
    """
    Checks if user is logged in. If not, shows login page and stops execution.
    This must be called at the *very top* of every page.
    """
    initialize_firebase() # Make sure Firebase is initialized
    
    if "user" not in st.session_state:
        # Hide the sidebar on the login page
        st.markdown("<style>[data-testid='stSidebar'] {display: none;}</style>", unsafe_allow_html=True)
        render_login_signup() # Show the login/signup form
        st.stop() # Stop execution of the rest of the page

# ----------------- (NEW) Sidebar with Logout (FIXED) -----------------
def render_sidebar():
    """Renders the sidebar for all logged-in pages."""
    lang = st.session_state.get("lang", "English")
    with st.sidebar:
        st.markdown(f"### {t('Settings', lang)}")
        language_toggle()
        
        # --- (FIX) ADDED THIS SECTION BACK ---
        st.markdown("---")
        # These values are hardcoded for now, but you could load them from .env if you want
        st.markdown(f"**{t('Model', lang)}:** `llama-3.3-70b-versatile`")
        st.markdown(f"**{t('Provider', lang)}:** `GROQ`")
        
        if st.button(t("Clear Chat History", lang)):
            # Get user info from session state
            user_id = st.session_state.user_id
            user_token = st.session_state.user['idToken']
            db = st.session_state.db
            
            # Clear locally
            st.session_state.messages = [] 
            st.session_state.audio_bytes_for_message = {}
            
            # Clear in database
            try:
                db.child("user_chats").child(user_id).set([], token=user_token)
            except Exception as e:
                st.error(f"Error clearing history: {e}")
            
            st.rerun()
        # --- (END OF FIX) ---
            
        st.markdown("---")
        st.write(f"{t('Logged in as', lang)}: **{st.session_state.user_email}**")
        if st.button(t("Logout", lang)):
            keys_to_delete = list(st.session_state.keys())
            for key in keys_to_delete:
                if key not in ['firebase_initialized', 'auth', 'db']:
                    del st.session_state[key]
            st.rerun()