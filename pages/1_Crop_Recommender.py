# pages/1_Crop_Recommender.py
import streamlit as st
import requests
import os
from groq import Groq
from datetime import datetime
import folium
import streamlit.components.v1 as components
from folium.plugins import MarkerCluster
from dotenv import load_dotenv
import io

# --- Import all required functions ---
from project_bot import render_project_bot
from utils import (
    apply_custom_css, t, get_kannada_audio_bytes,
    check_login, render_sidebar
)

# -----------------------------
# --- Main App Logic ---
# -----------------------------
apply_custom_css()
check_login()      
render_sidebar()   
# -----------------------------

lang = st.session_state.lang

# --- Get Firebase and User info ---
db = st.session_state.db
auth = st.session_state.auth
user_id = st.session_state.user_id
user_token = st.session_state.user['idToken']

load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ----------------- Load/Save User Data -----------------
def load_user_data():
    """Loads soil/location data from Firebase for the current user."""
    try:
        data = db.child("user_data").child(user_id).get(token=user_token).val()
        if data:
            return data
    except Exception as e:
        print(f"Error loading data (may be new user): {e}")
    # Return defaults if no data
    return {
        "location": {"state": "Select State", "district": "Select a state first", "month": datetime.now().strftime("%B")},
        "soil": {"n": 50.0, "p": 25.0, "k": 25.0, "ph": 6.5, "rainfall": 100.0}
    }

def save_user_data(data_to_save):
    """Saves soil/location data to Firebase for the current user."""
    try:
        db.child("user_data").child(user_id).set(data_to_save, token=user_token)
    except Exception as e:
        try:
            st.session_state.user = auth.refresh(st.session_state.user['refreshToken'])
            user_token = st.session_state.user['idToken'] 
            db.child("user_data").child(user_id).set(data_to_save, token=user_token) 
        except Exception as refresh_e:
            st.error(f"Error saving data. Your session may have expired. Please log out and log back in. {refresh_e}")

# ----------------- Load initial data -----------------
if "user_data" not in st.session_state:
    st.session_state.user_data = load_user_data()

# ----------------- Session State (Page Specific) -----------------
if "selected_crop" not in st.session_state: st.session_state.selected_crop = None
if "crops" not in st.session_state: st.session_state.crops = None
if "lat" not in st.session_state: st.session_state.lat = 12.9716
if "lon" not in st.session_state: st.session_state.lon = 77.5946

@st.cache_data(ttl=300)
def get_weather(lat, lon):
    if not OPENWEATHER_API_KEY: return {"temp": 25, "humidity": 60, "rainfall": 0, "desc": "Clear", "icon": "01d"}
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&appid={OPENWEATHER_API_KEY}"
        data = requests.get(url, timeout=10).json()
        if data.get("cod") == 200:
            return { "temp": round(data["main"]["temp"]), "humidity": data["main"]["humidity"], "rainfall": data.get("rain", {}).get("1h", 0), "desc": data["weather"][0]["description"].title(), "icon": data["weather"][0]["icon"] }
    except: pass
    return {"temp": 25, "humidity": 60, "rainfall": 0, "desc": "Clear", "icon": "01d"}

def get_crop_recommendations(n, p, k, ph, temp, hum, rain, state, district, month, lang):
    if not client: return ["1. Rice - Default", "2. Maize - Default", "3. Groundnut - Default"], "Rice Maize Groundnut"
    prompt = f"Recommend 3 crops for Indian farmer. Soil: N={n}, P={p}, K={k}, pH={ph}. Weather: {temp} deg C, {hum}% humidity, {rain} mm rain. Location: {state}, {district}, {month}. Rank: 1=best, 2=good, 3=viable. Format:\n1. [CROP] - [short reason]\n2. [CROP] - [short reason]\n3. [CROP] - [short reason]"
    if lang == "Kannada": prompt += " Answer in Kannada. Use 1. 2. 3."
    try:
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile", temperature=0.3, max_tokens=300)
        response = chat.choices[0].message.content.strip()
        crops = [line.strip() for line in response.split('\n') if line.strip().startswith(('1.', '2.', '3.'))]
        while len(crops) < 3: crops.append(f"{len(crops)+1}. Unknown - Error")
        if len(crops) >= 3:
            audio_text = " ".join([c.split('-')[0].replace('1.', '').replace('2.', '').replace('3.', '').strip() for c in crops[:3]])
            return crops[:3], audio_text
    except Exception as e: st.error(f"LLM Error: {e}")
    return ["1. Rice - Error", "2. Maize - Error", "3. Groundnut - Error"], "Rice Maize Groundnut"

def get_crop_guide(crop, state, district, month, lang):
    if not client: return t("Guide not available in demo mode.", lang)
    prompt = f"Complete growing guide for {crop} in {state}, {district} during {month}. Include: Soil preparation, Sowing time, Seed rate, Spacing, Irrigation, Fertilizer (NPK), Pest control, Harvesting, Yield per acre, Market tips. Use bullets."
    if lang == "Kannada": prompt += " Answer in Kannada."
    try:
        chat = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile", temperature=0.3, max_tokens=800)
        return chat.choices[0].message.content.strip()
    except Exception as e: return t(f"Error: {e}", lang)

FAMOUS_CROPS = { "Punjab": "Wheat 🌾", "Haryana": "Rice 🌾", "Uttar Pradesh": "Sugarcane 🍬", "Bihar": "Maize 🌽", "West Bengal": "Rice 🌾", "Odisha": "Rice 🌾", "Maharashtra": "Cotton ☁️", "Gujarat": "Groundnut 🥜", "Karnataka": "Ragi 🌾", "Kerala": "Coconut 🥥", "Tamil Nadu": "Rice 🌾", "Madhya Pradesh": "Soybean 🌱", "Andhra Pradesh": "Chillies 🌶️", "Telangana": "Cotton ☁️", "Rajasthan": "Bajra 🌾", "Assam": "Tea 🍃" }
STATE_COORDS = { "Punjab": (31.15, 75.34), "Haryana": (29.06, 76.08), "Uttar Pradesh": (26.84, 80.94), "Bihar": (25.59, 85.13), "West Bengal": (22.57, 88.36), "Odisha": (20.27, 85.84), "Maharashtra": (19.07, 72.88), "Gujarat": (22.30, 70.80), "Karnataka": (12.97, 77.59), "Kerala": (10.85, 76.27), "Tamil Nadu": (13.08, 80.27), "Madhya Pradesh": (23.25, 77.41), "Andhra Pradesh": (15.91, 79.74), "Telangana": (17.39, 78.49), "Rajasthan": (26.91, 75.79), "Assam": (26.20, 92.93) }
INDIA_STATES_DISTRICTS = { "Andhra Pradesh": ["Anantapur", "Chittoor", "Guntur", "Krishna", "Kurnool", "Visakhapatnam"], "Karnataka": [ "Bagalkote", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban", "Bidar", "Chamarajanagara", "Chikkaballapura", "Chikkamagaluru", "Chitradurga", "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri", "Kalaburagi", "Kodagu", "Kolar", "Koppal", "Mandya", "Mysuru", "Raichur", "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada", "Vijayapura", "Yadgir" ], "Kerala": ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Thiruvananthapuram"], "Maharashtra": ["Ahmednagar", "Aurangabad", "Kolhapu", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nashik", "Pune", "Satara", "Thane"], "Tamil Nadu": ["Chennai", "Coimbatore", "Kanchipuram", "Kanyakumari", "Madurai", "Salem", "Tiruchirappalli", "Vellore"], "Uttar Pradesh": ["Agra", "Aligarh", "Allahabad", "Bareilly", "Ghaziabad", "Gorakhpur", "Kanpur", "Lucknow", "Meerut", "Varanasi"] }
MONTHS_LIST = [ "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December" ]

lat, lon = st.session_state.lat, st.session_state.lon; weather = get_weather(lat, lon)
temp, hum, rain = weather["temp"], weather["humidity"], weather["rainfall"]; desc, icon = weather["desc"], weather["icon"]
icon_url = f"https://openweathermap.org/img/wn/{icon}@2x.png" 
_, col_w = st.columns([1, 6]);
with col_w:
    st.markdown(f"**{temp}°C** | {t('Humidity', lang)}: {hum}% | {t('Rain', lang)}: {rain}mm | <img src='{icon_url}' alt='{desc}' width='25' height='25' style='vertical-align: middle; margin-bottom: 5px;'> {t(desc, lang)}", unsafe_allow_html=True)

st.markdown(f"<h1 style='text-align:center;'>{t('AI Crop Recommender', lang)}</h1>", unsafe_allow_html=True)
tab1, tab2 = st.tabs([ f"📍 {t('Recommend Crops', lang)}", f"🗺️ {t('Crop Map', lang)}" ]) 

with tab1:
    st.markdown(f"<h3 style='text-align:center;'>{t('Enter Soil & Location Data', lang)}</h3>", unsafe_allow_html=True)
    states_list = sorted(list(INDIA_STATES_DISTRICTS.keys()))
    
    saved_loc = st.session_state.user_data.get("location", {})
    saved_soil = st.session_state.user_data.get("soil", {})
    
    try:
        state_index = states_list.index(saved_loc.get("state", "Select State")) + 1
    except ValueError:
        state_index = 0

    col1, col2, col3 = st.columns(3)
    with col1: 
        selected_state_rec = st.selectbox( 
            t("State", lang), 
            ["Select State"] + states_list, 
            key="state_select_rec", 
            index=state_index
        )
    with col2:
        district_options = [t("Select a state first", lang)]; district_disabled = True; district_index = 0
        if selected_state_rec != "Select State": 
            district_options = ["Select District"] + sorted(INDIA_STATES_DISTRICTS[selected_state_rec])
            district_disabled = False
            try:
                district_index = district_options.index(saved_loc.get("district", "Select District"))
            except ValueError:
                district_index = 0
        selected_district = st.selectbox( t("District", lang), options=district_options, disabled=district_disabled, key="district_select_unified", index=district_index)
    with col3:
        current_month = datetime.now().strftime("%B")
        saved_month = saved_loc.get("month", current_month)
        month_index = MONTHS_LIST.index(saved_month) + 1 if saved_month in MONTHS_LIST else 0
        selected_month = st.selectbox(t("Month", lang), ["Select Month"] + MONTHS_LIST, index=month_index, key="month_select")

    if st.button(t("Save Location", lang)):
         if selected_state_rec == "Select State" or selected_district in ["Select District", t("Select a state first", lang)] or selected_month == "Select Month": st.error(t("Please select a valid State, District, and Month.", lang))
         else: 
             st.session_state.user_data["location"] = {"state": selected_state_rec, "district": selected_district, "month": selected_month}
             save_user_data(st.session_state.user_data)
             st.success(t("Location saved!", lang) + f" ({selected_state_rec}, {selected_district})")
    
    st.markdown(f"### {t('Soil & Weather Data', lang)}")
    col1, col2, col3 = st.columns(3); col4, col5, col6 = st.columns(3)
    with col1: n = st.number_input(t("Nitrogen (N)", lang), 0.0, value=saved_soil.get("n", 50.0), step=1.0)
    with col2: p = st.number_input(t("Phosphorus (P)", lang), 0.0, value=saved_soil.get("p", 25.0), step=1.0)
    with col3: k = st.number_input(t("Potassium (K)", lang), 0.0, value=saved_soil.get("k", 25.0), step=1.0)
    with col4: ph = st.number_input(t("pH", lang), 0.0, 14.0, value=saved_soil.get("ph", 6.5), step=0.1)
    with col5: temp_in = st.number_input(t("Temperature (°C)", lang), 0.0, value=float(temp), step=0.5)
    with col6: hum_in = st.number_input(t("Humidity (%)", lang), 0.0, value=float(hum), step=1.0)
    rainfall = st.number_input(t("Rainfall (mm)", lang), 0.0, value=saved_soil.get("rainfall", 100.0), step=10.0)
    
    if st.button(t("Get Crop Recommendations", lang), type="primary"):
        if "state" not in st.session_state.user_data.get("location", {}): 
            st.error(t("Please save a location first.", lang))
        else:
            st.session_state.user_data["soil"] = {"n": n, "p": p, "k": k, "ph": ph, "rainfall": rainfall}
            save_user_data(st.session_state.user_data)
            loc = st.session_state.user_data["location"]
            crops, audio_text = get_crop_recommendations( n, p, k, ph, temp_in, hum_in, rainfall, loc["state"], loc["district"], loc["month"], lang )
            st.session_state.crops = crops
            if lang == "Kannada" and audio_text: 
                audio_bytes = get_kannada_audio_bytes(audio_text)
                if audio_bytes: st.audio(audio_bytes, autoplay=True, format="audio/mp3")

    if st.session_state.get("crops"):
        st.markdown(f"### {t('Top 3 Recommended Crops', lang)}")
        rank_labels = [t("Highly Recommended", lang), t("Good Choice", lang), t("Viable Option", lang)]; colors = ["#2e7d32", "#f9a825", "#e65100"]
        recommendations = st.session_state.crops
        while len(recommendations) < 3: recommendations.append("Error fetching recommendation")
        
        for i, line in enumerate(recommendations[:3]):
             parts = line.split('-', 1)
             crop_name = parts[0].strip().lstrip('1234567890. ') if len(parts) > 0 else "Unknown"
             reason = parts[1].strip() if len(parts) > 1 else "No reason provided"
             
             col_a, col_b = st.columns([1, 4])
             with col_a:
                 st.markdown(f"""
                 <div style='background:{colors[i]}; color:white; padding:12px; border-radius:12px; text-align:center; font-weight:600;'>
                     {rank_labels[i]}
                 </div>
                 """, unsafe_allow_html=True)
             with col_b:
                 is_error = "error" in crop_name.lower() or "unknown" in crop_name.lower()
                 if st.button(crop_name, key=f"crop_{i}", use_container_width=True, disabled=is_error):
                      st.session_state.selected_crop = crop_name
             st.markdown(f"<small>{reason}</small>", unsafe_allow_html=True) # Text will be colored by CSS
        
        if st.session_state.get("selected_crop"):
            loc = st.session_state.user_data.get("location") 
            if loc and "state" in loc:
                guide = get_crop_guide( st.session_state.selected_crop, loc["state"], loc["district"], loc["month"], lang )
                st.markdown(f"### {t('Complete Guide for', lang)} **{st.session_state.selected_crop}**")
                
                # --- (THIS IS THE FIX) ---
                # Use the new .info-box class instead of inline style
                st.markdown(f"""<div class='info-box'>{guide.replace('•', '<br>•')}</div>""", unsafe_allow_html=True)
                # --- (END OF FIX) ---
                
                if lang == "Kannada": 
                    audio_bytes = get_kannada_audio_bytes(guide[:500])
                    if audio_bytes: st.audio(audio_bytes, autoplay=True, format="audio/mp3")
            else:
                st.error(t("Please save your location first.", lang))

with tab2:
    st.markdown(f"<h3 style='text-align:center;'>{t('Famous Crops by State (India)', lang)}</h3>", unsafe_allow_html=True); st.markdown(f"<p style='text-align:center;'>{t('This is a static map showing major crops.', lang)}</p>", unsafe_allow_html=True)
    m = folium.Map(location=[22.97, 78.65], zoom_start=5); marker_cluster = MarkerCluster().add_to(m)
    for state, crop in FAMOUS_CROPS.items():
        coords = STATE_COORDS.get(state)
        if coords: popup = f"<b>{state}</b><br>{t('Famous Crop', lang)}: {t(crop, lang)}"; folium.Marker( location=coords, popup=popup, tooltip=f"{state}: {crop}", icon=folium.Icon(color='green', icon='leaf')).add_to(marker_cluster)
    map_html = m._repr_html_()
    components.html(map_html, height=600)

render_project_bot()
