import streamlit as st
import datetime
import math
import pandas as pd
import os
from google import genai
from PIL import Image

st.set_page_config(page_title="Step App", layout="wide", page_icon="🏃‍♂️")
st.title("🏃‍♂️ แอปแข่งนับก้าว")

# --- 🔐 ดึงรหัส Secrets หลังบ้าน ---
if "GEMINI_API_KEY" in st.secrets and "SHEET_URL" in st.secrets:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SHEET_URL = st.secrets["SHEET_URL"]
else:
    GEMINI_API_KEY = st.sidebar.text_input("🔑 ใส่ Gemini API Key:", type="password")
    SHEET_URL = st.sidebar.text_input("🔗 ใส่ลิงก์ Google Sheets:", type="password")

PLAYERS = ["A", "PAR", "TATA", "NADA"]
DATA_FILE = "global_step_database.csv"

# --- 📁 ฟังก์ชันจัดการฐานข้อมูลแบบถาวรออนไลน์ ---
def load_global_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        df['วันที่'] = pd.to_datetime(df['วันที่']).dt.date
        return df
    return pd.DataFrame(columns=["วันที่", "เดือน", "ชื่อผู้แข่งขัน", "เวลาจากรูป", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"])

def save_global_data(df):
    df.to_csv(DATA_FILE, index=False)

# โหลดฐานข้อมูลหลัก
if "db" not in st.session_state:
    st.session_state.db = load_global_data()

# --- 📊 ฟังก์ชันแจกคะแนนแต้มดิบประจำวัน (4,3,2,1 หรือ 0 สำหรับคนเบี้ยว) ---
def calculate_daily_points(df, target_date):
    day_filter = df['วันที่'] == target_date
    day_records = df[day_filter]
    if day_records.empty:
        return df
        
    active_subs = day_records[day_records['ก้าวจากรูป'] > 0]
    submitted_players = active_subs['ชื่อผู้แข่งขัน'].tolist()
    
    # จัดอันดับตามก้าวสุทธิจากมากไปน้อย
    sorted_records = active_subs.sort_values(by="ก้าวสุทธิ", ascending=False)
    
    points_pool = [4, 3, 2, 1]
    for idx, (row_idx, row) in enumerate(sorted_records.iterrows()):
        assigned_point = points_pool[idx] if idx < len(points_pool) else 1
        df.loc[row_idx, "คะแนนดิบ"] = assigned_point
        
    # คนที่ไม่ส่งรูปภายในวันนั้น (กติกาได้ 0 คะแนนอัตโนมัติ)
    for p in PLAYERS:
        if p not in submitted_players:
            df = df[~((df['ชื่อผู้แข่งขัน'] == p) & (df['วันที่'] == target_date))]
            new_blank = {
                "วันที่": target_date, "เดือน": target_date.strftime("%Y-%m"),
                "ชื่อผู้แข่งขัน": p, "เวลาจากรูป": "ไม่ได้ส่ง",
                "ก้าวจากรูป": 0, "ก้าวที่หัก": 0, "ก้าวสุทธิ": 0, "คะแนนดิบ": 0
            }
            df = pd.concat([df, pd.DataFrame([new_blank])], ignore_index=True)
    return df

# --- 📅 ระบบจัดการเวลาประเทศไทย ---
tz_delta = datetime.timedelta(hours=7)
now_thailand = datetime.datetime.utcnow() + tz_delta
today_date = now_thailand.date()
current_month_str = now_thailand.strftime("%Y-%m")

# --- 📥 เมนูฟอร์มหลักสำหรับการอัปโหลดหลักฐาน ---
st.header("📤 ส่งผลก้าวเดินประจำวัน (เดดไลน์ 20:02 น. บนหน้าปัดรูปถ่าย)")
st.warning("⚠️ เงื่อนไขกติกา: ส่งก่อน 24:00 น. เท่านั้น")

selected_player = st.selectbox("👤 เลือกชื่อของคุณ:", PLAYERS)
uploaded_file = st.file_uploader("📷 แนบรูปภาพแคปหน้าจอ (ระบบจะสแกนเวลาและจำนวนก้าวจากในรูปภาพ):", type=["png", "jpg", "jpeg"])

if st.button("🚀 ส่งหลักฐานประมวลผลระบบ AI"):
    # เช็กการส่งซ้ำ
    df_current = st.session_state.db
    already_sent = df_current[(df_current['ชื่อผู้แข่งขัน'] == selected_player) & (df_current['วันที่'] == today_date) & (df_current['ก้าวจากรูป'] > 0)]
    
    if not already_sent.empty:
        st.error(f"❌ {selected_player} ได้อัปโหลดรูปประจำวันที่ {today_date} เรียบร้อยแล้ว (ส่งได้วันละ 1 ครั้ง)")
    elif uploaded_file is None:
        st.error("❌ กรุณาอัปโหลดรูปภาพก้าวเดินก่อนกดส่ง")
    elif not GEMINI_API_KEY:
        st.error("❌ ขาดรหัส Gemini API Key ในระบบ")
    else:
        with st.spinner("🤖 AI กำลังถอดรหัสอ่านเวลาและจำนวนก้าวจากภาพหน้าปัดนาฬิกาของคุณ..."):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                image = Image.open(uploaded_file)
                
                # --- สั่งให้ AI อ่านข้อมูล 2 อย่างพร้อมกันจากรูปภาพตามกติกาใหม่ ---
                prompt = (
                    "Look at this screenshot of a fitness tracker. Extract 2 values: "
                    "1. The total step count number. "
                    "2. The clock time displayed on the screen/status bar (Format HH:MM). "
                    "Return the result exactly in this format: STEPS:number|TIME:HH:MM"
                )
                response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
                res_text = response.text.strip()
                
                # แยกชิ้นส่วนข้อมูลที่ AI อ่านได้
                parts = res_text.split('|')
                ai_steps = int(''.join(filter(str.isdigit, parts[0])))
                time_str = parts[1].replace("TIME:", "").strip()
                
                # แปลงเวลาจากรูปไปคำนวณเดดไลน์
                img_time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
                deadline_time = datetime.time(20, 2, 0)
                
                penalty_steps = 0
                if img_time_obj > deadline_time:
                    dt_u = datetime.datetime.combine(datetime.date.today(), img_time_obj)
                    dt_d = datetime.datetime.combine(datetime.date.today(), deadline_time)
                    minutes_late = math.ceil((dt_u - dt_d).total_seconds() / 60)
                    penalty_steps = minutes_late * 50
                    
                net_steps = max(0, ai_steps - penalty_steps)
                
                # บันทึกข้อมูลลงฐานข้อมูล
                new_row = {
                    "วันที่": today_date,
                    "เดือน": current_month_str,
                    "ชื่อผู้แข่งขัน": selected_player,
                    "เวลาจากรูป": time_str,
                    "ก้าวจากรูป": ai_steps,
                    "ก้าวที่หัก": penalty_steps,
                    "ก้าวสุทธิ": net_steps,
                    "คะแนนดิบ": 0
                }
                
                df_updated = pd.concat([st.session_state.db, pd.DataFrame([new_row])], ignore_index=True)
                df_updated = df_updated[df_updated['วันที่'] != today_date]
                df_updated = pd.concat([df_updated, pd.DataFrame([new_row])], ignore_index=True)
                df_updated = calculate_daily_points(df_updated, today_date)
                
                st.session_state.db = df_updated
                save_global_data(df_updated)
                
                st.success(f"🎉 สำเร็จ! AI อ่านเวลาจากภาพได้เวลา {time_str} น. จำนวนก้าว {ai_steps:,} ก้าว")
                if penalty_steps > 0:
                    st.warning(f"⚠️ เวลาในรูปเกินเดดไลน์ 20:02 น. ถูกหักคะแนนออก {penalty_steps:,} ก้าว")
                st.info(f"💡 สรุปยอดก้าวสุทธิประจำวันนี้ของคุณคือ: {net_steps:,} ก้าว")
                
            except Exception as e:
                st.error(f"❌ ระบบ AI อ่านรูปขัดข้อง กรุณาลองอัปโหลดใหม่อีกครั้ง: {e}")

# --- 📆 ระบบเลือกดูคลังข้อมูลประวัติแยกเป็นรายเดือนตามกติกา ---
st.markdown("---")
st.header("📊 ตารางคะแนนและสถิติประวัติการแข่งขัน")

df_display = st.session_state.db
all_months = sorted(df_display['เดือน'].unique()) if not df_display.empty else [current_month_str]
if current_month_str not in all_months:
    all_months.append(current_month_str)
    
selected_month = st.selectbox("📆 เลือกเดือนที่ต้องการเปิดดูสถิติคลังคะแนน:", all_months, index=all_months.index(current_month_str))

month_df = df_display[df_display['เดือน'] == selected_month]

# แดชบอร์ดสรุปยอดรวมประจำเดือนของผู้เล่นทั้ง 4 คน
st.subheader(f"🏆 ทำเนียบอันดับคะแนนสะสมประจำเดือน {selected_month}")
summary_metrics = []
for player in PLAYERS:
    if not month_df.empty:
        p_df = month_df[month_df['ชื่อผู้แข่งขัน'] == player]
        p_active = p_df[p_df['ก้าวจากรูป'] > 0]
        
        total_steps = p_df['ก้าวสุทธิ'].sum()
        total_score = p_df['คะแนนดิบ'].sum()
        days_walked = len(p_active)
        avg_steps = total_steps / days_walked if days_walked > 0 else 0
    else:
        total_steps, total_score, avg_steps = 0, 0, 0
        
    summary_metrics.append({
        "ชื่อผู้เข้าแข่ง": player,
        "ก้าวรวมทั้งหมด (เดือนนี้)": f"{int(total_steps):,}",
        "คะแนนรวมสะสม (เดือนนี้)": f"{int(total_score)} แต้ม",
        "เฉลี่ยก้าวเดินต่อวัน": f"{int(avg_steps):,} ก้าว/วัน"
    })
st.table(pd.DataFrame(summary_metrics).sort_values(by="คะแนนรวมสะสม (เดือนนี้)", ascending=False))

# --- 📋 ประวัติตารางแบบเรียงไล่เป็นรายวันลงมาตามกติกาใหม่ ---
st.subheader("📋 บันทึกตารางคะแนนและผลหักรายวันโดยละเอียด (เรียงจากปัจจุบันย้อนหลัง)")
if not month_df.empty:
    # สั่งเรียงลำดับตารางให้แสดงไล่วันที่ลงมาอย่างเป็นระเบียบชัดเจน
    sorted_month_df = month_df[["วันที่", "ชื่อผู้แข่งขัน", "เวลาจากรูป", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"]].sort_values(by=["วันที่", "ก้าวสุทธิ"], ascending=[False, False])
    st.dataframe(sorted_month_df, use_container_width=True)
else:
    st.info("ยังไม่มีบันทึกข้อมูลของเดือนนี้ เริ่มส่งก้าวคนแรกเพื่อเริ่มตารางได้เลยครับ!")
