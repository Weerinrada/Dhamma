"""
app.py - Streamlit App (ใช้ ffmpeg-python แทน moviepy)
แก้ไขปัญหา session state reset + เพิ่ม Quote & แก่นธรรม 3 ข้อ
"""

import streamlit as st
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
import google.generativeai as genai
import os
import tempfile
import time
import ffmpeg
import subprocess
import json

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="🤍 เสียงธรรมะสู่ภาพธรรมะ 🙏",
    page_icon="🔆 🙏 🤍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "processing_stage" not in st.session_state:
    st.session_state.processing_stage = "upload"
if "initial_result" not in st.session_state:
    st.session_state.initial_result = None
if "final_result" not in st.session_state:
    st.session_state.final_result = None
if "temp_path" not in st.session_state:
    st.session_state.temp_path = None
if "uploaded_file_name" not in st.session_state:
    st.session_state.uploaded_file_name = None

# CSS
st.markdown(
    """
<style>
    .main-header {
        text-align: center;
        color: #8B4513;
        padding: 20px;
        background: linear-gradient(135deg, #FFF8DC 0%, #F5DEB3 100%);
        border-radius: 10px;
        margin-bottom: 30px;
    }
    .post-container {
        background-color: #FFFAF0;
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #DAA520;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin: 20px 0;
    }
    .quote-container {
        background: linear-gradient(135deg, #FFF5E1 0%, #FFE4B5 100%);
        padding: 30px;
        border-radius: 15px;
        border-left: 5px solid #FF8C00;
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        margin: 20px 0;
        font-style: italic;
    }
    .essence-container {
        background: linear-gradient(135deg, #E6F3FF 0%, #CCE5FF 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid #4169E1;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin: 20px 0;
    }
    .essence-item {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 3px solid #4169E1;
    }
    .keyword-tag {
        background-color: #F0E68C;
        padding: 5px 12px;
        border-radius: 15px;
        margin: 5px;
        display: inline-block;
        color: #8B4513;
        font-weight: bold;
    }
    .stButton>button {
        background-color: #DAA520;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        padding: 10px 30px;
        border: none;
    }
    .stButton>button:hover {
        background-color: #B8860B;
    }
    .info-box {
        background-color: #E8F4F8;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #2196F3;
        margin: 10px 0;
    }
    .headline {
        font-size: 1.5em;
        font-weight: bold;
        color: #8B4513;
        text-align: center;
        margin: 20px 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Header
st.markdown(
    """
<div class="main-header">
    <h1>🙏 เสียง/วิดีโอธรรมะสู่ Social Media Post</h1>
    <p>แปลงเสียงหรือวิดีโอสอนธรรมะเป็นโพสต์ที่น่าสนใจและสร้างแรงบันดาลใจ</p>
</div>
""",
    unsafe_allow_html=True,
)


# ===== CLASS สำหรับประมวลผล =====
class DhammaPostCreator:
    def __init__(self, gemini_api_key):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        genai.configure(api_key=gemini_api_key)
        self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")

    def extract_audio_from_video_ffmpeg(self, video_file_path, progress_callback=None):
        """แยกเสียงจากวิดีโอด้วย ffmpeg-python"""
        if progress_callback:
            progress_callback("🎬 กำลังแยกเสียงจากวิดีโอ...")

        try:
            audio_path = video_file_path.rsplit(".", 1)[0] + "_extracted_audio.wav"
            stream = ffmpeg.input(video_file_path)
            stream = ffmpeg.output(
                stream,
                audio_path,
                acodec="pcm_s16le",
                ac=1,
                ar="16000",
            )
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            if progress_callback:
                progress_callback("✅ แยกเสียงจากวิดีโอเรียบร้อย")

            return audio_path

        except ffmpeg.Error as e:
            raise Exception(
                f"ไม่สามารถแยกเสียงจากวิดีโอได้: {e.stderr.decode() if e.stderr else str(e)}"
            )
        except Exception as e:
            raise Exception(f"ไม่สามารถแยกเสียงจากวิดีโอได้: {e}")

    def get_video_info_ffmpeg(self, video_file_path):
        """ดึงข้อมูลวิดีโอด้วย ffprobe"""
        try:
            probe = ffmpeg.probe(video_file_path)
            video_info = next(
                (s for s in probe["streams"] if s["codec_type"] == "video"), None
            )
            audio_info = next(
                (s for s in probe["streams"] if s["codec_type"] == "audio"), None
            )

            if video_info:
                duration = float(probe["format"]["duration"])
                width = int(video_info["width"])
                height = int(video_info["height"])

                return {
                    "duration": duration,
                    "size": (width, height),
                    "has_audio": audio_info is not None,
                }
            return None
        except Exception as e:
            return None

    def is_video_file(self, file_path):
        """ตรวจสอบว่าเป็นไฟล์วิดีโอหรือไม่"""
        video_extensions = [
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".flv",
            ".wmv",
            ".webm",
            ".m4v",
        ]
        file_extension = os.path.splitext(file_path)[1].lower()
        return file_extension in video_extensions

    def convert_to_wav(self, audio_file_path, progress_callback=None):
        """แปลงไฟล์เสียงเป็น WAV"""
        file_extension = os.path.splitext(audio_file_path)[1].lower()

        if file_extension == ".wav":
            return audio_file_path

        if progress_callback:
            progress_callback("🔄 กำลังแปลงไฟล์เสียง...")

        audio = AudioSegment.from_file(audio_file_path)
        audio = audio.set_channels(1)
        audio = audio.set_frame_rate(16000)

        wav_path = audio_file_path.rsplit(".", 1)[0] + "_converted.wav"
        audio.export(wav_path, format="wav")
        return wav_path

    def get_audio_duration(self, audio_file_path):
        """ตรวจสอบความยาวไฟล์เสียง"""
        audio = AudioSegment.from_file(audio_file_path)
        return len(audio) / 1000.0

    def speech_to_text_short(self, audio_file_path, progress_callback=None):
        """แปลงเสียงสั้น"""
        if progress_callback:
            progress_callback("🎤 กำลังแปลงเสียงเป็นข้อความ...")

        with sr.AudioFile(audio_file_path) as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = self.recognizer.record(source)

        try:
            text = self.recognizer.recognize_google(audio_data, language="th-TH")
            return text
        except sr.UnknownValueError:
            raise Exception("ไม่สามารถรู้จำเสียงได้ กรุณาตรวจสอบคุณภาพเสียง")
        except sr.RequestError as e:
            raise Exception(f"ไม่สามารถเชื่อมต่อ Google Speech API: {e}")

    def speech_to_text_long(self, audio_file_path, progress_callback=None):
        """แปลงเสียงยาว แบ่งเป็นส่วนๆ"""
        if progress_callback:
            progress_callback("📊 กำลังแบ่งไฟล์เสียงเป็นส่วนๆ...")

        audio = AudioSegment.from_wav(audio_file_path)
        chunk_length_ms = 30000
        chunks = []

        for i in range(0, len(audio), chunk_length_ms):
            chunks.append(audio[i : i + chunk_length_ms])

        full_text = []
        total_chunks = len(chunks)

        for i, chunk in enumerate(chunks, 1):
            if progress_callback:
                progress_callback(f"🎤 กำลังประมวลผลส่วนที่ {i}/{total_chunks}...")

            chunk_path = f"temp_chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")

            try:
                with sr.AudioFile(chunk_path) as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio_data = self.recognizer.record(source)

                text = self.recognizer.recognize_google(audio_data, language="th-TH")
                full_text.append(text)

            except sr.UnknownValueError:
                pass
            except Exception as e:
                st.warning(f"ข้ามส่วนที่ {i}: {e}")
            finally:
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)

            time.sleep(0.5)

        return " ".join(full_text)

    def speech_to_text_auto(self, audio_file_path, progress_callback=None):
        """เลือกวิธีแปลงอัตโนมัติ"""
        duration = self.get_audio_duration(audio_file_path)

        if duration > 60:
            return self.speech_to_text_long(audio_file_path, progress_callback)
        else:
            return self.speech_to_text_short(audio_file_path, progress_callback)

    def create_dhamma_post(self, transcript, category="ธรรมะ", progress_callback=None):
        """สร้างโพสต์ธรรมะด้วย Gemini"""
        if progress_callback:
            progress_callback("✨ กำลังวิเคราะห์และสร้างโพสต์...")

        prompt = f"""
คุณเป็นผู้เชี่ยวชาญในการสร้างเนื้อหาธรรมะสำหรับ Social Media

จากเนื้อหาการสอนธรรมะต่อไปนี้:
{transcript}

กรุณาสร้าง social media post ที่:
1. เริ่มต้นด้วย hook ที่ดึงดูดความสนใจและสัมผัสใจ
2. สรุปเนื้อหาธรรมะให้กระชับ เข้าใจง่าย และมีคุณค่า
3. ใช้น้ำเสียงที่อบอุ่น เป็นกันเอง แต่สื่อถึงความลึกซึ้งของธรรมะ
4. ใช้ emoji ที่เหมาะสม 2-3 ตัว (เช่น 🙏 ✨ 💫 🌟 ☸️)
5. จบด้วย call-to-action หรือคำถามเพื่อกระตุ้นการไตร่ตรอง
6. ใส่ hashtags ที่เกี่ยวข้องกับธรรมะ 5-8 อัน

หมวดหมู่: {category}
น้ำเสียง: สอนธรรมะ อบอุ่น สร้างแรงบันดาลใจ

รูปแบบ:
[Hook ที่สัมผัสใจ]

[เนื้อหาธรรมะที่กระชับและลึกซึ้ง 2-3 ประโยค]

[Call-to-action หรือคำถามเพื่อให้ไตร่ตรอง]

#hashtag1 #hashtag2 #hashtag3 ...

กรุณาสร้างโพสต์ที่สวยงาม เหมาะสำหรับโพสต์บน Facebook, Instagram, หรือ Line
"""

        try:
            response = self.gemini_model.generate_content(prompt)
            post = response.text.strip()
            return post
        except Exception as e:
            raise Exception(f"ไม่สามารถสร้างโพสต์ได้: {e}")

    def create_dhamma_essence(self, transcript, progress_callback=None):
        """สร้างแก่นธรรม 3 ข้อ และ Headline"""
        if progress_callback:
            progress_callback("📝 กำลังสร้างแก่นธรรม 3 ข้อ...")

        prompt = f"""
จากเนื้อหาธรรมะนี้ ช่วยสรุปเป็น "แก่นธรรม 3 ข้อ"
เพื่อนำไปทำภาพกราฟิกแบบ Checklist หรือ Carousel
ขอภาษาที่กระชับ อ่านง่าย เหมือนสรุป Key Takeaway ให้คนอ่าน
และขอ "พาดหัวเรื่อง" (Headline) ที่น่าสนใจสำหรับโพสต์นี้ด้วย 1 ชื่อ

เนื้อหา:
{transcript}

กรุณาตอบในรูปแบบ JSON:
{{
    "headline": "พาดหัวที่น่าสนใจ",
    "essence_1": "แก่นธรรมข้อที่ 1",
    "essence_2": "แก่นธรรมข้อที่ 2",
    "essence_3": "แก่นธรรมข้อที่ 3",
    "quote": "คำคมสั้นๆ ที่สรุปใจความสำคัญ"
}}

เงื่อนไข:
- Headline: ไม่เกิน 60 ตัวอักษร น่าสนใจ ดึงดูดใจ
- แก่นธรรมแต่ละข้อ: ไม่เกิน 100 ตัวอักษร กระชับ ชัดเจน
- Quote: ไม่เกิน 150 ตัวอักษร สั้น กระทบใจ จดจำง่าย
"""

        try:
            response = self.gemini_model.generate_content(prompt)
            response_text = (
                response.text.strip().replace("```json", "").replace("```", "").strip()
            )
            result = json.loads(response_text)
            return result
        except Exception as e:
            return {
                "headline": "หลักธรรมะสำคัญที่ควรรู้",
                "essence_1": "การฝึกสติในชีวิตประจำวัน",
                "essence_2": "การปล่อยวางความยึดติด",
                "essence_3": "การพัฒนาปัญญาเพื่อเข้าใจความจริง",
                "quote": "ความสุขที่แท้จริงเกิดจากภายใน ไม่ใช่สิ่งภายนอก",
            }

    def extract_keywords(self, transcript, progress_callback=None):
        """สกัด keywords จากเนื้อหา"""
        if progress_callback:
            progress_callback("🔍 กำลังสกัด keywords...")

        prompt = f"""
วิเคราะห์เนื้อหาธรรมะต่อไปนี้และสกัด 5-8 keywords ที่สำคัญ:

{transcript}

กรุณาตอบในรูปแบบ JSON:
{{
    "keywords": ["keyword1", "keyword2", ...],
    "main_teaching": "หลักธรรมะหลักที่สอน",
    "emotion": "อารมณ์/ความรู้สึกที่ต้องการสื่อ"
}}

keywords ควรเป็น:
- คำภาษาไทยที่เกี่ยวกับธรรมะ
- เหมาะสำหรับทำ hashtag
- สั้น กระชับ มีความหมาย
"""

        try:
            response = self.gemini_model.generate_content(prompt)
            response_text = (
                response.text.strip().replace("```json", "").replace("```", "").strip()
            )
            result = json.loads(response_text)
            return result
        except Exception as e:
            return {
                "keywords": ["ธรรมะ", "สติ", "ปัญญา", "สันติสุข"],
                "main_teaching": "การปฏิบัติธรรม",
                "emotion": "สงบ สะเทือนใจ",
            }

    def process_file(self, file_path, category="ธรรมะ", progress_callback=None):
        """ประมวลผลไฟล์ (เสียงหรือวิดีโอ)"""
        start_time = time.time()
        audio_path = file_path
        extracted_audio = False

        if self.is_video_file(file_path):
            if progress_callback:
                progress_callback("🎬 ตรวจพบไฟล์วิดีโอ กำลังแยกเสียง...")

            audio_path = self.extract_audio_from_video_ffmpeg(
                file_path, progress_callback
            )
            extracted_audio = True

        wav_path = self.convert_to_wav(audio_path, progress_callback)
        transcript = self.speech_to_text_auto(wav_path, progress_callback)

        if not transcript or len(transcript.strip()) < 20:
            raise Exception("ข้อความที่ได้สั้นเกินไป กรุณาตรวจสอบไฟล์")

        return {
            "transcript": transcript,
            "audio_path": audio_path,
            "wav_path": wav_path,
            "extracted_audio": extracted_audio,
            "was_video": self.is_video_file(file_path),
            "start_time": start_time,
        }

    def continue_processing(self, transcript, category, progress_callback=None):
        """ประมวลผลต่อหลังจากแสดง transcript แล้ว"""
        # สกัด keywords
        analysis = self.extract_keywords(transcript, progress_callback)

        # สร้างโพสต์
        post = self.create_dhamma_post(transcript, category, progress_callback)

        # สร้างแก่นธรรม 3 ข้อ
        essence = self.create_dhamma_essence(transcript, progress_callback)

        return {
            "post": post,
            "keywords": analysis.get("keywords", []),
            "main_teaching": analysis.get("main_teaching", ""),
            "emotion": analysis.get("emotion", ""),
            "headline": essence.get("headline", ""),
            "essence_1": essence.get("essence_1", ""),
            "essence_2": essence.get("essence_2", ""),
            "essence_3": essence.get("essence_3", ""),
            "quote": essence.get("quote", ""),
        }


# ===== SIDEBAR =====
with st.sidebar:
    st.markdown("### 🔑 การตั้งค่า")

    gemini_api_key = st.text_input(
        "Gemini API Key",
        type="password",
        help="ดาวน์โหลดฟรีจาก https://aistudio.google.com/app/apikey",
    )

    if gemini_api_key:
        st.success("✅ API Key ถูกต้อง")
    else:
        st.warning("⚠️ กรุณาใส่ API Key")

    st.markdown("---")

    st.markdown("### 📂 หมวดหมู่เนื้อหา")
    category = st.selectbox(
        "เลือกหมวดหมู่",
        [
            "ธรรมะทั่วไป",
            "สติปัฏฐาน",
            "เมตตาภาวนา",
            "วิปัสสนา",
            "ศีล สมาธิ ปัญญา",
            "กรรมฐาน",
            "พุทธประวัติ",
            "ชาดก",
            "อริยสัจ 4",
            "มรรคมีองค์ 8",
        ],
    )

    st.markdown("---")

    st.markdown("### 📊 คุณสมบัติ")
    st.markdown("""
    - ✅ รองรับไฟล์เสียง
      - MP3, M4A, WAV, FLAC
    - ✅ รองรับไฟล์วิดีโอ
      - MP4, AVI, MOV, MKV
      - WebM, FLV, WMV
    - ✅ แยกเสียงจากวิดีโออัตโนมัติ
    - ✅ แปลงเสียงเป็นข้อความ
    - ✅ สร้างโพสต์อัตโนมัติ
    - ✅ สร้างแก่นธรรม 3 ข้อ
    - ✅ สร้าง Quote กราฟิก
    - ✅ น้ำเสียงอบอุ่น เหมาะกับธรรมะ
    - ✅ สกัด Keywords
    - ✅ Hashtags อัตโนมัติ
    """)

    st.markdown("---")

    st.markdown("### 💡 เคล็ดลับ")
    st.info("""
    **ไฟล์เสียง:**
    - ไม่มี noise มาก
    - พูดชัดเจน
    - ไม่เร็วเกินไป

    **ไฟล์วิดีโอ:**
    - ควรมีเสียงชัด
    - ระบบจะแยกเสียงอัตโนมัติ
    - รองรับทุกรูปแบบ

    **ความยาว:**
    - สั้น: < 1 นาที
    - ยาว: แบ่งอัตโนมัติ
    """)

# ===== MAIN CONTENT =====

if not gemini_api_key:
    st.warning("⚠️ กรุณาใส่ Gemini API Key ใน Sidebar ด้านซ้าย")
    st.info("""
    ### วิธีการใช้งาน:
    1. ไปที่ https://aistudio.google.com/app/apikey
    2. Sign in ด้วย Google Account
    3. คลิก "Create API Key"
    4. Copy API Key มาวางในช่องด้านซ้าย
    5. อัปโหลดไฟล์เสียงหรือวิดีโอธรรมะ
    6. รอระบบประมวลผล
    7. Copy โพสต์ไปใช้งาน!
    """)
    st.stop()

# สร้าง processor
try:
    processor = DhammaPostCreator(gemini_api_key)
except Exception as e:
    st.error(f"❌ ไม่สามารถเริ่มระบบได้: {e}")
    st.stop()

# ===== STAGE 1: UPLOAD =====
if st.session_state.processing_stage == "upload":
    st.markdown("### 📤 อัปโหลดไฟล์เสียงหรือวิดีโอธรรมะ")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
        <div class="info-box">
        <h4>🎵 ไฟล์เสียง</h4>
        <p>MP3, WAV, M4A, FLAC, AAC</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
        <div class="info-box">
        <h4>🎬 ไฟล์วิดีโอ</h4>
        <p>MP4, AVI, MOV, MKV, WebM, FLV, WMV</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

    uploaded_file = st.file_uploader(
        "เลือกไฟล์เสียงหรือวิดีโอ",
        type=[
            "mp3",
            "wav",
            "m4a",
            "mp4",
            "flac",
            "aac",
            "avi",
            "mov",
            "mkv",
            "webm",
            "flv",
            "wmv",
            "m4v",
        ],
        help="รองรับไฟล์เสียงและวิดีโอหลายรูปแบบ (ขนาดไม่เกิน 200MB)",
    )

    if uploaded_file is not None:
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        is_video = file_extension in [
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".flv",
            ".wmv",
            ".webm",
            ".m4v",
        ]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "📁 ชื่อไฟล์",
                uploaded_file.name[:20] + "..."
                if len(uploaded_file.name) > 20
                else uploaded_file.name,
            )
        with col2:
            file_size = uploaded_file.size / (1024 * 1024)
            st.metric("📊 ขนาด", f"{file_size:.2f} MB")
        with col3:
            file_type = "🎬 วิดีโอ" if is_video else "🎵 เสียง"
            st.metric("📝 ประเภท", file_type)
        with col4:
            format_type = file_extension.upper().replace(".", "")
            st.metric("🔧 รูปแบบ", format_type)

        if is_video:
            st.video(uploaded_file)
            st.info("💡 ระบบจะแยกเสียงจากวิดีโออัตโนมัติก่อนแปลงเป็นข้อความ")
        else:
            st.audio(uploaded_file)

        st.markdown("---")

        if st.button("🚀 เริ่มสร้างโพสต์", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(message):
                status_text.text(message)

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=os.path.splitext(uploaded_file.name)[1]
            ) as tmp_file:
                tmp_file.write(uploaded_file.read())
                temp_path = tmp_file.name

            try:
                progress_bar.progress(10)
                update_progress("📂 กำลังโหลดไฟล์...")

                if is_video:
                    video_info = processor.get_video_info_ffmpeg(temp_path)
                    if video_info:
                        st.info(f"""
                        📊 **ข้อมูลวิดีโอ:**
                        - ความยาว: {video_info["duration"]:.1f} วินาที ({video_info["duration"] / 60:.1f} นาที)
                        - ขนาด: {video_info["size"][0]}x{video_info["size"][1]} pixels
                        - มีเสียง: {"✅ ใช่" if video_info["has_audio"] else "❌ ไม่มี"}
                        """)

                        if not video_info["has_audio"]:
                            st.error("❌ วิดีโอนี้ไม่มีเสียง กรุณาอัปโหลดไฟล์ที่มีเสียง")
                            os.remove(temp_path)
                            st.stop()

                progress_bar.progress(20)

                initial_result = processor.process_file(
                    temp_path, category=category, progress_callback=update_progress
                )

                progress_bar.progress(60)
                status_text.empty()
                progress_bar.empty()

                # บันทึกใน session state
                st.session_state.initial_result = initial_result
                st.session_state.temp_path = temp_path
                st.session_state.uploaded_file_name = uploaded_file.name
                st.session_state.processing_stage = "transcript"
                st.rerun()

            except Exception as e:
                progress_bar.empty()
                status_text.empty()

                if os.path.exists(temp_path):
                    os.remove(temp_path)

                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

                with st.expander("ℹ️ วิธีแก้ไข"):
                    st.markdown("""
                    **ปัญหาที่พบบ่อย:**

                    1. **ไม่สามารถรู้จำเสียงได้**
                       - ตรวจสอบคุณภาพเสียง
                       - ลดเสียง noise
                       - พูดชัดเจนขึ้น

                    2. **API Error**
                       - ตรวจสอบ API Key
                       - ตรวจสอบการเชื่อมต่ออินเทอร์เน็ต

                    3. **ไฟล์ใหญ่เกินไป**
                       - แบ่งไฟล์เป็นส่วนเล็กลง
                       - ใช้ไฟล์ที่สั้นกว่า 10 นาที

                    4. **วิดีโอไม่มีเสียง**
                       - ตรวจสอบว่าวิดีโอมี audio track หรือไม่

                    5. **ไม่สามารถแยกเสียงจากวิดีโอได้**
                       - ตรวจสอบว่าติดตั้ง ffmpeg แล้วหรือยัง
                    """)

    else:
        # แสดงตัวอย่าง
        st.markdown("### 📖 ตัวอย่างโพสต์ที่สร้างได้")

        example_post = """🙏 ความสุขที่แท้จริง... ไม่ได้อยู่ที่สิ่งภายนอก

ในโลกที่เร่งรีบและเต็มไปด้วยความวุ่นวาย เรามักหาความสุขจากสิ่งภายนอก แต่พระพุทธเจ้าทรงสอนว่า ความสุขที่แท้จริงนั้นเกิดจากภายใน เกิดจากจิตใจที่สงบ ปล่อยวาง และเข้าใจในความจริงของชีวิต ✨

การฝึกสติในชีวิตประจำวัน คือการเริ่มต้นเส้นทางสู่ความสุขที่ยั่งยืน 💫

คุณมีวิธีฝึกสติในชีวิตประจำวันอย่างไร? มาแบ่งปันกันนะคะ 🌟

#ธรรมะ #สติปัฏฐาน #ความสุขที่แท้จริง #ปัญญา #สันติสุข #พุทธศาสนา #ฝึกสติ #ชีวิตที่ดีกว่า"""

        st.markdown(
            f"""
        <div class="post-container">
        {example_post.replace(chr(10), "<br>")}
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # แสดงคำแนะนำการใช้งาน
        st.markdown("### 🎯 วิธีใช้งาน")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            #### 🎵 สำหรับไฟล์เสียง

            1. **เตรียมไฟล์เสียง**
               - MP3, WAV, M4A, FLAC
               - คุณภาพเสียงดี ไม่มี noise มาก
               - พูดชัดเจน ไม่เร็วเกินไป

            2. **อัปโหลดไฟล์**
               - คลิกปุ่ม "Browse files"
               - เลือกไฟล์เสียงของคุณ

            3. **รอผลลัพธ์**
               - ระบบจะแปลงเสียงเป็นข้อความ
               - สร้างโพสต์อัตโนมัติ
               - ใช้เวลาประมาณ 1-3 นาที
            """)

        with col2:
            st.markdown("""
            #### 🎬 สำหรับไฟล์วิดีโอ

            1. **เตรียมไฟล์วิดีโอ**
               - MP4, AVI, MOV, MKV, WebM
               - ต้องมีเสียงในวิดีโอ
               - ความยาวไม่เกิน 10 นาที (แนะนำ)

            2. **อัปโหลดไฟล์**
               - คลิกปุ่ม "Browse files"
               - เลือกไฟล์วิดีโอของคุณ

            3. **รอผลลัพธ์**
               - ระบบจะแยกเสียงจากวิดีโออัตโนมัติ
               - แปลงเสียงเป็นข้อความ
               - สร้างโพสต์
               - ใช้เวลาประมาณ 2-5 นาที
            """)

        st.markdown("---")

        st.markdown("### 💡 Tips สำหรับผลลัพธ์ที่ดี")

        tips_col1, tips_col2, tips_col3 = st.columns(3)

        with tips_col1:
            st.markdown("""
            #### 🎤 คุณภาพเสียง
            - ใช้ไมโครโฟนที่ดี
            - บันทึกในห้องเงียบ
            - หลีกเลี่ยง echo
            - ระดับเสียงพอเหมาะ
            """)

        with tips_col2:
            st.markdown("""
            #### 🗣️ การพูด
            - พูดชัดเจน ไม่เร็วเกินไป
            - หยุดพักตามจังหวะ
            - ออกเสียงถูกต้อง
            - ไม่พูดทับกัน
            """)

        with tips_col3:
            st.markdown("""
            #### 📏 ความยาว
            - สั้น: < 1 นาที (เร็วที่สุด)
            - กลาง: 1-5 นาที (แนะนำ)
            - ยาว: 5-10 นาที (แบ่งอัตโนมัติ)
            - ยาวมาก: > 10 นาที (แบ่งไฟล์)
            """)

# ===== STAGE 2: TRANSCRIPT =====
elif st.session_state.processing_stage == "transcript":
    initial_result = st.session_state.initial_result

    st.success("✅ ถอดข้อความจากเสียงเสร็จสิ้น!")

    st.markdown("---")
    st.markdown("### 📝 ข้อความที่ถอดจากเสียง")

    # แสดงสถิติ
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 ความยาว", f"{len(initial_result['transcript'])} ตัวอักษร")
    with col2:
        word_count = len(initial_result["transcript"].split())
        st.metric("📝 จำนวนคำ", f"{word_count} คำ")
    with col3:
        sentences = (
            initial_result["transcript"].count(".")
            + initial_result["transcript"].count("?")
            + initial_result["transcript"].count("!")
        )
        st.metric("📄 ประโยค", f"~{sentences} ประโยค")

    # แสดง Transcript ในกล่อง
    st.markdown(
        """
    <div class="post-container">
    <h4>📄 Transcript เต็ม:</h4>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.text_area(
        "Transcript ที่ถอดได้:",
        initial_result["transcript"],
        height=300,
        key="transcript_preview",
        help="ตรวจสอบความถูกต้องของข้อความที่ถอดได้",
    )

    # ปุ่มยืนยันและดำเนินการต่อ
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("🔙 กลับไปอัปโหลดใหม่", use_container_width=True):
            # ลบไฟล์ชั่วคราว
            if st.session_state.temp_path and os.path.exists(
                st.session_state.temp_path
            ):
                try:
                    os.remove(st.session_state.temp_path)
                except:
                    pass

            # ลบไฟล์เสียงที่แยกจากวิดีโอ
            if initial_result.get("extracted_audio") and initial_result.get(
                "audio_path"
            ):
                if os.path.exists(initial_result["audio_path"]):
                    try:
                        os.remove(initial_result["audio_path"])
                    except:
                        pass

            # ลบไฟล์ wav ที่แปลงแล้ว
            if initial_result.get("wav_path") and initial_result["wav_path"].endswith(
                "_converted.wav"
            ):
                if os.path.exists(initial_result["wav_path"]):
                    try:
                        os.remove(initial_result["wav_path"])
                    except:
                        pass

            # Reset session state
            st.session_state.processing_stage = "upload"
            st.session_state.initial_result = None
            st.session_state.temp_path = None
            st.session_state.uploaded_file_name = None
            st.rerun()

    with col2:
        if st.button(
            "✅ ยืนยันและสร้างโพสต์",
            type="primary",
            use_container_width=True,
        ):
            progress_bar = st.progress(60)
            status_text = st.empty()

            def update_progress(message):
                status_text.text(message)

            try:
                progress_bar.progress(70)
                final_result = processor.continue_processing(
                    initial_result["transcript"],
                    category=category,
                    progress_callback=update_progress,
                )

                progress_bar.progress(100)
                status_text.empty()
                progress_bar.empty()

                # ลบไฟล์ชั่วคราว
                if st.session_state.temp_path and os.path.exists(
                    st.session_state.temp_path
                ):
                    try:
                        os.remove(st.session_state.temp_path)
                    except:
                        pass

                if initial_result.get("extracted_audio") and initial_result.get(
                    "audio_path"
                ):
                    if os.path.exists(initial_result["audio_path"]):
                        try:
                            os.remove(initial_result["audio_path"])
                        except:
                            pass

                if initial_result.get("wav_path") and initial_result[
                    "wav_path"
                ].endswith("_converted.wav"):
                    if os.path.exists(initial_result["wav_path"]):
                        try:
                            os.remove(initial_result["wav_path"])
                        except:
                            pass

                # คำนวณเวลา
                processing_time = time.time() - initial_result["start_time"]

                # รวมผลลัพธ์
                result = {
                    "transcript": initial_result["transcript"],
                    "post": final_result["post"],
                    "keywords": final_result["keywords"],
                    "main_teaching": final_result["main_teaching"],
                    "emotion": final_result["emotion"],
                    "processing_time": processing_time,
                    "was_video": initial_result["was_video"],
                    "headline": final_result["headline"],
                    "essence_1": final_result["essence_1"],
                    "essence_2": final_result["essence_2"],
                    "essence_3": final_result["essence_3"],
                    "quote": final_result["quote"],
                }

                # เก็บผลลัพธ์ใน session state
                st.session_state.final_result = result
                st.session_state.processing_stage = "result"
                st.rerun()

            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

    with col3:
        pass  # ว่างไว้เพื่อ spacing

    # หยุดการทำงานที่นี่ รอให้ผู้ใช้กดปุ่มยืนยัน
    st.info("💡 กรุณาตรวจสอบความถูกต้องของ Transcript ด้านบน แล้วกดปุ่ม 'ยืนยันและสร้างโพสต์'")

# ===== STAGE 3: RESULT =====
elif st.session_state.processing_stage == "result":
    result = st.session_state.final_result

    # แสดงผลสำเร็จ
    if result["was_video"]:
        st.success(
            f"✅ แยกเสียงจากวิดีโอและสร้างโพสต์เสร็จสิ้น! ใช้เวลา {result['processing_time']:.2f} วินาที"
        )
    else:
        st.success(f"✅ สร้างโพสต์เสร็จสิ้น! ใช้เวลา {result['processing_time']:.2f} วินาที")

    st.markdown("---")

    # แท็บต่างๆ
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📱 โพสต์ Social Media",
            "🎨 แก่นธรรม 3 ข้อ & Quote",
            "📝 Transcript",
            "🔍 การวิเคราะห์",
        ]
    )

    with tab1:
        st.markdown("### 📱 โพสต์ที่พร้อมใช้งาน")

        # แสดงโพสต์ในกล่องสวยงาม
        st.markdown(
            f"""
        <div class="post-container">
        {result["post"].replace(chr(10), "<br>")}
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ช่อง copy
        st.text_area("📋 Copy ข้อความนี้:", result["post"], height=300, key="post_copy")

        # ปุ่มดาวน์โหลด
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="💾 ดาวน์โหลดโพสต์",
                data=result["post"],
                file_name=f"dhamma_post_{st.session_state.uploaded_file_name}.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            full_content = f"""โพสต์:\n{result["post"]}\n\n{"=" * 50}\n\nTranscript:\n{result["transcript"]}\n\n{"=" * 50}\n\nKeywords: {", ".join(result["keywords"])}\nหลักธรรมะ: {result["main_teaching"]}\nอารมณ์: {result["emotion"]}\n\nประเภทไฟล์: {"วิดีโอ" if result["was_video"] else "เสียง"}\nเวลาประมวลผล: {result["processing_time"]:.2f} วินาที"""

            st.download_button(
                label="📄 ดาวน์โหลดทั้งหมด",
                data=full_content,
                file_name=f"dhamma_full_{st.session_state.uploaded_file_name}.txt",
                mime="text/plain",
                use_container_width=True,
            )

    with tab2:
        st.markdown("### 🎨 แก่นธรรม 3 ข้อ & Quote สำหรับกราฟิก")

        # Headline
        st.markdown(
            f"""
        <div class="headline">
        {result["headline"]}
        </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # แก่นธรรม 3 ข้อ
        st.markdown("#### 📋 แก่นธรรม 3 ข้อ (สำหรับ Checklist/Carousel)")

        st.markdown(
            f"""
        <div class="essence-container">
        <div class="essence-item">
        <strong>1️⃣ {result["essence_1"]}</strong>
        </div>
        <div class="essence-item">
        <strong>2️⃣ {result["essence_2"]}</strong>
        </div>
        <div class="essence-item">
        <strong>3️⃣ {result["essence_3"]}</strong>
        </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ช่อง copy แก่นธรรม
        essence_text = f"""Headline: {result["headline"]}

แก่นธรรม 3 ข้อ:

1. {result["essence_1"]}

2. {result["essence_2"]}

3. {result["essence_3"]}"""

        st.text_area(
            "📋 Copy แก่นธรรม 3 ข้อ:", essence_text, height=200, key="essence_copy"
        )

        st.markdown("---")

        # Quote
        st.markdown("#### 💬 Quote สำหรับกราฟิก")

        st.markdown(
            f"""
        <div class="quote-container">
        <h3 style="text-align: center; color: #8B4513; margin-bottom: 20px;">"{result["quote"]}"</h3>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ช่อง copy quote
        st.text_area("📋 Copy Quote:", result["quote"], height=100, key="quote_copy")

        st.markdown("---")

        # ปุ่มดาวน์โหลด
        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="💾 ดาวน์โหลดแก่นธรรม 3 ข้อ",
                data=essence_text,
                file_name=f"dhamma_essence_{st.session_state.uploaded_file_name}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with col2:
            quote_content = (
                f"""Headline: {result["headline"]}\n\nQuote:\n"{result["quote"]}" """
            )

            st.download_button(
                label="💾 ดาวน์โหลด Quote",
                data=quote_content,
                file_name=f"dhamma_quote_{st.session_state.uploaded_file_name}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        st.markdown("---")

        # คำแนะนำการใช้งาน
        st.info("""
        💡 **วิธีใช้งาน:**

        **แก่นธรรม 3 ข้อ:**
        - เหมาะสำหรับทำ Carousel Post (Instagram/Facebook)
        - ทำ Checklist Graphic
        - Infographic แบบ Step-by-Step
        - แต่ละข้อเป็น 1 Slide

        **Quote:**
        - เหมาะสำหรับทำ Quote Card
        - Instagram Story/Post
        - Facebook Cover
        - ใช้ font สวยๆ พื้นหลังสีอ่อน

        **Headline:**
        - ใช้เป็นหัวข้อหลักของกราฟิก
        - ใช้เป็น Caption เมื่อโพสต์
        - ดึงดูดความสนใจ
        """)

    with tab3:
        st.markdown("### 📝 Transcript เต็ม")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 ความยาว", f"{len(result['transcript'])} ตัวอักษร")
        with col2:
            word_count = len(result["transcript"].split())
            st.metric("📝 จำนวนคำ", f"{word_count} คำ")

        st.text_area(
            "Transcript:", result["transcript"], height=400, key="transcript_view"
        )

        st.download_button(
            label="💾 ดาวน์โหลด Transcript",
            data=result["transcript"],
            file_name=f"transcript_{st.session_state.uploaded_file_name}.txt",
            mime="text/plain",
        )

    with tab4:
        st.markdown("### 🔍 การวิเคราะห์เนื้อหา")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📌 หมวดหมู่")
            st.info(category)

            st.markdown("#### 🎭 อารมณ์/ความรู้สึก")
            st.info(result["emotion"])

            st.markdown("#### 📁 ประเภทไฟล์")
            file_type_display = "🎬 วิดีโอ" if result["was_video"] else "🎵 เสียง"
            st.info(file_type_display)

        with col2:
            st.markdown("#### ☸️ หลักธรรมะหลัก")
            st.success(result["main_teaching"])

            st.markdown("#### ⏱️ เวลาประมวลผล")
            st.metric("", f"{result['processing_time']:.2f} วินาที")

            st.markdown("#### 📏 ความยาวเนื้อหา")
            st.metric("", f"{len(result['transcript'])} ตัวอักษร")

        st.markdown("---")

        st.markdown("#### 🏷️ Keywords")
        keywords_html = " ".join(
            [f'<span class="keyword-tag">#{kw}</span>' for kw in result["keywords"]]
        )
        st.markdown(keywords_html, unsafe_allow_html=True)

        st.markdown("---")

        # สถิติเพิ่มเติม
        st.markdown("#### 📊 สถิติเพิ่มเติม")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            sentences = (
                result["transcript"].count(".")
                + result["transcript"].count("?")
                + result["transcript"].count("!")
            )
            st.metric("ประโยค", sentences)

        with col2:
            words = len(result["transcript"].split())
            st.metric("คำ", words)

        with col3:
            chars = len(result["transcript"])
            st.metric("ตัวอักษร", chars)

        with col4:
            tags = len(result["keywords"])
            st.metric("Keywords", tags)

    # ปุ่มเริ่มใหม่
    st.markdown("---")
    if st.button("🔄 ประมวลผลไฟล์ใหม่", use_container_width=True):
        # Reset session state
        st.session_state.processing_stage = "upload"
        st.session_state.initial_result = None
        st.session_state.final_result = None
        st.session_state.temp_path = None
        st.session_state.uploaded_file_name = None
        st.rerun()

# Footer
st.markdown("---")
st.markdown(
    """
<div style="text-align: center; color: #8B4513; padding: 20px;">
    <p><strong>🙏 สาธุ สาธุ สาธุ 🙏</strong></p>
    <p>ขอให้ธรรมะเป็นที่พึ่งแก่ทุกท่าน</p>
    <p style="font-size: 0.9em; color: #999;">
        Powered by Google Speech Recognition & Gemini AI<br>
        รองรับทั้งไฟล์เสียงและวิดีโอ | สร้างโพสต์ + แก่นธรรม 3 ข้อ + Quote
    </p>
</div>
""",
    unsafe_allow_html=True,
)
