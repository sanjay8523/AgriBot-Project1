# AgriBot.py
import os
import time
import base64
import requests
import streamlit as st
import speech_recognition as sr
from langdetect import detect
from groq import Groq
from dotenv import load_dotenv, find_dotenv
import io
from typing import List, Dict
from gtts import gTTS

# --- (NEW) Import the authentication, project bot, and utils ---
from project_bot import render_project_bot
from utils import (
    apply_custom_css, t, get_kannada_audio_bytes,
    check_login, render_sidebar, # Import login check and sidebar
    translate_to_english, translate_back
)

# -----------------------------
# (NEW) --- Main App Logic ---
# -----------------------------
apply_custom_css() # Apply CSS *before* the login check
check_login()      # <-- This is the login gate.
render_sidebar()   # <-- This renders the sidebar with "Logout"
# -----------------------------

# --- USER IS LOGGED IN, SHOW THE CHATBOT PAGE ---

# -----------------------------
# Load environment variables & Clients
# -----------------------------
load_dotenv(find_dotenv())
GROQ_KEY = os.getenv("GROQ_API_KEY")
API_KEY = GROQ_KEY
if not GROQ_KEY: st.error("GROQ_API_KEY is not set!"); st.stop()
PROVIDER = "GROQ"; DEFAULT_BASE = "https://api.groq.com/openai/v1"; DEFAULT_MODEL = "llama-3.3-70b-versatile"
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", DEFAULT_BASE); MODEL = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
RETRIES = int(os.getenv("API_RETRIES", 2))
client = Groq(api_key=GROQ_KEY)
r = sr.Recognizer()

db = st.session_state.db
auth = st.session_state.auth
user_id = st.session_state.user_id
user_token = st.session_state.user['idToken']

# -----------------------------
# Load Chat History from Firebase
# -----------------------------
if "messages" not in st.session_state:
    try:
        chat_history = db.child("user_chats").child(user_id).get(token=user_token).val()
        st.session_state.messages = chat_history if chat_history else []
    except Exception as e:
        print(f"Error loading chat history: {e}")
        st.session_state.messages = []

if "last_audio_hash" not in st.session_state: st.session_state.last_audio_hash = None
if "audio_bytes_for_message" not in st.session_state: st.session_state.audio_bytes_for_message = {}

# -----------------------------
# API Call with Chat History
# -----------------------------
def call_chat_api(message_history: List[Dict[str, str]], max_retries: int = RETRIES) -> str:
    if not API_KEY: raise EnvironmentError("Missing API key in .env")
    messages_payload = [{"role": "system", "content": "You are an expert agriculture and farming assistant for Indian farmers. Answer concisely and helpfully. If asked in Kannada, answer in Kannada."}]
    messages_payload.extend(message_history[-10:])
    url = OPENAI_API_BASE.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL, "messages": messages_payload, "temperature": 0.3, "max_tokens": 700}
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=40)
            if resp.status_code == 200: return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e: last_error = str(e); time.sleep(1 * attempt)
    raise RuntimeError(f"API failed: {last_error}")

# -----------------------------
# Title
# -----------------------------
lang = st.session_state.lang
st.markdown(f"<h1 style='text-align:center;'>{t('Agri-Bot: Your Smart Farming Assistant', lang)}</h1>", unsafe_allow_html=True)
st.markdown(f"<h3 style='text-align:center;'>{t('Powered by AI', lang)}</h3>", unsafe_allow_html=True)

# -----------------------------
# Chat Messages Display
# -----------------------------
message_counter = 0
if st.session_state.messages is None: st.session_state.messages = []
for msg in st.session_state.messages:
    message_counter += 1
    msg_key = f"msg_{message_counter}"
    avatar = "🌱" if msg["role"] == "assistant" else "🧑‍🌾"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg_key in st.session_state.audio_bytes_for_message:
            audio_bytes = st.session_state.audio_bytes_for_message[msg_key]
            if st.button(f"🔊 {t('Play Kannada', lang)}", key=f"play_btn_{msg_key}"):
                 st.audio(audio_bytes, format="audio/mp3", autoplay=True)

# -----------------------------
# Input Area & Voice Input
# -----------------------------
user_input_text = st.chat_input(t("Type in Kannada or English…", lang))
user_input_voice = None
st.markdown("###") # Spacer
audio_bytes_obj = st.audio_input(label=t("Or record your voice (press, speak, press again)", lang))

if audio_bytes_obj:
    audio_data_bytes = audio_bytes_obj.read()
    current_audio_hash = hash(audio_data_bytes)
    if current_audio_hash != st.session_state.last_audio_hash:
        st.session_state.last_audio_hash = current_audio_hash
        st.info(t("Processing voice input...", lang))
        try:
            wav_file = io.BytesIO(audio_data_bytes)
            with sr.AudioFile(wav_file) as source: audio_data = r.record(source)
            user_input_voice = r.recognize_google(audio_data, language="kn-IN")
        except Exception as e:
            st.error(t("Sorry, I could not understand the audio.", lang))

# -----------------------------
# Process Input (Text or Voice)
# -----------------------------
user_input = user_input_text or user_input_voice

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    message_counter += 1 
    
    with st.chat_message("user", avatar="🧑‍🌾"):
        st.markdown(user_input)

    with st.spinner(t("Thinking…", lang)):
        try:
            eng_query, orig_lang = translate_to_english(user_input)
            history = st.session_state.messages
            answer = call_chat_api(history)
            final_answer = translate_back(answer, orig_lang)
            st.session_state.messages.append({"role": "assistant", "content": final_answer})
            message_counter += 1 
            assistant_msg_key = f"msg_{message_counter}"
            if orig_lang == "kn":
                audio_bytes = get_kannada_audio_bytes(final_answer)
                if audio_bytes:
                    st.session_state.audio_bytes_for_message[assistant_msg_key] = audio_bytes
            try:
                db.child("user_chats").child(user_id).set(st.session_state.messages, token=user_token)
            except Exception as e:
                try:
                    st.session_state.user = auth.refresh(st.session_state.user['refreshToken'])
                    user_token = st.session_state.user['idToken'] 
                    db.child("user_chats").child(user_id).set(st.session_state.messages, token=user_token)
                except Exception as refresh_e:
                    st.error(f"Error saving chat. Session expired. Please log out and log back in. {refresh_e}")
            st.rerun() 
        except Exception as e:
            st.error(f"Error: {e}")

# Render the floating bot at the end
render_project_bot()