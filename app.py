# ==============================================================================
# 1. CONFIGURARE ȘI IMPORTURI
# ==============================================================================
import streamlit as st
from google import genai
from transformers import pipeline
from deep_translator import GoogleTranslator
import sqlite3
import hashlib
from datetime import datetime
import os
import time
import json
import random
import pandas as pd
import plotly.express as px
import anthropic
from openai import OpenAI
from groq import Groq
st.set_page_config(page_title="MoodLift Jurnal", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")
import os
from dotenv import load_dotenv
# --- PACHETELE MULTIMEDIA ---
from gtts import gTTS
import requests
from streamlit_lottie import st_lottie

load_dotenv()

GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_ID = 'gemini-flash-latest'


API_KEY_CLAUDE = os.getenv("CLAUDE_API_KEY")
API_KEY_DEEPSEEK = os.getenv("DEEPSEEK_API_KEY")
API_KEY_GROQ = os.getenv("GROQ_API_KEY")
# Inițializăm "telefoanele" prin care aplicația sună la roboți:
client_claude = anthropic.Anthropic(api_key=API_KEY_CLAUDE)
client_deepseek = OpenAI(api_key=API_KEY_DEEPSEEK, base_url="https://api.deepseek.com")
client_groq = Groq(api_key=API_KEY_GROQ)

def load_lottieurl(url: str):
    try:
        r = requests.get(url, timeout=5)
        if r.status_code != 200: return None
        return r.json()
    except:
        return None


LOTTIE_URLS = {
    "joy": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f31e/lottie.json",
    "surprise": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f632/lottie.json",
    "sadness": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f327/lottie.json",
    "fear": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f628/lottie.json",
    "anger": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f621/lottie.json",
    "disgust": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f922/lottie.json",
    "neutral": "https://fonts.gstatic.com/s/e/notoemoji/latest/1f343/lottie.json"
}

# --- MUZICA LOCALĂ  ---
MUZICA_TERAPIE = {
    "joy": {"nume": "Muzică Veselă", "fisier": "muzica/joy.mp3"},
    "sadness": {"nume": "Pian Relaxant", "fisier": "muzica/sadness.mp3"},
    "anger": {"nume": "Sunete din Natură", "fisier": "muzica/anger.mp3"},
    "fear": {"nume": "Frecvențe Calmate", "fisier": "muzica/fear.mp3"},
    "surprise": {"nume": "Muzică Clasică", "fisier": "muzica/surprise.mp3"},
    "disgust": {"nume": "Chitară Acustică", "fisier": "muzica/disgust.mp3"},
    "neutral": {"nume": "Lo-Fi Beats", "fisier": "muzica/neutral.mp3"}
}

CULORI_EMOTII = {
    "joy": "#FFD700", "sadness": "#4682B4", "anger": "#DC143C",
    "fear": "#800080", "surprise": "#FF8C00", "disgust": "#8B4513", "neutral": "#808080"
}


@st.cache_resource
def load_emotion_model():
    return pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=1)


classifier = load_emotion_model()


# ==============================================================================
# 2. BAZA DE DATE
# ==============================================================================
def init_db():
    conn = sqlite3.connect('moodlift_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profiles (username TEXT PRIMARY KEY, display_name TEXT)''')
    c.execute(
        '''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, emotion TEXT, conversation TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS themes (username TEXT PRIMARY KEY, bg_color TEXT, text_color TEXT)''')
    c.execute(
        '''CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, date TEXT, rating INTEGER, comment TEXT)''')
    conn.commit()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", ("admin", hash_password("admin")))
        c.execute("INSERT INTO profiles (username, display_name) VALUES (?, ?)", ("admin", "Administrator"))
        c.execute("INSERT INTO themes (username, bg_color, text_color) VALUES (?, '#FEFBEA', '#5D4037')", ("admin",))
        conn.commit()
    except:
        pass
    conn.close()


def hash_password(password): return hashlib.sha256(str.encode(password)).hexdigest()


def verify_user(username, password):
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = c.fetchone();
    conn.close()
    return result and result[0] == hash_password(password)


def get_display_name(username):
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    c.execute("SELECT display_name FROM profiles WHERE username = ?", (username,))
    result = c.fetchone();
    conn.close()
    return result[0] if result else username


def get_user_theme(username):
    try:
        conn = sqlite3.connect('moodlift_users.db');
        c = conn.cursor()
        c.execute("SELECT bg_color, text_color FROM themes WHERE username = ?", (username,))
        res = c.fetchone();
        conn.close()
        if res and res[0] and res[1]: return res[0], res[1]
    except:
        pass
    return '#FEFBEA', '#5D4037'


def update_user_theme(username, bg, txt):
    try:
        conn = sqlite3.connect('moodlift_users.db');
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO themes (username, bg_color, text_color) VALUES (?, ?, ?)",
                  (username, bg, txt))
        conn.commit();
        conn.close()
        return True
    except:
        return False


def save_emotion_to_history(username, emotion, messages):
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    azi = datetime.now().strftime("%Y-%m-%d %H:%M")
    conversatie_salvata = json.dumps(messages)
    c.execute("INSERT INTO history (username, date, emotion, conversation) VALUES (?, ?, ?, ?)",
              (username, azi, emotion, conversatie_salvata))
    conn.commit();
    conn.close()


def get_history(username):
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    c.execute("SELECT id, date, emotion, conversation FROM history WHERE username = ? ORDER BY id DESC", (username,))
    data = c.fetchall();
    conn.close()
    return data


def delete_history_entry(entry_id):
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE id = ?", (entry_id,))
    conn.commit();
    conn.close()


def save_feedback(username, rating, comment):
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    azi = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute("INSERT INTO feedback (username, date, rating, comment) VALUES (?, ?, ?, ?)",
              (username, azi, rating, comment))
    conn.commit();
    conn.close()


def get_feedback(username):
    conn = sqlite3.connect('moodlift_users.db')
    df = pd.read_sql_query("SELECT date, rating, comment FROM feedback WHERE username = ? ORDER BY id DESC", conn,
                           params=(username,))
    conn.close()
    return df


init_db()


# ==============================================================================
# 3. GENERATOR AUTOMAT DE DATE
# ==============================================================================
def generate_synthetic_batch():
    conn = sqlite3.connect('moodlift_users.db');
    c = conn.cursor()
    nume_pacienti = ["Elena", "Andrei", "Maria", "Mihai", "Ioana", "Alexandru", "Diana", "Gabriel", "Roxana", "Vlad"]
    ponderi = [0.20, 0.30, 0.15, 0.15, 0.05, 0.05, 0.10]
    emotii = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]

    for _ in range(50):
        user = random.choice(nume_pacienti)
        em = random.choices(emotii, weights=ponderi, k=1)[0]
        ziua = random.randint(1, 28)
        luna = random.choice([4, 5])
        ora = random.randint(9, 19)
        data_s = f"2026-{luna:02d}-{ziua:02d} {ora:02d}:00"
        c.execute("INSERT INTO history (username, date, emotion, conversation) VALUES (?, ?, ?, ?)",
                  (user, data_s, em, "[]"))

        if random.random() < 0.3:
            rating = random.randint(3, 5)
            comment = random.choice(["Foarte util azi.", "M-a ajutat să mă calmez.", "Chat-ul a fost ok.",
                                     "Un pic prea repetitiv, dar m-am liniștit."])
            c.execute("INSERT INTO feedback (username, date, rating, comment) VALUES (?, ?, ?, ?)",
                      (user, data_s, rating, comment))

    conn.commit();
    conn.close()


# ==============================================================================
# STARE SESIUNE
# ==============================================================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""
if "logged_in_display_name" not in st.session_state: st.session_state.logged_in_display_name = ""
if "lang" not in st.session_state: st.session_state.lang = "Română"
if "messages" not in st.session_state: st.session_state.messages = []
if "session_ended" not in st.session_state: st.session_state.session_ended = False
if "last_emotion" not in st.session_state: st.session_state.last_emotion = "neutral"
if "emotion_history" not in st.session_state: st.session_state.emotion_history = []
if "predominant_emotion" not in st.session_state: st.session_state.predominant_emotion = "neutral"
if "feedback_submitted" not in st.session_state: st.session_state.feedback_submitted = False

if st.session_state.logged_in:
    bg_color, txt_color = get_user_theme(st.session_state.username)
else:
    bg_color, txt_color = '#FEFBEA', '#5D4037'

# ==============================================================================
# DICȚIONAR TRADUCERI COMPLETE
# ==============================================================================
UI = {
    "Română": {
        "nav_chat": "🖋️ Jurnal Emoțional", "nav_profile": "🗝️ Profilul Meu", "nav_admin": "📊 Dashboard Admin",
        "logout": "🚪 Deconectare", "end_btn": "Finalizează Sesiunea",
        "welcome": "Salut! Sunt MoodLift. Cum te simți astăzi?",
        "history_title": "ISTORICUL EMOȚIILOR MELE", "profile_title": "🗝️ PROFILUL MEU",
        "theme_title": "🎨 Personalizare Temă", "theme_bg": "Culoare Fundal", "theme_txt": "Culoare Text",
        "btn_save_theme": "Salvează Tema", "theme_success": "Temă actualizată!",
        "login_title": "🌿 Jurnalul Emoțional MoodLift",
        "name_title": "Schimbă Numele Utilizatorului", "name_input": "Numele afișat", "btn_name": "Actualizează Numele",
        "name_success": "Numele a fost actualizat!",
        "lang_title": "🌐 Limba Aplicației", "lang_radio": "Alege limba jurnalului:",
        "pass_title": "Schimbă Parola", "pass_old": "Parola veche", "pass_new": "Parola nouă",
        "btn_pass": "Actualizează Parola", "pass_success": "Parola a fost schimbată cu succes!",
        "pass_err": "Parola veche este incorectă!",
        "hist_empty": "Încă nu ai finalizat nicio sesiune.", "hist_inv": "Formatul conversației este invalid.",
        "hist_old": "Sesiune mai veche, salvată doar cu emoția (fără text).", "btn_del": "🗑️ Șterge Jurnalul",
        "login_tab1": "🔒 Autentificare", "login_tab2": "📝 Creare Cont", "login_user": "Utilizator",
        "login_pass": "Parolă", "btn_login": "Conectare", "login_err": "Eroare la conectare!",
        "chat_input_hint": "Cum te simți azi?", "chat_summary": "📊 Rezumat Zi",
        "chat_predominant": "Emoție predominantă:", "chat_new_page": "Pagină Nouă (Reset)", "you": "Tu",
        "admin_title": "📊 Analiză Comportamentală și Evoluție Pacienți",
        "btn_pop": "⚡ Populează Baza (50 Înregistrări)",
        "dist_global": "Distribuția Emoțiilor (Global)", "top_patients": "Top Pacienți Activi",
        "det_analysis": "👤 Analiză Detaliată Pacient",
        "sel_patient": "Alege pacientul pentru analiză:", "trend_for": "📈 **Evoluția stărilor pentru",
        "no_data": "Nu există date suficiente.",
        "comp_pct": "⚖️ **Comparație Procentuală:", "vs_rest": "vs. Restul Populației**", "dist_of": "**Distribuție",
        "norm": "**Media globală (Norma)**",
        "x_emo": "Emoție", "y_pct": "Procent (%)", "export_title": "📂 Export Date",
        "btn_export": "📥 Descarcă Baza (.CSV)", "db_empty": "Baza de date este goală.",
        "x_date": "Dată și Oră", "y_state": "Stare Emoțională Înregistrată",
        "fb_title": "💬 Lasă-ne părerea ta!", "fb_rating": "Cât de utilă a fost discuția azi?",
        "fb_comment": "Detalii (ce am putea îmbunătăți?):", "btn_fb": "Trimite Feedback",
        "fb_thanks": "Mulțumim mult pentru feedback!",
        "admin_fb_title": "💬 Feedback Lăsat de Pacient", "admin_no_fb": "Acest utilizator nu a lăsat recenzii.",
        "music_ask": "🎵 Dorești să asculți puțină muzică terapeutică? Îți propunem:",
        "music_err": "⚠️ Te rog să creezi folderul 'muzica' și să adaugi fișierele MP3."
    },
    "English": {
        "nav_chat": "🖋️ Emotional Journal", "nav_profile": "🗝️ My Profile", "nav_admin": "📊 Admin Dashboard",
        "logout": "🚪 Logout", "end_btn": "End Session", "welcome": "Hello! I'm MoodLift. How are you feeling today?",
        "history_title": "MY EMOTION HISTORY", "profile_title": "🗝️ MY PROFILE",
        "theme_title": "🎨 Theme Customization", "theme_bg": "Background Color", "theme_txt": "Text Color",
        "btn_save_theme": "Save Theme", "theme_success": "Theme updated!",
        "login_title": "🌿 MoodLift Emotional Journal",
        "name_title": "Change Username", "name_input": "Display Name", "btn_name": "Update Name",
        "name_success": "Name successfully updated!",
        "lang_title": "🌐 Application Language", "lang_radio": "Choose journal language:",
        "pass_title": "Change Password", "pass_old": "Old Password", "pass_new": "New Password",
        "btn_pass": "Update Password", "pass_success": "Password successfully changed!",
        "pass_err": "Old password is incorrect!",
        "hist_empty": "No sessions finished yet.", "hist_inv": "Invalid conversation format.",
        "hist_old": "Older session, saved only with emotion (no text).", "btn_del": "🗑️ Delete Journal",
        "login_tab1": "🔒 Login", "login_tab2": "📝 Create Account", "login_user": "Username", "login_pass": "Password",
        "btn_login": "Login", "login_err": "Login error!",
        "chat_input_hint": "How are you feeling today?", "chat_summary": "📊 Daily Summary",
        "chat_predominant": "Predominant emotion:", "chat_new_page": "New Page (Reset)", "you": "You",
        "admin_title": "📊 Behavioral Analysis & Patient Evolution", "btn_pop": "⚡ Populate Database (50 Records)",
        "dist_global": "Emotion Distribution (Global)", "top_patients": "Top Active Patients",
        "det_analysis": "👤 Detailed Patient Analysis",
        "sel_patient": "Select patient for analysis:", "trend_for": "📈 **Mood evolution for",
        "no_data": "Not enough data.",
        "comp_pct": "⚖️ **Percentage Comparison:", "vs_rest": "vs. Rest of Population**", "dist_of": "**Distribution",
        "norm": "**Global Average (Norm)**",
        "x_emo": "Emotion", "y_pct": "Percentage (%)", "export_title": "📂 Export Data",
        "btn_export": "📥 Download Database (.CSV)", "db_empty": "The database is empty.",
        "x_date": "Date and Time", "y_state": "Recorded Emotional State",
        "fb_title": "💬 Leave your feedback!", "fb_rating": "How helpful was today's discussion?",
        "fb_comment": "Details (what can we improve?):", "btn_fb": "Submit Feedback",
        "fb_thanks": "Thank you so much for your feedback!",
        "admin_fb_title": "💬 Feedback Left by Patient", "admin_no_fb": "This user hasn't left any reviews.",
        "music_ask": "🎵 Would you like to listen to some music? We suggest:",
        "music_err": "⚠️ Please create the 'muzica' folder and add the MP3 files."
    }
}
t = UI[st.session_state.lang]

# ==============================================================================
# CSS DINAMIC
# ==============================================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400;1,600&display=swap');
html, body, [class*="css"], .stMarkdown p, .stMarkdown div, label, h1, h2, h3, h4, h5, h6 {{
    font-family: 'Cormorant Garamond', serif !important; color: {txt_color} !important; font-size: 1.15rem; 
}}

[data-testid="stAppViewContainer"] {{ background-color: {bg_color} !important; background-image: radial-gradient(rgba(0,0,0,0.06) 1px, transparent 1px); background-size: 40px 40px; }}
[data-testid="stSidebar"] {{ background-color: {bg_color} !important; border-right: 1px solid rgba(0,0,0,0.1); }}

/* ASCUNDEM HEADER-UL SI BUTONUL DEFINITIV */
header {{ display: none !important; }}
[data-testid="collapsedControl"] {{ display: none !important; }}

.stButton button {{ background-color: transparent !important; border: 1px solid {txt_color} !important; color: {txt_color} !important; border-radius: 20px !important; }}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{ background-color: {txt_color}15 !important; border: 1px solid {txt_color}33 !important; border-radius: 12px; }}
[data-testid="stFooter"] {{ visibility: hidden !important; }}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# LOGICA DE PAGINI
# ==============================================================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title(t["login_title"])
        tab1, tab2 = st.tabs([t["login_tab1"], t["login_tab2"]])
        with tab1:
            u = st.text_input(t["login_user"], key="l_u")
            p = st.text_input(t["login_pass"], type="password", key="l_p")
            if st.button(t["btn_login"]):
                if verify_user(u, p):
                    st.session_state.logged_in, st.session_state.username = True, u
                    st.session_state.logged_in_display_name = get_display_name(u)
                    st.session_state.messages = [{"role": "assistant", "content": t["welcome"], "audio": None}]
                    st.rerun()
                else:
                    st.error(t["login_err"])
else:
    with st.sidebar:
        st.title("📖 " + ("Meniul Meu" if st.session_state.lang == "Română" else "My Menu"))
        # Adăugăm pagina de "Laborator Date"
        optiuni = [t["nav_admin"], t["nav_profile"], "🧪 Laborator Date"] if st.session_state.username == "admin" else [
            t["nav_chat"], t["nav_profile"]]
        pagina = st.radio("✒️ " + ("Răsfoiește paginile:" if st.session_state.lang == "Română" else "Browse pages:"),
                          optiuni)
        st.write("---")
        if pagina == t["nav_chat"]:
            if st.button("✅ " + t["end_btn"], use_container_width=True):
                pred = max(set(st.session_state.emotion_history),
                           key=st.session_state.emotion_history.count) if st.session_state.emotion_history else st.session_state.last_emotion
                st.session_state.predominant_emotion = pred
                save_emotion_to_history(st.session_state.username, pred, st.session_state.messages)
                st.session_state.session_ended = True
                st.session_state.feedback_submitted = False
                st.rerun()
        if st.button(t["logout"], use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # ==============================================================================
    # 4. DASHBOARD ADMIN
    # ==============================================================================
    if pagina == t.get("nav_admin"):
        st.title(t["admin_title"])

        if st.button(t["btn_pop"]):
            generate_synthetic_batch()
            st.rerun()

        conn = sqlite3.connect('moodlift_users.db')
        df = pd.read_sql_query("SELECT username, date, emotion, conversation FROM history", conn)
        conn.close()

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])

            c1, c2 = st.columns(2)
            with c1:
                st.subheader(t["dist_global"])
                fig_p = px.pie(df, names='emotion', color='emotion', color_discrete_map=CULORI_EMOTII)
                st.plotly_chart(fig_p, use_container_width=True)
            with c2:
                st.subheader(t["top_patients"])
                st.bar_chart(df['username'].value_counts())

            st.write("---")
            st.subheader(t["det_analysis"])
            pacient = st.selectbox(t["sel_patient"], df['username'].unique())

            df_ind = df[df['username'] == pacient].sort_values('date')
            df_pop = df[df['username'] != pacient]

            st.markdown(f"{t['trend_for']} `{pacient}`**")
            if not df_ind.empty:
                fig_line = px.line(df_ind, x='date', y='emotion', color_discrete_sequence=['#4682B4'], markers=True)
                fig_line.update_yaxes(categoryorder='array',
                                      categoryarray=['disgust', 'anger', 'fear', 'sadness', 'neutral', 'surprise',
                                                     'joy'])
                fig_line.update_layout(xaxis_title=t["x_date"], yaxis_title=t["y_state"])
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.caption(t["no_data"])

            st.write("")
            st.subheader(f"{t['admin_fb_title']} (`{pacient}`)")
            df_fb = get_feedback(pacient)
            if not df_fb.empty:
                media_stele = df_fb['rating'].mean()
                st.markdown(f"**Media evaluărilor:** {media_stele:.1f} / 5.0 ⭐")
                for index, row in df_fb.head(5).iterrows():
                    stele = "⭐" * int(row['rating'])
                    comentariu = row['comment'] if row['comment'] else "Fără comentariu text."
                    st.info(f"📅 **{row['date']}** | Evaluare: {stele}\n\n💬 *„{comentariu}”*")
            else:
                st.caption(t["admin_no_fb"])

            st.write("---")
            st.markdown(f"{t['comp_pct']} `{pacient}` {t['vs_rest']}")

            b1, b2 = st.columns(2)
            with b1:
                st.markdown(f"{t['dist_of']} `{pacient}`**")
                pct_ind = df_ind['emotion'].value_counts(normalize=True).reset_index()
                pct_ind.columns = ['emotion', 'procent'];
                pct_ind['procent'] *= 100
                fig_bar_ind = px.bar(pct_ind, x='emotion', y='procent', color='emotion',
                                     color_discrete_map=CULORI_EMOTII, range_y=[0, 100])
                fig_bar_ind.update_layout(showlegend=False, xaxis_title=t["x_emo"], yaxis_title=t["y_pct"])
                st.plotly_chart(fig_bar_ind, use_container_width=True)

            with b2:
                st.markdown(t["norm"])
                pct_pop = df_pop['emotion'].value_counts(normalize=True).reset_index()
                pct_pop.columns = ['emotion', 'procent'];
                pct_pop['procent'] *= 100
                fig_bar_pop = px.bar(pct_pop, x='emotion', y='procent', color='emotion',
                                     color_discrete_map=CULORI_EMOTII, range_y=[0, 100])
                fig_bar_pop.update_layout(showlegend=False, xaxis_title=t["x_emo"], yaxis_title=t["y_pct"])
                st.plotly_chart(fig_bar_pop, use_container_width=True)

            st.write("---")
            st.subheader(t["export_title"])
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(t["btn_export"], data=csv, file_name=f"moodlift_dataset_{int(time.time())}.csv",
                               mime="text/csv")
        else:
            st.info(t["db_empty"])

    # ==============================================================================
    # 5. PAGINA PROFIL
    # ==============================================================================
    elif pagina == t["nav_profile"]:
        st.title(t["profile_title"])
        conectat = "Connected as:" if st.session_state.lang == "English" else "Conectat curent ca:"
        st.caption(f"*({conectat} **{st.session_state.logged_in_display_name}**)*")
        st.write("---")

        col_st1, col_center, col_st2 = st.columns([1, 4, 1])
        with col_center:
            col_avatar1, col_info1 = st.columns([1, 2])
            with col_avatar1:
                st.image(
                    "https://api.dicebear.com/7.x/adventurer-neutral/svg?seed=" + st.session_state.username + "&backgroundColor=transparent",
                    width=120)
            with col_info1:
                st.subheader(t["name_title"])
                disp_name = st.text_input(t["name_input"], value=st.session_state.logged_in_display_name)
                if st.button(t["btn_name"]):
                    conn = sqlite3.connect('moodlift_users.db');
                    c = conn.cursor()
                    c.execute("UPDATE profiles SET display_name = ? WHERE username = ?",
                              (disp_name, st.session_state.username))
                    conn.commit();
                    conn.close()
                    st.session_state.logged_in_display_name = disp_name
                    st.success(t["name_success"])

            st.write("---")
            st.subheader(t["lang_title"])
            selected_lang = st.radio(t["lang_radio"], ["Română", "English"],
                                     index=0 if st.session_state.lang == "Română" else 1)
            if selected_lang != st.session_state.lang:
                st.session_state.lang = selected_lang
                st.session_state.messages = [
                    {"role": "assistant", "content": UI[selected_lang]["welcome"], "audio": None}]
                st.rerun()

            st.write("---")
            st.subheader(t["theme_title"])
            col_bg, col_txt = st.columns(2)
            with col_bg:
                new_bg = st.color_picker(t["theme_bg"], bg_color)
            with col_txt:
                new_txt = st.color_picker(t["theme_txt"], txt_color)

            if st.button(t["btn_save_theme"]):
                if update_user_theme(st.session_state.username, new_bg, new_txt):
                    st.success(t["theme_success"]);
                    time.sleep(0.5);
                    st.rerun()

            st.write("---")
            st.subheader(t["pass_title"])
            old_p = st.text_input(t["pass_old"], type="password")
            new_p = st.text_input(t["pass_new"], type="password")
            if st.button(t["btn_pass"]):
                if verify_user(st.session_state.username, old_p):
                    conn = sqlite3.connect('moodlift_users.db');
                    c = conn.cursor()
                    c.execute("UPDATE users SET password = ? WHERE username = ?",
                              (hash_password(new_p), st.session_state.username))
                    conn.commit();
                    conn.close()
                    st.success(t["pass_success"])
                else:
                    st.error(t["pass_err"])

            st.write("---")
            st.subheader(t["history_title"])

            istoric_date = get_history(st.session_state.username)
            if istoric_date:
                for r in istoric_date:
                    entry_id = r[0]
                    with st.expander(f"🗓️ {r[1]}  —  {r[2].upper()}"):
                        if len(r) > 3 and r[3]:
                            try:
                                for m in json.loads(r[3]):
                                    rol = t["you"] if m["role"] == "user" else "MoodLift"
                                    st.write(f"**{rol}:** {m['content']}")
                            except:
                                st.caption(t["hist_inv"])
                        else:
                            st.caption(t["hist_old"])

                        st.write("")
                        col_del1, col_del2 = st.columns([3, 2])
                        with col_del2:
                            if st.button(t["btn_del"], key=f"del_{entry_id}"):
                                delete_history_entry(entry_id)
                                st.rerun()
            else:
                st.info(t["hist_empty"])

                # =====================================================================
                # 5.5.  PAGINA DE DATA AUGMENTATION
                # =====================================================================
    elif pagina == "🧪 Laborator Date":
                st.title("🧪 Laborator Data Augmentation")
                st.write(
                    "Acest modul folosește AI pentru a genera date sintetice și a echilibra clasele minoritare, permițând compararea performanței mai multor modele.")

                # Citim datele actuale
                conn = sqlite3.connect('moodlift_users.db')
                df_all = pd.read_sql_query("SELECT emotion FROM history", conn)
                conn.close()

                if not df_all.empty:
                    st.subheader("1. Distribuția curentă (Înainte de augmentare)")
                    dist = df_all['emotion'].value_counts(normalize=True).reset_index()
                    dist.columns = ['Emoție', 'Procentaj']
                    dist['Procentaj'] = dist['Procentaj'] * 100

                    fig_before = px.bar(dist, x='Emoție', y='Procentaj', color='Emoție',
                                        color_discrete_map=CULORI_EMOTII)
                    st.plotly_chart(fig_before, use_container_width=True)

                    # ---------------- NOU: MENIU DE SELECȚIE AI & EMOȚII ----------------
                    st.write("---")
                    st.subheader("🛠️ Setări Augmentare Comparativă")

                    # 1. Alegerea robotului AI
                    ai_ales = st.selectbox("🤖 Alege modelul AI pentru generarea datelor:",
                                           ["Gemini 1.5 (Google)", "Claude 3 (Anthropic)", "DeepSeek",
                                            "Llama 3 (Groq)"])

                    # Setarea numelui de utilizator în funcție de AI-ul ales
                    if ai_ales == "Gemini 1.5 (Google)":
                        username_fals = "admin_gemini"
                    elif ai_ales == "Claude 3 (Anthropic)":
                        username_fals = "admin_claude"
                    elif ai_ales == "DeepSeek":
                        username_fals = "admin_deepseek"
                    elif ai_ales == "Llama 3 (Groq)":
                        username_fals = "admin_llama"

                    # 2. Alegerea emoțiilor
                    st.write("**Alege emoțiile care au procentul cel mai mic pe grafic:**")
                    toate_emotiile = ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"]
                    clase_selectate = st.multiselect("Bifează emoțiile pe care vrei să le generezi:", toate_emotiile,
                                                     default=["surprise", "disgust"])

                    # Butonul magic de augmentare controlată
                    if st.button(f"🚀 Generează Date Sintetice cu {ai_ales}"):
                        if not clase_selectate:
                            st.warning("Te rog să selectezi cel puțin o emoție din meniu!")
                        else:
                            with st.spinner(
                                    f"{ai_ales} generează date pentru {', '.join(clase_selectate)}... te rog așteaptă."):
                                conn = sqlite3.connect('moodlift_users.db')
                                c = conn.cursor()
                                azi = datetime.now().strftime("%Y-%m-%d %H:%M")

                                for clasa in clase_selectate:
                                    prompt_aug = f"Generează 5 propoziții scurte (maxim 10-15 cuvinte fiecare), la persoana I, specifice unui jurnal emoțional, care exprimă clar emoția '{clasa}'. Răspunde DOAR cu propozițiile, câte una pe rând, fără numere sau alte comentarii."

                                    try:
                                        # Logica de direcționare a comenzii către robotul corect
                                        if ai_ales == "Gemini 1.5 (Google)":
                                            raspuns = client.models.generate_content(model=MODEL_ID,
                                                                                     contents=prompt_aug).text

                                        elif ai_ales == "Claude 3 (Anthropic)":
                                            mesaj_claude = client_claude.messages.create(
                                                model="claude-haiku-4-5",
                                                max_tokens=300,
                                                messages=[{"role": "user", "content": prompt_aug}]
                                            )
                                            raspuns = mesaj_claude.content[0].text

                                        elif ai_ales == "DeepSeek":
                                            mesaj_deepseek = client_deepseek.chat.completions.create(
                                                model="deepseek-chat",
                                                messages=[{"role": "user", "content": prompt_aug}]
                                            )
                                            raspuns = mesaj_deepseek.choices[0].message.content

                                        elif ai_ales == "Llama 3 (Groq)":
                                            mesaj_groq = client_groq.chat.completions.create(
                                                model="llama-3.1-8b-instant",
                                                messages=[{"role": "user", "content": prompt_aug}]
                                            )
                                            raspuns = mesaj_groq.choices[0].message.content

                                        # Procesăm textul primit și salvăm
                                        propozitii = raspuns.strip().split('\n')
                                        for prop in propozitii:
                                            if prop.strip() and len(prop.strip()) > 5:
                                                fake_conv = json.dumps([{"role": "user", "content": prop.strip()}])
                                                c.execute(
                                                    "INSERT INTO history (username, date, emotion, conversation) VALUES (?, ?, ?, ?)",
                                                    (username_fals, azi, clasa, fake_conv))
                                    except Exception as e:
                                        st.error(
                                            f"Eroare la {ai_ales} pentru clasa '{clasa}': Verificați cheia API sau fondurile. Detalii: {e}")

                                conn.commit()
                                conn.close()
                            st.success(f"✅ Datele au fost augmentate cu succes folosind {ai_ales}!")
                            time.sleep(1.5)
                            st.rerun()

                    # Zona de Undo
                    st.write("---")
                    st.write("**Zonă de curățare (Resetare la starea inițială):**")

                    if st.button("🗑️ Șterge TOATE Datele Sintetice (Undo)"):
                        conn = sqlite3.connect('moodlift_users.db')
                        c = conn.cursor()
                        # Am pus LIKE 'admin%' ca să șteargă orice începe cu admin (admin_gemini, admin_claude etc.)
                        c.execute("DELETE FROM history WHERE username LIKE 'admin%'")
                        conn.commit()
                        conn.close()

                        st.warning(
                            "✅ Toate datele sintetice (de la toți roboții) au fost șterse cu succes! Baza a revenit la Baseline.")
                        time.sleep(2)
                        st.rerun()

                else:
                    st.warning("Baza de date este goală. Apasă butonul de populare din Admin Dashboard mai întâi.")
    # ==============================================================================
    # 6. CHAT ȘI FEEDBACK
    # ==============================================================================
    else:
        if st.session_state.session_ended:
            st.title(t["chat_summary"])

            col_sum1, col_sum2 = st.columns([1, 2])
            with col_sum1:
                anim = load_lottieurl(LOTTIE_URLS.get(st.session_state.predominant_emotion, LOTTIE_URLS["neutral"]))
                if anim: st_lottie(anim, height=150)
            with col_sum2:
                st.write("")
                st.write("")
                st.success(f"{t['chat_predominant']} **{st.session_state.predominant_emotion.upper()}**")

            st.write("---")

            if not st.session_state.feedback_submitted:
                st.subheader(t["fb_title"])
                rating = st.slider(t["fb_rating"], 1, 5, 5, help="1 = Deloc util, 5 = Foarte util")
                comentariu = st.text_area(t["fb_comment"], height=100)

                if st.button(t["btn_fb"]):
                    save_feedback(st.session_state.username, rating, comentariu)
                    st.session_state.feedback_submitted = True
                    st.rerun()
            else:
                st.info(t["fb_thanks"])

            st.write("---")
            if st.button(t["chat_new_page"]):
                st.session_state.session_ended, st.session_state.messages, st.session_state.emotion_history = False, [], []
                st.rerun()
            st.stop()

        st.title(t["nav_chat"])
        anim_data = load_lottieurl(LOTTIE_URLS.get(st.session_state.last_emotion, LOTTIE_URLS["neutral"]))
        if anim_data: st_lottie(anim_data, height=100)

        # --- PLAYER AUDIO LOCAL ---
        st.write("---")
        melodie_curenta = MUZICA_TERAPIE.get(st.session_state.last_emotion, MUZICA_TERAPIE["neutral"])

        vrei_muzica = st.checkbox(f"{t['music_ask']} **{melodie_curenta['nume']}**")

        if vrei_muzica:
            if os.path.exists(melodie_curenta["fisier"]):
                st.audio(melodie_curenta["fisier"])
            else:
                st.warning(t["music_err"])

        st.write("---")
        # ----------------------------------------

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])
                if m.get("audio"): st.audio(m["audio"])

        if prompt := st.chat_input(t["chat_input_hint"]):
            with st.chat_message("user"):
                st.write(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            tradus = GoogleTranslator(source='auto', target='en').translate(prompt)
            res = classifier(tradus)
            emo = res[0][0]['label'] if isinstance(res[0], list) else res[0]['label']
            st.session_state.last_emotion = emo
            st.session_state.emotion_history.append(emo)

            with st.chat_message("assistant"):
                # Instrucțiuni îmbunătățite pentru Gemini
                system_instruction = f"""
                        Ești MoodLift, un asistent terapeutic proactiv și empatic. 
                        Reguli:
                        1. CRIZĂ: Dacă detectezi disperare sau intenții de auto-vătămare, activează PROTOCOLUL DE CRIZĂ: oferă tehnici de calmare și îndrumă-l ferm să contacteze un specialist/linie de urgență.
                        2. BUCURIE/EVOLUȚIE: Dacă utilizatorul raportează succes, fii entuziast, laudă progresul și încurajează-l.
                        3. STĂRI NEGATIVE: Dacă utilizatorul este stresat sau trist, fii empatic și proactiv: propune o tehnică de relaxare, un sport, un obicei sau o melodie.
                        CONSTRÂNGERI: Nu face recomandări la absolut fiecare mesaj. Fă-le doar ocazional, când contextul o cere.
                        Răspunde in limba {st.session_state.lang}.
                        """

                full_prompt = f"{system_instruction}\n\nStare emoțională detectată: {emo}\n\nUtilizatorul spune: {prompt}"

                resp = client.models.generate_content(model=MODEL_ID, contents=full_prompt)
                txt = resp.text
                st.write(txt)

                a_file = f"v_{int(time.time())}.mp3"
                try:
                    gTTS(text=txt, lang='ro' if st.session_state.lang == "Română" else 'en').save(a_file)
                    st.audio(a_file)
                except:
                    a_file = None

                st.session_state.messages.append({"role": "assistant", "content": txt, "audio": a_file})
                st.rerun()