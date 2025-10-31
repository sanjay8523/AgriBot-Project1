# auth.py
import streamlit as st
import pyrebase
import time

# -----------------
# YOUR FIREBASE CONFIG
# -----------------
firebaseConfig = {
  "apiKey": "AIzaSyD6NJYPC6q27mgd43fIfg0bsfFC4_7ptTs",
  "authDomain": "agribot-project-c2cc7.firebaseapp.com",
  "projectId": "agribot-project-c2cc7",
  "storageBucket": "agribot-project-c2cc7.firebasestorage.app",
  "messagingSenderId": "72191469603",
  "appId": "1:72191469603:web:9312f9a448f9f748372996",
  "databaseURL": "https://agribot-project-c2cc7-default-rtdb.firebaseio.com"
}
# -----------------
# (END) CONFIG
# -----------------

# (NEW) --- Initialization Function ---
def initialize_firebase():
    """
    Initializes Firebase and stores connections in session state.
    """
    if "firebase_initialized" not in st.session_state:
        try:
            firebase = pyrebase.initialize_app(firebaseConfig)
            auth = firebase.auth()
            db = firebase.database() 
            st.session_state.firebase_initialized = True
            st.session_state.auth = auth
            st.session_state.db = db
            print("Firebase Initialized Successfully")
        except Exception as e:
            st.session_state.firebase_initialized = False
            st.session_state.firebase_error = f"Firebase initialization failed: {e}"

# Function to render the login/signup UI
def render_login_signup():
    """Shows a login/signup form and returns when a user is logged in."""
    
    if not st.session_state.get("firebase_initialized", False):
        st.error(st.session_state.get("firebase_error", "Firebase connection failed."))
        st.stop()
        
    st.markdown("<h1 style='text-align: center;'>Welcome to Agri-Bot</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Please login or sign up to continue</h3>", unsafe_allow_html=True)

    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])

    with login_tab:
        with st.form(key="login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")
            
            if login_button:
                if email and password:
                    try:
                        user = st.session_state.auth.sign_in_with_email_and_password(email, password)
                        st.session_state.user = user 
                        st.session_state.user_email = user['email']
                        st.session_state.user_id = user['localId'] 
                        st.success("Logged in successfully!")
                        st.rerun() 
                    except Exception as e:
                        st.error(f"Login failed. Please check your email/password.")
                else:
                    st.warning("Please enter both email and password.")

    with signup_tab:
        with st.form(key="signup_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            signup_button = st.form_submit_button("Sign Up")

            if signup_button:
                if email and password and confirm_password:
                    if password == confirm_password:
                        try:
                            user = st.session_state.auth.create_user_with_email_and_password(email, password)
                            st.session_state.user = user
                            st.session_state.user_email = user['email']
                            st.session_state.user_id = user['localId']
                            user_id = user['localId']
                            st.session_state.db.child("user_chats").child(user_id).set([], user['idToken'])
                            st.success("Account created! Logging you in...")
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Account creation failed. The email might already be in use.")
                    else:
                        st.error("Passwords do not match.")
                else:
                    st.warning("Please fill out all fields.")