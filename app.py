import streamlit as st
import datetime, math
import pandas as pd
from google import genai
from PIL import Image

st.set_page_config(page_title="Step App", layout="wide", page_icon="🏆")
st.title("🏃‍♂️ นับก้าว")

GEMINI_API_KEY = st.sidebar.text_input("🔑 Gemini API Key:", type="password")
SHEET_URL = st.sidebar.text_input("🔗 ลิงก์ Google Sheets:", type="password")
PLAYERS = ["A", "PAR", "TATA", "NADA"]

def load_data(url):
    try:
        csv_url = url.split('/edit')[0] + '/gviz/tq?tqx=out:csv'
        df = pd.read_csv(csv_url)
        df['วันที่'] = pd.to_datetime(df['วันที่']).dt.date
        return df
    except:
        return pd.DataFrame(columns=["วันที่", "เดือน", "ชื่อผู้แข่งขัน", "เวลาที่ส่ง", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"])

df_db = load_data(SHEET_URL) if SHEET_URL else pd.DataFrame(columns=["วันที่", "เดือน", "ชื่อผู้แข่งขัน", "เวลาที่ส่ง", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"])

st.header("📸 อัปโหลดรูปหลักฐานก้าวเดิน")
selected_player = st.selectbox("👤 เลือกชื่อของคุณ:", PLAYERS)
now = datetime.datetime.now()
current_month_str = now.strftime("%Y-%m")
current_date_obj = now.date()

uploaded_file = st.file_uploader("📷 เลือกรูปภาพหน้าจอนับก้าว:", type=["png", "jpg", "jpeg"])

if st.button("🚀 ส่งข้อมูลและคำนวณผล"):
    if uploaded_file is None:
        st.error("❌ กรุณาแนบรูปภาพก่อนส่ง")
    elif not GEMINI_API_KEY or not SHEET_URL:
        st.error("❌ กรุณากรอก Key และ ลิงก์ Google Sheets ที่แถบด้านซ้าย")
    else:
        with st.spinner("🤖 AI กำลังอ่านรูปภาพ..."):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                image = Image.open(uploaded_file)
                response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, "Extract total step count number. Return ONLY the raw number value."])
                ai_steps = int(''.join(filter(str.isdigit, response.text.strip())))
                
                upload_time = now.time()
                penalty_steps = 0
                if upload_time > datetime.time(20, 2, 0):
                    dt_u = datetime.datetime.combine(datetime.date.today(), upload_time)
                    dt_d = datetime.datetime.combine(datetime.date.today(), datetime.time(20, 2, 0))
                    penalty_steps = math.ceil((dt_u - dt_d).total_seconds() / 60) * 50
                
                st.success(f"🎉 สำเร็จ! วันนี้ {selected_player} เดินไป {ai_steps:,} ก้าว (หักส่งช้า {penalty_steps:,} ก้าว)")
            except Exception as e:
                st.error(f"❌ ระบบ AI ขัดข้อง: {e}")

st.markdown("---")
st.header(f"📊 สรุปสถิติคะแนนประจำเดือน ({current_month_str})")
summary_metrics = []
for p in PLAYERS:
    summary_metrics.append({"ชื่อผู้เข้าแข่ง": p, "ก้าวรวมทั้งหมด (เดือนนี้)": "0", "คะแนนรวมสะสม (เดือนนี้)": "0 แต้ม", "เฉลี่ยก้าวเดินต่อวัน": "0 ก้าว/วัน"})
st.table(pd.DataFrame(summary_metrics))
