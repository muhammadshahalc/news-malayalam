import streamlit as st
import mysql.connector
import base64
import pandas as pd
from PIL import Image
import io
import time

# ---------------------------
# Configuration
# ---------------------------
st.set_page_config(
    page_title="Medical News",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------
# MySQL Connection Function with error handling
# ---------------------------
def get_connection():
    try:
        conn = mysql.connector.connect(
            host=st.secrets["DB_HOST"],
            port=st.secrets["DB_PORT"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASS"],
            database=st.secrets["DB_NAME"],
            ssl_ca="ssl/ca.pem",
            connection_timeout=5,
            pool_size=5
        )
        return conn
    except mysql.connector.Error as err:
        st.error(f"Database connection error: {err}")
        return None

# ---------------------------
# Fetch Data from DB with retry logic
# ---------------------------
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_news():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_connection()
            if conn is None:
                return pd.DataFrame()
                
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
            
        except mysql.connector.Error as err:
            if attempt == max_retries - 1:
                st.error(f"Failed to fetch news after {max_retries} attempts: {err}")
                return pd.DataFrame()
            time.sleep(1)  # Wait before retrying

# ---------------------------
# Fetch Unique Tags
# ---------------------------
@st.cache_data(ttl=600)  # Cache for 10 minutes
def fetch_unique_tags():
    try:
        conn = get_connection()
        if conn is None:
            return []
            
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT tag FROM news_articles_four WHERE tag IS NOT NULL")
        tags = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return sorted(tags)
    except mysql.connector.Error as err:
        st.error(f"Error fetching tags: {err}")
        return []

# ---------------------------
# Decode Base64 → PIL Image with better error handling
# ---------------------------
def decode_image(base64_str):
    try:
        if not base64_str or pd.isna(base64_str):
            return None
        img_bytes = base64.b64decode(base64_str)
        img = Image.open(io.BytesIO(img_bytes))
        return img
    except Exception as e:
        st.error(f"Error decoding image: {e}")
        return None

# ---------------------------
# Safe text display function
# ---------------------------
def safe_display_text(text, default="No content available"):
    if pd.isna(text) or not text:
        return default
    return text

# ---------------------------
# Language Selection Popup
# ---------------------------
if "language" not in st.session_state:
    st.title("🌐 Select Language")
    st.write("Please select your preferred language to continue:")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("English 🇬🇧", use_container_width=True):
            st.session_state.language = "english"
            st.rerun()
    with col2:
        if st.button("മലയാളം 🇮🇳", use_container_width=True):
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

# Add a loading spinner while fetching data
with st.spinner("Loading news..."):
    df = fetch_news()
    unique_tags = fetch_unique_tags()

# Check if data was loaded successfully
if df.empty:
    st.error("Failed to load news data. Please try again later.")
    st.stop()

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
    st.sidebar.info(f"Showing {len(filtered_df)} of {len(df)} articles")
    
    rows = filtered_df.to_dict(orient='records')
    for i in range(0, len(rows), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j < len(rows):
                row = rows[i + j]
                with col:
                    # Create a container for each news item
                    with st.container():
                        if st.session_state.language == "english":
                            title = safe_display_text(row["cleaned_title"], "No title available")
                            st.subheader(title)
                            desc = safe_display_text(row["cleaned_description"])
                        else:
                            title = safe_display_text(row["malayalam_title"], "തലക്കെട്ട് ലഭ്യമല്ല")
                            st.subheader(title)
                            desc = safe_display_text(row["malayalam_description"])

                        # Display date and tag
                        date_str = safe_display_text(row.get("date", ""), "Date not available")
                        tag_str = safe_display_text(row.get("tag", ""), "No tag")
                        st.caption(f"🗓️ {date_str} | 🏷️ {tag_str}")

                        # Image rendering
                        if row.get("image_data"):
                            img = decode_image(row["image_data"])
                            if img:
                                st.image(img, use_container_width=True, caption=title)
                            else:
                                st.warning("Image not available")
                        else:
                            st.info("No image available for this article")

                        # Description preview
                        if desc:
                            desc_words = desc.split()
                            if len(desc_words) > 100:
                                preview_text = " ".join(desc_words[:100]) + "..."
                                st.write(preview_text)
                                with st.expander("Read more"):
                                    st.write(desc)
                            else:
                                st.write(desc)
                        else:
                            st.info("No description available")

                        st.markdown("---")