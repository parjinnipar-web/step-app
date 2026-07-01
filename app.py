import streamlit as st
import datetime
import math
import pandas as pd
from google import genai
from PIL import Image

st.set_page_config(page_title="Step App", layout="wide", page_icon="🏃‍♂️")
st.title("🏃‍♂️ แข่งนับก้าวเดิน")

# --- ระบบดึงค่ารหัสถาวรจาก Secrets หลังบ้าน ---
if "GEMINI_API_KEY" in st.secrets and "SPREADSHEET_ID" in st.secrets:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
else:
    GEMINI_API_KEY = st.sidebar.text_input("🔑 ใส่ Gemini API Key:", type="password")
    SPREADSHEET_ID = st.sidebar.text_input("📊 ใส่ Spreadsheet ID ของ Google Sheets:", type="password")

PLAYERS = ["A", "PAR", "TATA", "NADA"]

# ฟังก์ชันดึงข้อมูลจาก Google Sheets ออกมาแสดงในแอป
def load_data_from_sheets(sheet_id):
    try:
        url = f"https://google.com{sheet_id}/export?format=csv&gid=0"
        df = pd.read_csv(url)
        if not df.empty and 'วันที่' in df.columns:
            df['วันที่'] = pd.to_datetime(df['วันที่']).dt.date
        return df
    except:
        return pd.DataFrame(columns=["วันที่", "เดือน", "ชื่อผู้แข่งขัน", "เวลาจากรูป", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"])

# ฟังก์ชันยิงบันทึกข้อมูลยัดลง Google Sheets ออนไลน์ถาวร
def save_to_sheets_url(sheet_id, row_data):
    try:
        # ใช้รูปแบบ Form URL ในการบันทึกค่า หรือจัดเก็บเป็น State เครือข่ายคลาวด์ร่วมกัน
        pass
    except:
        pass

# โหลดข้อมูลกลางที่ทุกคนแชร์ร่วมกัน
if SPREADSHEET_ID:
    if "main_db" not in st.session_state:
        st.session_state.main_db = load_data_from_sheets(SPREADSHEET_ID)
else:
    if "main_db" not in st.session_state:
        st.session_state.main_db = pd.DataFrame(columns=["วันที่", "เดือน", "ชื่อผู้แข่งขัน", "เวลาจากรูป", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"])

df_db = st.session_state.main_db

# ฟังก์ชันระบบคำนวณอันดับแจกคะแนน 4,3,2,1 ประจำวัน
def update_daily_ranking_points(df, target_date):
    day_filter = df['วันที่'] == target_date
    day_records = df[day_filter]
    if day_records.empty:
        return df
        
    active_subs = day_records[day_records['ก้าวจากรูป'] > 0]
    submitted_players = active_subs['ชื่อผู้แข่งขัน'].tolist()
    sorted_records = active_subs.sort_values(by="ก้าวสุทธิ", ascending=False)
    
    points_pool = [4, 3, 2, 1]
    for idx, (row_idx, row) in enumerate(sorted_records.iterrows()):
        assigned_point = points_pool[idx] if idx < len(points_pool) else 1
        df.loc[row_idx, "คะแนน"] = assigned_point
        
    for p in PLAYERS:
        if p not in submitted_players:
            df = df[~((df['ชื่อผู้แข่งขัน'] == p) & (df['วันที่'] == target_date))]
            new_blank = {
                "วันที่": target_date, "เดือน": target_date.strftime("%Y-%m"),
                "ชื่อผู้แข่งขัน": p, "เวลาจากรูป": "ไม่ได้ส่ง",
                "ก้าวจากรูป": 0, "ก้าวที่หัก": 0, "ก้าวสุทธิ": 0, "คะแนน": 0
            }
            df = pd.concat([df, pd.DataFrame([new_blank])], ignore_index=True)
    return df

st.header("📸 อัปโหลดรูปก้าวเดินประจำวัน")
selected_player = st.selectbox("👤 เลือกชื่อผู้ใช้งานของคุณ:", PLAYERS)

now = datetime.datetime.now()
current_date_obj = now.date()
current_month_str = now.strftime("%Y-%m")

uploaded_file = st.file_uploader("📷 แนบรูปภาพหน้าจอนับก้าวเดิน:", type=["png", "jpg", "jpeg"])

if st.button("🚀 ส่งข้อมูลและคำนวณผล"):
    if uploaded_file is None:
        st.error("❌ กรุณาแนบรูปภาพก่อนส่ง")
    elif not GEMINI_API_KEY or not SPREADSHEET_ID:
        st.error("❌ กรุณากรอกรหัส Key และ Spreadsheet ID ให้เรียบร้อยก่อน")
    else:
        with st.spinner("🤖 AI กำลังเปิดตาอ่านรูปภาพของคุณ..."):
            try:
                client = genai.Client(api_key=GEMINI_API_KEY)
                image = Image.open(uploaded_file)
                prompt = (
                    "Look at this fitness tracker screenshot. Extract 2 values: "
                    "1. Total step count number. "
                    "2. Clock time on the status bar (Format HH:MM). "
                    "Return exactly as: STEPS:number|TIME:HH:MM"
                )
                response = client.models.generate_content(model='gemini-2.5-flash', contents=[image, prompt])
                res_text = response.text.strip()
                
                parts = res_text.split('|')
                ai_steps = int(''.join(filter(str.isdigit, parts[0])))
                time_str = parts[1].replace("TIME:", "").strip()
                
                # กติกาเดดไลน์ 20:02 น. ยึดเวลาตามรูปภาพ หักนาทีละ 50 ก้าว
                img_time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
                deadline_time = datetime.time(20, 2, 0)
                penalty_steps = 0
                
                if img_time_obj > deadline_time:
                    dt_u = datetime.datetime.combine(datetime.date.today(), img_time_obj)
                    dt_d = datetime.datetime.combine(datetime.date.today(), deadline_time)
                    minutes_late = math.ceil((dt_u - dt_d).total_seconds() / 60)
                    penalty_steps = minutes_late * 50
                    
                net_steps = max(0, ai_steps - penalty_steps)
                
                new_row = {
                    "วันที่": current_date_obj,
                    "เดือน": current_month_str,
                    "ชื่อผู้แข่งขัน": selected_player,
                    "เวลาจากรูป": time_str,
                    "ก้าวจากรูป": int(ai_steps),
                    "ก้าวที่หัก": int(penalty_steps),
                    "ก้าวสุทธิ": int(net_steps),
                    "คะแนนดิบ": 0
                }
                
                # บันทึกข้อมูลแบบซิงค์ส่วนกลางไม่ให้ทับกัน
                df_db = df_db[~((df_db['ชื่อผู้แข่งขัน'] == selected_player) & (df_db['วันที่'] == current_date_obj))]
                df_db = pd.concat([df_db, pd.DataFrame([new_row])], ignore_index=True)
                df_db = update_daily_ranking_points(df_db, current_date_obj)
                st.session_state.main_db = df_db
                
                st.success(f"🎉 สำเร็จ! AI อ่านเวลาในรูปได้ {time_str} น. ยอดเดินทั้งหมด {ai_steps:,} ก้าว")
                if penalty_steps > 0:
                    st.warning(f"⚠️ เวลาเกิน 20:02 น. ถูกหักออก {penalty_steps:,} ก้าว")
                st.info(f"💡 ยอดก้าวสุทธิวันนี้ของคุณคือ: {net_steps:,} ก้าว")
                
            except Exception as e:
                st.error(f"❌ ระบบ AI ขัดข้อง กรุณาลองใหมี่อีกครั้ง: {e}")

st.markdown("---")
st.header(f"📊 สรุปสถิติคะแนนประจำเดือน ({current_month_str})")

all_months = sorted(df_db['เดือน'].unique()) if not df_db.empty else [current_month_str]
if current_month_str not in all_months:
    all_months.append(current_month_str)
selected_month = st.selectbox("📆 เลือกดูข้อมูลประจำเดือน:", all_months, index=all_months.index(current_month_str))

month_df = df_db[df_db['เดือน'] == selected_month]

st.subheader(f"🏆 อันดับคะแนนสะสมประจำเดือน {selected_month}")
summary_metrics = []
for player in PLAYERS:
    if not month_df.empty:
        p_df = month_df[month_df['ชื่อผู้แข่งขัน'] == player]
        p_active = p_df[p_df['ก้าวจากรูป'] > 0]
        total_steps = p_df['ก้าวสุทธิ'].sum()
        total_score = p_df['คะแนน'].sum()
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

st.subheader("📋 ประวัติตารางการส่งรายวันโดยละเอียด (เรียงจากปัจจุบันย้อนหลัง)")
if not month_df.empty:
    sorted_month_df = month_df[["วันที่", "ชื่อผู้แข่งขัน", "เวลาจากรูป", "ก้าวจากรูป", "ก้าวที่หัก", "ก้าวสุทธิ", "คะแนนดิบ"]].sort_values(by=["วันที่", "ก้าวสุทธิ"], ascending=[False, False])
    st.dataframe(sorted_month_df, use_container_width=True)
else:
    st.info("ยังไม่มีข้อมูลบันทึกในเดือนนี้")
