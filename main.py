import streamlit as st
import mysql.connector
import base64
import pandas as pd
from PIL import Image
import io

# ---------------------------
# MySQL Connection Function
# ---------------------------
def get_connection():
    return mysql.connector.connect(
        host=st.secrets["DB_HOST"],
        port=st.secrets["DB_PORT"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASS"],
        database=st.secrets["DB_NAME"],
        ssl_ca="ssl/ca.pem"   # keep your SSL cert if required
    )

# ---------------------------
# Fetch Data from DB
# ---------------------------
@st.cache_data
def fetch_news():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, cleaned_title, malayalam_title, date, tag, image_data,
               cleaned_description, malayalam_description
        FROM news_articles_four
        ORDER BY date DESC
        LIMIT 500;
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(rows)

# ---------------------------
# Fetch Unique Tags
# ---------------------------
@st.cache_data
def fetch_unique_tags():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT tag FROM news_articles_four WHERE tag IS NOT NULL")
    tags = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return sorted(tags)

# ---------------------------
# Decode & Validate Base64 Image
# ---------------------------
def decode_image(base64_str):
    try:
        img_bytes = base64.b64decode(base64_str) if base64_str else None
        if img_bytes:
            # Validate if it’s a real image
            Image.open(io.BytesIO(img_bytes))
        return img_bytes
    except Exception:
        return None

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Medical News", layout="wide")

# ---------------------------
# Language Selection Popup
# ---------------------------
if "language" not in st.session_state:
    st.title("🌐 Select Language")
    st.write("Please select your preferred language to continue:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("English 🇬🇧"):
            st.session_state.language = "english"
            st.rerun()
    with col2:
        if st.button("മലയാളം 🇮🇳"):
            st.session_state.language = "malayalam"
            st.rerun()
    st.stop()

# ---------------------------
# Sidebar: Language Switch
# ---------------------------
st.sidebar.header("⚙️ Settings")
lang_choice = st.sidebar.radio(
    "Choose Language",
    options=["English 🇬🇧", "മലയാളം 🇮🇳"],
    index=0 if st.session_state.language == "english" else 1
)

if "English" in lang_choice:
    st.session_state.language = "english"
else:
    st.session_state.language = "malayalam"

# ---------------------------
# Main Portal
# ---------------------------
st.title("🩺 Medical News Portal")

# Load news and tags
df = fetch_news()
unique_tags = fetch_unique_tags()

# Sidebar Search
st.sidebar.header("🔎 Search Options")
search_query = st.sidebar.text_input("Search news")
search_tag = st.sidebar.selectbox("Search by tag", ["All"] + unique_tags)

# Filter DataFrame
filtered_df = df.copy()
if search_query:
    if st.session_state.language == "english":
        filtered_df = filtered_df[
            filtered_df["cleaned_title"].str.contains(search_query, case=False, na=False) |
            filtered_df["cleaned_description"].str.contains(search_query, case=False, na=False)
        ]
    else:  # Malayalam
        filtered_df = filtered_df[
            filtered_df["malayalam_title"].str.contains(search_query, case=False, na=False) |
            filtered_df["malayalam_description"].str.contains(search_query, case=False, na=False)
        ]

if search_tag != "All":
    filtered_df = filtered_df[filtered_df["tag"] == search_tag]

# Display Results: 2 per row
if filtered_df.empty:
    st.warning("No news found. Try different keywords or tags.")
else:
    rows = filtered_df.to_dict(orient='records')
    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j < len(rows):
                row = rows[i + j]
                with col:
                    if st.session_state.language == "english":
                        st.subheader(row["cleaned_title"])
                        desc = row["cleaned_description"] or ""
                    else:
                        st.subheader(row["malayalam_title"])
                        desc = row["malayalam_description"] or ""

                    st.caption(f"🗓️ {row['date']} | 🏷️ {row['tag']}")

                    # --- Safe Image Rendering ---
                    if row["image_data"]:
                        img_bytes = decode_image(row["image_data"])
                        if img_bytes:
                            st.image(img_bytes, use_container_width=True)
                        else:
                            st.warning(f"⚠️ Could not display image for ID {row['id']}")

                    # Description preview
                    desc_words = desc.split()
                    if len(desc_words) > 100:
                        preview_text = " ".join(desc_words[:100]) + "..."
                        st.write(preview_text)
                        with st.expander("Read more"):
                            st.write(desc)
                    else:
                        st.write(desc)

                    st.markdown("---")
