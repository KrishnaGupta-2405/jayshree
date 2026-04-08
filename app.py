import streamlit as st
import nltk
from nltk.tokenize import word_tokenize
from sklearn.feature_extraction.text import CountVectorizer
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# -------- PAGE CONFIG --------
st.set_page_config(
    page_title="AI Privacy Guard",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------- NLTK --------
try:
    nltk.data.find('tokenizers/punkt')
except:
    nltk.download('punkt')

# -------- DATABASE --------
conn = sqlite3.connect("privacy_guard.db", check_same_thread=False)
c = conn.cursor()

c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT, password TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS history (username TEXT, url TEXT, risk TEXT, score INTEGER)")
conn.commit()

# -------- SESSION --------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if "result" not in st.session_state:
    st.session_state.result = None

if "last_url" not in st.session_state:
    st.session_state.last_url = ""

# -------- KEYWORDS --------
keywords = [
    "data sharing","sell data","third party","location tracking",
    "cookies tracking","behavioral ads","advertising partners","personal data sharing"
]

# -------- FETCH --------
def fetch_policy(url):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)
        driver.get(url)
        time.sleep(3)

        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            if "privacy" in link.text.lower():
                privacy_url = link.get_attribute("href")
                if privacy_url:
                    driver.get(privacy_url)
                    time.sleep(3)
                    break

        text = driver.find_element(By.TAG_NAME, "body").text.lower()
        text = text.replace("\n", "")
        driver.quit()
        return text

    except Exception as e:
        print("Error:", e)
        return ""

# -------- ANALYZE --------
def analyze_policy(text):
    if not text or len(text.strip()) < 50:
        return "Low Risk ⚠️", 10, [], ["⚠️ Not enough data"]

    negative_words = ["not", "no", "never", "do not", "does not"]
    found = []

    for key in keywords:
        if key in text:
            is_safe = False
            for neg in negative_words:
                if neg + " " + key in text:
                    is_safe = True
            if not is_safe:
                found.append(key)

    if "share" in text and "data" in text:
        if "not share" not in text and "do not share" not in text:
            found.append("data sharing")

    found = list(set(found))
    score = len(found) * 25
    score = min(score, 100)

    if score > 70:
        risk = "High Risk ❌"
    elif score > 40:
        risk = "Medium Risk ⚠️"
    else:
        risk = "Low Risk ✅"

    suggestions = []
    if "third party" in found or "data sharing" in found:
        suggestions.append("⚠️ Data may be shared with third parties")
    if "location tracking" in found:
        suggestions.append("📍 Location tracking detected")
    if "cookies tracking" in found:
        suggestions.append("🍪 Cookies used for tracking")
    if "behavioral ads" in found:
        suggestions.append("📢 Personalized ads detected")

    return risk, score, found, suggestions

def generate_pdf(url, risk, score, found, suggestions):
    import io
    from reportlab.platypus import Image as RLImage

    file_path = "report.pdf"
    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name='TitleStyle',
        fontSize=22,
        textColor=colors.HexColor("#0B5394"),
        spaceAfter=15,
        alignment=1
    )
    heading_style = ParagraphStyle(
        name='HeadingStyle',
        fontSize=14,
        textColor=colors.HexColor("#333333"),
        spaceAfter=8
    )
    normal_style = ParagraphStyle(
        name='NormalStyle',
        fontSize=11,
        spaceAfter=5
    )

    if "High" in risk:
        risk_color = colors.red
    elif "Medium" in risk:
        risk_color = colors.orange
    else:
        risk_color = colors.green

    # -------- Generate Chart Image --------
    bar_color = '#e74c3c' if score > 70 else '#f39c12' if score > 40 else '#2ecc71'
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(["Risk Score", "Safe Score"], [score, 100 - score], color=[bar_color, '#95a5a6'], width=0.4)
    ax.set_ylim(0, 115)
    ax.set_title("Risk Breakdown", fontsize=13, fontweight='bold')
    for bar in ax.patches:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 2,
            f'{int(bar.get_height())}',
            ha='center', va='bottom', fontsize=12, fontweight='bold'
        )
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='PNG', dpi=150)
    img_buffer.seek(0)
    plt.close(fig)

    content = []
    content.append(Paragraph("AI Privacy Guard Report", title_style))
    content.append(Spacer(1, 10))

    data = [
        ["Website URL", url],
        ["Risk Level", risk],
        ["Risk Score", f"{score}/100"]
    ]

    table = Table(data, colWidths=[130, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 1), (-1, 1), risk_color),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))

    content.append(table)
    content.append(Spacer(1, 20))

    content.append(Paragraph("Detected Privacy Risks", heading_style))
    if found:
        for i, k in enumerate(found, 1):
            content.append(Paragraph(f"{i}. {k.title()}", normal_style))
    else:
        content.append(Paragraph("No major risky keywords detected.", normal_style))

    content.append(Spacer(1, 15))
    content.append(Paragraph("Analysis & Recommendations", heading_style))
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            content.append(Paragraph(f"{i}. {s}", normal_style))
    else:
        content.append(Paragraph("The website appears safe with minimal risk.", normal_style))

    content.append(Spacer(1, 20))

    # -------- Add Chart to PDF --------
    content.append(Paragraph("Risk Chart", heading_style))
    content.append(Spacer(1, 8))
    chart_img = RLImage(img_buffer, width=300, height=180)
    content.append(chart_img)

    content.append(Spacer(1, 25))
    content.append(Paragraph(
        "This report is generated using AI-based Privacy Analysis system.",
        styles["Italic"]
    ))

    doc.build(content)
    return file_path


# ========================
#        SIDEBAR
# ========================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/lock.png", width=64)
    st.title("🔐 Privacy Guard")
    st.divider()

    if not st.session_state.logged_in:
        menu = st.radio("Navigation", ["🔑 Login", "📝 Register"], label_visibility="collapsed")
    else:
        st.success(f"👤 {st.session_state.username}")
        st.divider()
        page = st.radio(
            "Go to",
            ["🔍 Scan Website", "📋 History"],
            label_visibility="collapsed"
        )
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()


# ========================
#     NOT LOGGED IN
# ========================
if not st.session_state.logged_in:

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("## 🔐 AI Privacy Guard")
        st.caption("Analyze any website's privacy policy in seconds.")
        st.divider()

        # ---- REGISTER ----
        if menu == "📝 Register":
            st.subheader("Create Account")
            user = st.text_input("Username", placeholder="Choose a username")
            pwd = st.text_input("Password", type="password", placeholder="Choose a password")
            st.write("")
            if st.button("✅ Register", use_container_width=True, type="primary"):
                if user and pwd:
                    c.execute("INSERT INTO users VALUES (?,?)", (user, pwd))
                    conn.commit()
                    st.success("Account created! Please login.")
                else:
                    st.warning("Please fill all fields.")

        # ---- LOGIN ----
        elif menu == "🔑 Login":
            st.subheader("Welcome Back")
            user = st.text_input("Username", placeholder="Enter your username")
            pwd = st.text_input("Password", type="password", placeholder="Enter your password")
            st.write("")
            if st.button("🔓 Login", use_container_width=True, type="primary"):
                c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pwd))
                if c.fetchone():
                    st.session_state.logged_in = True
                    st.session_state.username = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")


# ========================
#      LOGGED IN
# ========================
else:

    # -------- SCAN PAGE --------
    if page == "🔍 Scan Website":

        st.title("🔍 Website Privacy Scanner")
        st.caption("Enter a website URL to analyze its privacy policy for potential risks.")
        st.divider()

        col_input, col_btn = st.columns([4, 1])
        with col_input:
            url = st.text_input(
                "Website URL",
                placeholder="https://example.com",
                label_visibility="collapsed",
                key="url_input"
            )
        with col_btn:
            scan_clicked = st.button("🚀 Scan", use_container_width=True, type="primary")

        if url != st.session_state.last_url:
            st.session_state.result = None

        if scan_clicked:
            if not url:
                st.warning("Please enter a URL first.")
            else:
                with st.spinner("🔍 Fetching & analyzing privacy policy..."):
                    text = fetch_policy(url)

                if len(text) < 50:
                    st.error("⚠️ Could not load content from that URL. Please check the link.")
                    st.stop()

                result = analyze_policy(text)
                st.session_state.result = result
                st.session_state.last_url = url

                risk, score, _, _ = result
                c.execute("INSERT INTO history VALUES (?,?,?,?)",
                          (st.session_state.username, url, risk, score))
                conn.commit()

        # -------- RESULTS --------
        if st.session_state.result:
            risk, score, found, suggestions = st.session_state.result

            st.divider()
            st.subheader("📊 Analysis Results")

            # Metric cards
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🎯 Risk Level", risk)
            with col2:
                st.metric("📈 Risk Score", f"{score} / 100")
            with col3:
                st.metric("🔑 Keywords Found", len(found))

            st.divider()

            col_left, col_right = st.columns(2)

            # Keywords
            with col_left:
                st.subheader("⚠️ Detected Keywords")
                if found:
                    for k in found:
                        st.warning(f"🔴 {k.title()}")
                else:
                    st.success("✅ No risky keywords found!")

            # Suggestions
            with col_right:
                st.subheader("💡 Recommendations")
                if suggestions:
                    for s in suggestions:
                        st.info(s)
                else:
                    st.success("✅ This website appears safe!")

            st.divider()

            # Chart
            st.subheader("📉 Risk Breakdown")

            fig, ax = plt.subplots(figsize=(7, 3.5))
            fig.patch.set_facecolor('#0e1117')
            ax.set_facecolor('#0e1117')

            bar_colors = ['#e74c3c' if score > 70 else '#f39c12' if score > 40 else '#2ecc71', '#2c3e50']
            bars = ax.bar(
                ["Risk Score", "Safe Score"],
                [score, 100 - score],
                color=bar_colors,
                width=0.4,
                edgecolor='none'
            )
            ax.set_ylim(0, 110)
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.tick_params(colors='white', labelsize=11)
            ax.spines['bottom'].set_color('#444')
            ax.spines['left'].set_color('#444')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 2,
                    f'{int(height)}',
                    ha='center', va='bottom',
                    color='white', fontsize=13, fontweight='bold'
                )

            st.pyplot(fig)

            st.divider()

            # Download
            pdf_file = generate_pdf(url, risk, score, found, suggestions)
            with open(pdf_file, "rb") as f:
                st.download_button(
                    label="📄 Download Full Report (PDF)",
                    data=f,
                    file_name="Privacy_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )

    # -------- HISTORY PAGE --------
    elif page == "📋 History":

        st.title("📋 Scan History")
        st.caption("All your previously scanned websites.")
        st.divider()

        data = c.execute(
            "SELECT * FROM history WHERE username=?",
            (st.session_state.username,)
        ).fetchall()

        df = pd.DataFrame(data, columns=["User", "URL", "Risk", "Score"])
        df['Score'] = pd.to_numeric(df["Score"], errors="coerce")
        df["Score"] = df["Score"].fillna(0)

        if df.empty:
            st.info("No scans yet. Go to 'Scan Website' to get started!")
        else:
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔢 Total Scans", len(df))
            with col2:
                st.metric("📈 Avg Risk Score", f"{df['Score'].mean():.1f}")
            with col3:
                high_risk = len(df[df["Risk"].str.contains("High", na=False)])
                st.metric("🔴 High Risk Sites", high_risk)

            st.divider()
            st.subheader("📊 Score Trend")

            fig2, ax2 = plt.subplots(figsize=(9, 3.5))
            fig2.patch.set_facecolor('#0e1117')
            ax2.set_facecolor('#0e1117')

            x = range(len(df))
            ax2.plot(list(x), df["Score"].tolist(), color='#3498db', linewidth=2.5, marker='o', markersize=7)
            ax2.fill_between(list(x), df["Score"].tolist(), alpha=0.15, color='#3498db')
            ax2.set_xticks(list(x))
            ax2.set_xticklabels(
                [u[:18] + "..." if len(u) > 18 else u for u in df["URL"]],
                rotation=30, ha='right', color='white', fontsize=8
            )
            ax2.set_ylim(0, 110)
            ax2.tick_params(colors='white')
            ax2.spines['bottom'].set_color('#444')
            ax2.spines['left'].set_color('#444')
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)
            ax2.set_ylabel("Risk Score", color='white')
            st.pyplot(fig2)

            st.divider()
            st.subheader("🗂️ Full History")
            st.dataframe(
                df[["URL", "Risk", "Score"]],
                use_container_width=True,
                hide_index=True
            )
