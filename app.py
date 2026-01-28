import streamlit as st
# 페이지 설정을 와이드 모드로 변경하고, 모바일 브라우저 탭에 보일 이름과 아이콘을 정합니다.
st.set_page_config(
    page_title="링크 올인원",
    page_icon="🔗",
    layout="wide",  # 이 부분이 핵심입니다! 화면을 넓게 사용하게 해줍니다.
    initial_sidebar_state="collapsed" # 모바일에서 왼쪽 메뉴를 기본으로 접어둡니다.
)
import yt_dlp
import whisper
import os
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import datetime
from collections import Counter
import pandas as pd
from deep_translator import GoogleTranslator
import asyncio
from shazamio import Shazam
import time  # [추가] 시간을 재기 위한 도구

# === [설정] 화면 넓게 쓰기 ===
st.set_page_config(page_title="Link All-in-One", page_icon="🔗", layout="wide")

# === [스타일링] CSS (가독성 끝판왕 적용) ===
st.markdown("""
<style>
    /* 전체 폰트 가독성: 더 진하고 선명하게 */
    html, body, [class*="css"] { 
        font-family: 'Pretendard', sans-serif; 
        font-size: 18px; 
        color: #212529; /* 거의 검은색에 가까운 진한 회색 */
    }
    
    /* 메인 타이틀: 압도적인 크기와 굵기 */
    h1 { 
        text-align: center; 
        color: #111111; 
        margin-bottom: 10px; 
        font-weight: 900; 
        font-size: 3.5rem !important; 
        letter-spacing: -2px;
    }
    
    /* 서브 설명 문구 */
    .sub-desc { 
        text-align: center; 
        color: #495057; 
        font-size: 1.4rem;
        margin-bottom: 50px; 
        font-weight: 600; 
    }
    
    /* 탭 메뉴: 버튼처럼 선명하게 */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; justify-content: center; }
    .stTabs [data-baseweb="tab"] {
        height: 65px; 
        background-color: #f1f3f5; 
        border-radius: 12px;
        color: #495057; 
        font-size: 20px !important; 
        font-weight: 800 !important;
        border: 2px solid #dee2e6; 
        padding: 0 40px !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #FF4B4B;
        border-color: #FF4B4B;
        background-color: #fff0f0;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #ffffff; 
        color: #FF4B4B; 
        border: 2px solid #FF4B4B;
        box-shadow: 0 6px 12px rgba(255, 75, 75, 0.15);
    }
    
    /* 캡션(설명) 글씨 잘 보이게 수정 */
    div[data-testid="stCaptionContainer"] {
        font-size: 16px !important;
        color: #343a40 !important; /* 진한 회색 */
        font-weight: 600;
        margin-bottom: 20px;
        background-color: #f8f9fa;
        padding: 10px 15px;
        border-radius: 8px;
        border-left: 5px solid #FF4B4B;
    }
    
    /* 카드 박스 디자인 */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 16px !important; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
        background: white; 
        padding: 30px; 
        border: 1px solid #e9ecef;
    }
    
    /* 버튼 디자인 */
    .stButton > button { 
        width: 100%; 
        border-radius: 12px; 
        font-weight: 800; 
        height: 55px; 
        font-size: 19px !important; 
        transition: all 0.2s;
    }
    
    /* 입력창 디자인 */
    .stTextInput > div > div > input { 
        font-size: 18px; 
        height: 55px; 
        font-weight: 500;
    }
    
    /* 사이드바 */
    [data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #dee2e6; 
    }
</style>
""", unsafe_allow_html=True)

# === [세션 & 변수] ===
if 'dl_info' not in st.session_state: st.session_state['dl_info'] = None
if 'sub_result' not in st.session_state: st.session_state['sub_result'] = None
if 'analyze_result' not in st.session_state: st.session_state['analyze_result'] = None
if 'music_result' not in st.session_state: st.session_state['music_result'] = None
SELECTED_MODEL = "large"

# === [함수 모음] ===
def format_time(seconds): return str(datetime.timedelta(seconds=int(seconds)))
def seconds_to_srt_time(seconds):
    millis = int((seconds - int(seconds)) * 1000)
    dt = datetime.timedelta(seconds=int(seconds))
    return f"{str(dt).zfill(8)},{millis:03d}"

def generate_srt(transcript_data):
    srt_content = ""
    for i, item in enumerate(transcript_data):
        start = item['start']
        end = start + item.get('duration', 3.0)
        srt_content += f"{i+1}\n{seconds_to_srt_time(start)} --> {seconds_to_srt_time(end)}\n{item['text']}\n\n"
    return srt_content

def get_video_info(url):
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl: return ydl.extract_info(url, download=False)

def download_video_file(url, resolution_key):
    filename = f"video_{resolution_key}.mp4"
    if os.path.exists(filename): os.remove(filename)
    format_str = 'bestvideo+bestaudio/best' if resolution_key == "best" else f'bestvideo[height<={resolution_key}]+bestaudio/best[height<={resolution_key}]'
    ydl_opts = {'format': format_str, 'merge_output_format': 'mp4', 'outtmpl': filename, 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        return filename
    except: return None

def download_audio_for_ai(url):
    filename = "temp_audio_tool"
    for f in os.listdir():
        if f.startswith(filename):
            try: os.remove(f)
            except: pass
    ydl_opts = {'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 'outtmpl': filename, 'quiet': True, 'no_warnings': True, 'ignoreerrors': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        target_file = filename + ".mp3"
        if os.path.exists(target_file) and os.path.getsize(target_file) > 0: return target_file
        else: return None
    except: return None

@st.cache_resource
def load_whisper_model(model_size): return whisper.load_model(model_size)

async def recognize_song(file_path):
    shazam = Shazam()
    try: return await shazam.recognize(file_path)
    except: return None

def find_bgm(file_path):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(recognize_song(file_path))

# ==========================================
# [사이드바]
# ==========================================
with st.sidebar:
    st.header("🔗 통합 링크 관리")
    st.markdown("여기에 링크를 넣고 **[전체 적용]** 버튼을 누르면, 모든 탭에 자동으로 링크가 입력됩니다.")
    
    shared_url = st.text_input("통합 URL 입력", placeholder="https://...", key="global_url")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🔄 전체 적용 & 검색 준비", type="primary"):
        if shared_url: st.success("모든 탭에 링크가 적용되었습니다! 이제 탭을 이동해 보세요.")
        else: st.warning("링크를 먼저 입력해주세요.")
    
    st.divider()
    st.info("**💡 지원 플랫폼**\nYouTube, Instagram, TikTok, Facebook 등 대부분의 영상 링크를 지원합니다.")

# === [메인 헤더] ===
# 변경 추천 (이모지를 넣으면 훨씬 생동감 있어 보입니다!)
st.title("🔗 링크 올인원 (Link All-in-One)")
st.markdown('<p class="sub-desc">링크 하나만 있으면 다운로드, 자막 생성, 번역, 분석, BGM 검색까지 한 번에 가능합니다.</p>', unsafe_allow_html=True)

# 탭 구성
t1, t2, t3, t4 = st.tabs([" 📥 미디어 다운로더 ", " 📝 자막/번역 ", " 📊 키워드 분석 ", " 🎵 BGM 검색 "])

# ==========================================
# [탭 1] 미디어 다운로더
# ==========================================
with t1:
    st.markdown("### 📥 미디어 다운로더 (비디오, 오디오, 썸네일)")
    st.caption("영상(MP4), 오디오(MP3), 썸네일(JPG)을 각각 원본 화질로 추출하여 저장합니다.")
    
    default_dl = shared_url if shared_url else ""
    c_in, c_btn = st.columns([4, 1])
    with c_in: url_dl = st.text_input("다운로드 링크", value=default_dl, placeholder="영상 링크를 붙여넣으세요", label_visibility="collapsed", key="dl_url")
    with c_btn: 
        if st.button("🔍 파일 검색", key="dl_search", type="primary"):
            if url_dl:
                with st.spinner("링크 정보를 분석하고 있습니다..."):
                    try: st.session_state['dl_info'] = get_video_info(url_dl)
                    except: st.error("올바른 링크인지 확인해주세요.")

    if st.session_state['dl_info']:
        info = st.session_state['dl_info']
        with st.container(border=True):
            ci1, ci2 = st.columns([1, 4])
            with ci1: st.image(info.get('thumbnail'), use_container_width=True)
            with ci2:
                st.subheader(info.get('title', '제목 없음'))
                st.markdown(f"**채널:** {info.get('uploader')} | **조회수:** {info.get('view_count', 0):,}회")

        st.divider()

        col1, col2, col3 = st.columns(3)

        # 영상
        with col1:
            with st.container(border=True):
                st.markdown("##### 🎬 영상 (MP4)")
                is_yt = 'youtube' in info.get('extractor', '').lower()
                res_key = "best"
                if is_yt:
                    res = st.selectbox("화질 선택", ("최고화질", "1080p", "720p"), label_visibility="collapsed")
                    res_key = {"최고화질":"best", "1080p":"1080", "720p":"720"}[res]
                else:
                    st.info("ℹ️ 원본 화질 자동 선택")
                    st.markdown("<div style='height: 2px'></div>", unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("영상 추출하기", key="btn_vid_ex"):
                    with st.spinner("다운로드 준비 중..."):
                        f = download_video_file(info['webpage_url'], res_key)
                        if f:
                            with open(f, "rb") as file:
                                st.download_button("💾 파일 저장", file, "video.mp4", "video/mp4", type="primary")

        # 오디오
        with col2:
            with st.container(border=True):
                st.markdown("##### 🎵 오디오 (MP3)")
                st.markdown("<div style='height: 42px'></div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("오디오 추출하기", key="btn_aud_ex"):
                    with st.spinner("MP3 변환 중..."):
                        f = download_audio_for_ai(info['webpage_url'])
                        if f:
                            with open(f, "rb") as file:
                                st.download_button("💾 파일 저장", file, "audio.mp3", "audio/mpeg", type="primary")

        # 썸네일
        with col3:
            with st.container(border=True):
                st.markdown("##### 🖼️ 썸네일 (JPG)")
                st.image(info.get('thumbnail'), use_container_width=True)
                st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                img_data = requests.get(info.get('thumbnail')).content
                st.download_button("💾 이미지 바로 저장", img_data, "thumb.jpg", "image/jpeg", type="primary")

# ==========================================
# [탭 2] 자막/번역
# ==========================================
with t2:
    st.markdown("### 📝 자막 생성 및 번역")
    st.caption("자막이 없어도 걱정 마세요. AI가 영상을 듣고 자막을 생성하며, 번역까지 해드립니다.")
    
    default_sub = shared_url if shared_url else ""
    with st.container(border=True):
        c_in, c_btn = st.columns([4, 1])
        with c_in: 
            url_sub = st.text_input("자막 링크", value=default_sub, placeholder="🔗 링크를 입력하세요", label_visibility="collapsed", key="sub_url")
        with c_btn:
            if st.button("🚀 자막 생성 시작", type="primary", key="sub_go"):
                if url_sub:
                    st.session_state['sub_result'] = []
                    
                    # [추가] 예상 시간 안내 메시지
                    st.info("⏳ 영상 길이에 따라 분석 시간이 달라집니다. (약 30초 ~ 60초 소요)")
                    
                    # [추가] 타이머 시작
                    start_time = time.time()
                    
                    with st.status("AI 분석을 시작합니다...", expanded=True) as status:
                        status.update(label="1. 공식 자막 스캔 중...")
                        found = False
                        try:
                            vid_id = parse_qs(urlparse(url_sub).query)['v'][0]
                            raw = YouTubeTranscriptApi.get_transcript(vid_id, languages=['ko', 'en'])
                            st.session_state['sub_result'] = [{'start':l['start'], 'duration':l.get('duration',3.0), 'text':l['text']} for l in raw]
                            found = True
                        except: pass
                        
                        if not found:
                            status.update(label="2. AI(Large 모델)가 영상을 정밀 분석 중입니다...")
                            f = download_audio_for_ai(url_sub)
                            if f:
                                model = load_whisper_model(SELECTED_MODEL)
                                res = model.transcribe(f, fp16=False)
                                st.session_state['sub_result'] = [{'start':s['start'], 'duration':s['end']-s['start'], 'text':s['text']} for s in res['segments']]
                                if os.path.exists(f): os.remove(f)
                        
                        # [추가] 타이머 종료 및 완료 메시지 업데이트
                        end_time = time.time()
                        elapsed_time = end_time - start_time
                        status.update(label=f"완료! ({int(elapsed_time)}초 소요)", state="complete", expanded=False)

    if st.session_state['sub_result']:
        data = st.session_state['sub_result']
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.container(border=True):
            col_tool1, col_tool2, col_tool3 = st.columns([1, 3, 1])
            with col_tool1: st.markdown("**🌐 번역 도구**")
            with col_tool2: target_lang = st.selectbox("언어 선택", ("한국어", "영어", "일본어", "중국어", "스페인어"), label_visibility="collapsed")
            with col_tool3:
                if st.button("번역 실행", key="trans_run"):
                    with st.spinner("번역 중..."):
                        lang_map = {"한국어":"ko", "영어":"en", "일본어":"ja", "중국어":"zh-CN", "스페인어":"es"}
                        trans = GoogleTranslator(source='auto', target=lang_map[target_lang])
                        res = []
                        for i in data:
                            try: res.append({**i, 'text': trans.translate(i['text'])})
                            except: res.append(i)
                        st.session_state['sub_result'] = res
                        st.rerun()

        col_view, col_ctrl = st.columns([3, 1])
        
        txt_pure = "".join([f"{d['text']} " for d in data])
        txt_time = "".join([f"[{format_time(d['start'])}] {d['text']}\n" for d in data])
        txt_srt = generate_srt(data)
        
        with col_ctrl:
            with st.container(border=True):
                st.markdown("#### 👁️ 보기 설정")
                view_mode = st.radio("형식 선택", ("텍스트", "타임스탬프", "SRT 파일"), label_visibility="collapsed")
                
                st.markdown("---")
                
                if view_mode == "텍스트":
                    final_data, file_name = txt_pure, "subtitle.txt"
                elif view_mode == "타임스탬프":
                    final_data, file_name = txt_time, "timestamp.txt"
                else:
                    final_data, file_name = txt_srt, "subtitle.srt"
                
                st.markdown("#### 💾 파일 저장")
                st.download_button("파일 다운로드", data=final_data, file_name=file_name, type="primary", use_container_width=True)

        with col_view:
            st.text_area(f"📜 미리보기 ({view_mode})", value=final_data, height=500)

# ==========================================
# [탭 3] 키워드 분석
# ==========================================
with t3:
    st.markdown("### 📊 영상 내용 분석")
    st.caption("영상 전체를 보지 않아도, 핵심 키워드와 요약 정보를 통해 내용을 빠르게 파악할 수 있습니다.")
    
    default_an = shared_url if shared_url else ""
    c_in, c_btn = st.columns([4, 1])
    with c_in: url_an = st.text_input("링크", value=default_an, placeholder="영상 링크 입력", label_visibility="collapsed", key="an_url")
    with c_btn:
        if st.button("분석 시작", type="primary", key="an_go"):
            if url_an:
                # [추가] 분석 시간 안내 및 타이머
                st.info("⏳ 내용 분석에는 약 30~60초 정도 소요됩니다.")
                start_time = time.time()
                
                with st.spinner("키워드를 추출하고 있습니다..."):
                    temp_data = []
                    try:
                        vid_id = parse_qs(urlparse(url_an).query)['v'][0]
                        raw = YouTubeTranscriptApi.get_transcript(vid_id, languages=['ko', 'en'])
                        temp_data = [{'text':l['text']} for l in raw]
                    except:
                        f = download_audio_for_ai(url_an)
                        if f:
                            model = load_whisper_model(SELECTED_MODEL)
                            res = model.transcribe(f, fp16=False)
                            temp_data = [{'text':s['text']} for s in res['segments']]
                            if os.path.exists(f): os.remove(f)
                    st.session_state['analyze_result'] = temp_data
                
                end_time = time.time()
                elapsed_time = end_time - start_time
                st.success(f"분석 완료! (총 {int(elapsed_time)}초 소요)")

    if st.session_state['analyze_result']:
        data = st.session_state['analyze_result']
        full_text = " ".join([d['text'] for d in data])
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("#### 🏆 많이 언급된 단어 (Top 10)")
                words = [w for w in full_text.split() if len(w) >= 2]
                if words:
                    df = pd.DataFrame(Counter(words).most_common(10), columns=['단어', '빈도']).set_index('단어')
                    st.bar_chart(df, color="#FF4B4B")
        with c2:
            with st.container(border=True):
                st.markdown("#### 🕵️‍♀️ 족집게 키워드 검색")
                q = st.text_input("찾고 싶은 단어를 입력하세요", key="k_search")
                if q:
                    found = [d['text'] for d in data if q in d['text']]
                    st.success(f"총 {len(found)}번 발견되었습니다!")
                    for text in found[:5]: st.markdown(f"- ...{text.replace(q, f'**{q}**')}...")

# ==========================================
# [탭 4] BGM 검색
# ==========================================
with t4:
    st.markdown("### 🎵 배경음악(BGM) 검색")
    st.caption("이 영상에 나온 노래 제목이 궁금하신가요? AI가 배경음악을 듣고 제목과 가수를 찾아줍니다.")
    
    default_bgm = shared_url if shared_url else ""
    c_in, c_btn = st.columns([4, 1])
    with c_in: url_bgm = st.text_input("링크", value=default_bgm, placeholder="영상 링크 입력", label_visibility="collapsed", key="bgm_url")
    with c_btn:
        if st.button("음악 찾기", type="primary", key="bgm_go"):
            if url_bgm:
                # [추가] 검색 시간 안내 및 타이머
                st.info("⏳ 오디오 추출 및 검색에는 약 30~50초가 소요됩니다.")
                start_time = time.time()
                
                with st.status("음악을 분석하고 있습니다...", expanded=True) as status:
                    st.write("1. 오디오 추출 중...")
                    f = download_audio_for_ai(url_bgm)
                    if f:
                        st.write("2. Shazam 데이터베이스 조회 중...")
                        res = find_bgm(f)
                        st.session_state['music_result'] = res
                        if os.path.exists(f): os.remove(f)
                        
                        end_time = time.time()
                        elapsed_time = end_time - start_time
                        status.update(label=f"완료! ({int(elapsed_time)}초 소요)", state="complete", expanded=False)
                    else: st.error("오디오 추출에 실패했습니다.")

    if st.session_state['music_result']:
        res = st.session_state['music_result']
        if 'track' in res:
            track = res['track']
            with st.container(border=True):
                i1, i2 = st.columns([1, 3])
                with i1: st.image(track['images']['coverart'], use_container_width=True)
                with i2:
                    st.subheader(track['title'])
                    st.markdown(f"**아티스트:** {track['subtitle']}")
                    if 'sections' in track:
                        for s in track['sections']:
                            if s['type']=='VIDEO' and 'youtubeurl' in s:
                                st.markdown(f"[▶️ 유튜브에서 듣기]({s['youtubeurl']})")

        else: st.warning("음악 정보를 찾을 수 없습니다. (너무 짧거나 효과음일 수 있습니다.)")


