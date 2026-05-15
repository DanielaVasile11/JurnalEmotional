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

st.set_page_config(page_title="MoodLift Jurnal", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

# --- PACHETELE MULTIMEDIA ---
from gtts import gTTS
import requests
from streamlit_lottie import st_lottie

# --- CONFIGURARE API GEMINI ---
GOOGLE_API_KEY = "AIzaSyDJLK91IY5ZZaGk9APgD27Ip6k2BGzjT5A"  # Pune cheia ta Gemini!
client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_ID = 'gemini-flash-latest'


# --- FUNCȚIE PENTRU ANIMAȚII ---
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

# Harta de culori fixă pentru consistență vizuală în toate graficele
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


init_db()


# ==============================================================================
# 3. GENERATOR AUTOMAT DE DATE (DATASET SINTETIC)
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

if st.session_state.logged_in:
    bg_color, txt_color = get_user_theme(st.session_state.username)
else:
    bg_color, txt_color = '#FEFBEA', '#5D4037'

UI = {
    "Română": {
        "nav_chat": "🖋️ Jurnal Emoțional", "nav_profile": "🗝️ Profilul Meu", "nav_admin": "📊 Dashboard Admin",
        "logout": "🚪 Deconectare", "end_btn": "Finalizează Sesiunea",
        "welcome": "Salut! Sunt MoodLift. Cum te simți astăzi?",
        "history_title": "ISTORICUL EMOȚIILOR MELE", "profile_title": "🗝️ PROFILUL MEU",
        "theme_title": "🎨 Personalizare Temă",
        "login_title": "🌿 Jurnalul Emoțional MoodLift"
    },
    "English": {
        "nav_chat": "🖋️ Emotional Journal", "nav_profile": "🗝️ My Profile", "nav_admin": "📊 Admin Dashboard",
        "logout": "🚪 Logout", "end_btn": "End Session", "welcome": "Hello! I'm MoodLift. How are you feeling today?",
        "history_title": "MY EMOTION HISTORY", "profile_title": "🗝️ MY PROFILE", "theme_title": "🎨 Theme Customization",
        "login_title": "🌿 MoodLift Emotional Journal"
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
header {{ visibility: visible !important; background: transparent !important; }}
[data-testid="collapsedControl"] {{ visibility: visible !important; display: flex !important; color: {txt_color} !important; }}
[data-testid="stToolbar"] {{ visibility: hidden !important; }} 
.stButton button {{ background-color: transparent !important; border: 1px solid {txt_color} !important; color: {txt_color} !important; border-radius: 20px !important; }}
div[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{ background-color: {txt_color}15 !important; border: 1px solid {txt_color}33 !important; border-radius: 12px; }}
[data-testid="stFooter"] {{visibility: hidden;}}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# LOGICA DE PAGINI
# ==============================================================================
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title(t["login_title"])
        tab1, tab2 = st.tabs(["🔒 Autentificare", "📝 Creare Cont"])
        with tab1:
            u = st.text_input("Utilizator", key="l_u")
            p = st.text_input("Parolă", type="password", key="l_p")
            if st.button("Conectare"):
                if verify_user(u, p):
                    st.session_state.logged_in, st.session_state.username = True, u
                    st.session_state.logged_in_display_name = get_display_name(u)
                    st.session_state.messages = [{"role": "assistant", "content": t["welcome"], "audio": None}]
                    st.rerun()
                else:
                    st.error("Eroare la conectare!")
else:
    with st.sidebar:
        st.title("📖 Meniul Meu")
        optiuni = [t["nav_admin"], t["nav_profile"]] if st.session_state.username == "admin" else [t["nav_chat"],
                                                                                                   t["nav_profile"]]
        pagina = st.radio("✒️ Răsfoiește paginile:", optiuni)
        st.write("---")
        if pagina == t["nav_chat"]:
            if st.button("✅ " + t["end_btn"], use_container_width=True):
                pred = max(set(st.session_state.emotion_history),
                           key=st.session_state.emotion_history.count) if st.session_state.emotion_history else st.session_state.last_emotion
                st.session_state.predominant_emotion = pred
                save_emotion_to_history(st.session_state.username, pred, st.session_state.messages)
                st.session_state.session_ended = True
                st.rerun()
        if st.button(t["logout"], use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # ==============================================================================
    # 4. DASHBOARD ADMIN (ACTUALIZAT CRONOLOGIC PE PACIENT)
    # ==============================================================================
    if pagina == t.get("nav_admin"):
        st.title("📊 Analiză Comportamentală și Evoluție Pacienți")

        if st.button("⚡ Populează Baza (50 Înregistrări Sintetice)"):
            generate_synthetic_batch()
            st.rerun()

        conn = sqlite3.connect('moodlift_users.db')
        df = pd.read_sql_query("SELECT username, date, emotion FROM history", conn)
        conn.close()

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])

            # 1. Grafice Globale
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Distribuția Emoțiilor (Global)")
                fig_p = px.pie(df, names='emotion', color='emotion', color_discrete_map=CULORI_EMOTII)
                st.plotly_chart(fig_p, use_container_width=True)
            with c2:
                st.subheader("Top Pacienți Activi")
                st.bar_chart(df['username'].value_counts())

            st.write("---")
            st.subheader("👤 Analiză Detaliată și Evoluție Temporală Pacient")
            pacient = st.selectbox("Alege pacientul pentru analiză cronologică și comparativă:",
                                   df['username'].unique())

            # Sortăm datele pacientului cronologic pentru ca linia de timp să aibă sens
            df_ind = df[df['username'] == pacient].sort_values('date')
            df_pop = df[df['username'] != pacient]

            # 2. NOU: Evoluția Temporală SPECIFICĂ pacientului selectat
            st.markdown(f"📈 **Evoluția cronologică a stărilor pentru `{pacient}`**")
            if not df_ind.empty:
                fig_line = px.line(df_ind, x='date', y='emotion', color_discrete_sequence=['#4682B4'], markers=True)
                # Ordonăm axa verticală logic: de la emoții negative jos, la cele pozitive sus
                fig_line.update_yaxes(categoryorder='array',
                                      categoryarray=['disgust', 'anger', 'fear', 'sadness', 'neutral', 'surprise',
                                                     'joy'])
                fig_line.update_layout(xaxis_title="Dată și Oră", yaxis_title="Stare Emoțională Înregistrată")
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.caption("Nu există date suficiente pentru un istoric temporal.")

            # 3. Benchmarking (Reparat: range_y=[0, 100] folosit corect)
            st.write("")
            st.markdown(f"⚖️ **Comparație Procentuală: `{pacient}` vs. Restul Populației**")

            b1, b2 = st.columns(2)
            with b1:
                st.markdown(f"**Distribuție `{pacient}`**")
                pct_ind = df_ind['emotion'].value_counts(normalize=True).reset_index()
                pct_ind.columns = ['emotion', 'procent'];
                pct_ind['procent'] *= 100

                # REPARAT: Folosim range_y=[0, 100] ca argument corect
                fig_bar_ind = px.bar(pct_ind, x='emotion', y='procent', color='emotion',
                                     color_discrete_map=CULORI_EMOTII, range_y=[0, 100])
                fig_bar_ind.update_layout(showlegend=False, xaxis_title="Emoție", yaxis_title="Procent (%)")
                st.plotly_chart(fig_bar_ind, use_container_width=True)

            with b2:
                st.markdown("**Media celorlalți pacienți (Norma)**")
                pct_pop = df_pop['emotion'].value_counts(normalize=True).reset_index()
                pct_pop.columns = ['emotion', 'procent'];
                pct_pop['procent'] *= 100

                # REPARAT: Folosim range_y=[0, 100] ca argument corect
                fig_bar_pop = px.bar(pct_pop, x='emotion', y='procent', color='emotion',
                                     color_discrete_map=CULORI_EMOTII, range_y=[0, 100])
                fig_bar_pop.update_layout(showlegend=False, xaxis_title="Emoție", yaxis_title="Procent (%)")
                st.plotly_chart(fig_bar_pop, use_container_width=True)

            # 4. Export Dataset CSV
            st.write("---")
            st.subheader("📂 Export Date (Compilare Dataset)")
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descarcă Baza de Date (.CSV)", data=csv,
                               file_name=f"moodlift_dataset_{int(time.time())}.csv", mime="text/csv")
        else:
            st.info("Baza de date este goală.")

    # --- PROFIL ---
    elif pagina == t["nav_profile"]:
        st.title(t["profile_title"])
        st.subheader(t["theme_title"])
        c_bg, c_txt = st.columns(2)
        new_bg = c_bg.color_picker("Culoare Fundal", bg_color)
        new_txt = c_txt.color_picker("Culoare Text", txt_color)
        if st.button("Salvează Tema"):
            if update_user_theme(st.session_state.username, new_bg, new_txt):
                st.success("Temă actualizată!");
                time.sleep(0.5);
                st.rerun()

        st.write("---")
        st.subheader(t["history_title"])
        for r in get_history(st.session_state.username):
            with st.expander(f"🗓️ {r[1]} - {r[2].upper()}"):
                for m in json.loads(r[3]): st.write(f"**{m['role']}:** {m['content']}")

    # --- CHAT ---
    else:
        if st.session_state.session_ended:
            st.title("📊 Rezumat Zi")
            anim = load_lottieurl(LOTTIE_URLS.get(st.session_state.predominant_emotion, LOTTIE_URLS["neutral"]))
            if anim: st_lottie(anim, height=200)
            st.success(f"Emoție predominantă: **{st.session_state.predominant_emotion.upper()}**")
            if st.button("Pagină Nouă"):
                st.session_state.session_ended, st.session_state.messages, st.session_state.emotion_history = False, [], []
                st.rerun()
            st.stop()

        st.title(t["nav_chat"])
        anim_data = load_lottieurl(LOTTIE_URLS.get(st.session_state.last_emotion, LOTTIE_URLS["neutral"]))
        if anim_data: st_lottie(anim_data, height=100)

        for m in st.session_state.messages:
            with st.chat_message(m["role"]):
                st.write(m["content"])
                if m.get("audio"): st.audio(m["audio"])

        if prompt := st.chat_input("Cum te simți azi?"):
            with st.chat_message("user"):
                st.write(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            tradus = GoogleTranslator(source='auto', target='en').translate(prompt)
            res = classifier(tradus)
            emo = res[0][0]['label'] if isinstance(res[0], list) else res[0]['label']
            st.session_state.last_emotion = emo
            st.session_state.emotion_history.append(emo)

            with st.chat_message("assistant"):
                resp = client.models.generate_content(model=MODEL_ID,
                                                      contents=f"Mood: {emo}. Raspunde empatic in {st.session_state.lang}: " + prompt)
                txt = resp.text
                st.write(txt)
                a_file = f"v_{int(time.time())}.mp3"
                try:
                    gTTS(text=txt, lang='ro' if st.session_state.lang == "Română" else 'en').save(a_file); st.audio(
                        a_file)
                except:
                    a_file = None
                st.session_state.messages.append({"role": "assistant", "content": txt, "audio": a_file})
                st.rerun()