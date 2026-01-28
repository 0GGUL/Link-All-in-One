import streamlit as st
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
import time 

# === [설정] 화면 구성 설정 ===
st.set_page_config(
    page_title="Link All-in-One", 
    page_icon="🔗", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# === [스타일링] 반응형 CSS ===
st.markdown("""
<style>
    /* 1. 메인 컨테이너 (PC에서 넓게 1400px) */
    .block-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
    }
    
    /* 2. 제목 (H1) - 중앙 정렬 & 한 줄 유지 */
    h1 { 
        text-align: center !important; 
        color: #111111; 
        margin-bottom: 15px; 
        font-weight: 900; 
        font-size: calc(1.8rem + 1.5vw) !important; 
        letter-spacing: -1px;
        white-space: nowrap !important; 
    }
    
    /* 3. 설명 문구 (.sub-desc) - 무조건 한 줄로! */
    .sub-desc { 
        text-align: center !important; 
        color: #495057; 
        font-size: 1.15rem; 
        width: 100%; /* 화면 전체 폭 사용 */
        max-width: none !important; /* 너비 제한 해제 (이게 문제였음) */
        margin: 0 auto 40px auto; 
        white-space: nowrap !important; /* 강제 한 줄 유지 */
        overflow: hidden; /* 넘치면 깔끔하게 처리 */
        text-overflow: ellipsis; 
    }

    /* 4. 기타 필수 설정 */
    html, body, [data-testid="stAppViewContainer"] {
        max-width: 100vw;
        overflow-x: hidden !important;
    }
    div, span, p, button, input {
        word-break: break-word !important; 
        white-space: normal !important;
    }
    
    /* 탭 메뉴 */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; 
        justify-content: center; 
        flex-wrap: wrap; 
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px; 
        background-color: #f1f3f5; 
        border-radius: 10px;
        color: #495057; 
        font-size: 15px !important; 
        font-weight: 700 !important;
        border: 1px solid #dee2e6; 
        padding: 0 15px !important;
        flex-grow: 1; 
        min-width: 80px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #ffffff; 
        color: #FF4B4B; 
        border: 2px solid #FF4B4B;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    /* 버튼 및 입력창 */
    .stButton > button { 
        width: 100%; 
        border-radius: 10px; 
        font-weight: 700; 
        height: auto !important; 
        min-height: 48px;
        padding: 10px !important;
        font-size: 16px !important;
    }
    .stTextInput > div > div > input {
        min-height: 48px;
        font-size: 16px;
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
    # 기존 파일 정리
    filename = "temp_audio_tool"
    for f in os.listdir():
        if f.startswith(filename):
            try: os.remove(f)
            except: pass
    
    # [수정] 다운로드 옵션 강화
    ydl_opts = {
        'format': 'bestaudio/best', 
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}], 
        'outtmpl': filename, 
        'quiet': True, 
        'no_warnings': True, 
        'ignoreerrors': True,
        # 봇 차단 회피용 헤더
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        target_file = filename + ".mp3"
        
        # [중요] 파일이 진짜 존재하는지, 그리고 텅 빈 파일(0 bytes)은 아닌지 체크
        if os.path.exists(target_file):
            file_size = os.path.getsize(target_file)
            if file_size > 1000: # 최소 1KB 이상이어야 정상
                return target_file
            else:
                return None # 파일은 있는데 너무 작으면(오류 파일) 실패 처리
        else: 
            return None
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
        if shared_url: st.success("적용 완료!")
        else: st.warning("링크를 먼저 입력해주세요.")
    
    st.divider()
    st.info("**💡 지원 플랫폼**\nYouTube, Instagram, TikTok 등")

# === [메인 헤더] ===
st.title("🔗 링크 올인원 (Link All-in-One)")
st.markdown('<p class="sub-desc">링크 하나만 있으면 다운로드, 자막 생성, 번역, 분석, BGM 검색까지 한 번에 가능합니다.</p>', unsafe_allow_html=True)

# 탭 구성
t1, t2, t3, t4 = st.tabs([" 📥 미디어 다운로더 ", " 📝 자막/번역 ", " 📊 키워드 분석 ", " 🎵 BGM 검색 "])

# ==========================================
# [탭 1] 미디어 다운로더
# ==========================================
with t1:
    st.markdown("#### 📥 미디어 다운로더")
    st.caption("영상(MP4), 오디오(MP3), 썸네일(JPG)을 각각 원본 화질로 추출하여 저장합니다.")
    
    default_dl = shared_url if shared_url else ""
    c_in, c_btn = st.columns([3, 1])
    with c_in: url_dl = st.text_input("다운로드 링크", value=default_dl, placeholder="영상 링크를 붙여넣으세요", label_visibility="collapsed", key="dl_url")
    with c_btn: 
        if st.button("🔍 검색", key="dl_search", type="primary"):
            if url_dl:
                with st.spinner("링크 정보를 분석하고 있습니다..."):
                    try: st.session_state['dl_info'] = get_video_info(url_dl)
                    except: st.error("올바른 링크인지 확인해주세요.")

    if st.session_state['dl_info']:
        info = st.session_state['dl_info']
        with st.container(border=True):
            ci1, ci2 = st.columns([1, 2])
            with ci1: st.image(info.get('thumbnail'), use_container_width=True)
            with ci2:
                st.subheader(info.get('title', '제목 없음'))
                st.markdown(f"**채널:** {info.get('uploader')} | **조회수:** {info.get('view_count', 0):,}회")

        st.divider()

        col1, col2, col3 = st.columns(3)

        # 영상
        with col1:
            with st.container(border=True):
                st.markdown("##### 🎬 영상")
                is_yt = 'youtube' in info.get('extractor', '').lower()
                res_key = "best"
                if is_yt:
                    res = st.selectbox("화질 선택", ("최고화질", "1080p", "720p"), label_visibility="collapsed")
                    res_key = {"최고화질":"best", "1080p":"1080", "720p":"720"}[res]
                else:
                    st.info("원본 화질")
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("영상 저장", key="btn_vid_ex"):
                    with st.spinner("다운로드 중..."):
                        f = download_video_file(info['webpage_url'], res_key)
                        if f:
                            with open(f, "rb") as file:
                                st.download_button("💾 받기", file, "video.mp4", "video/mp4", type="primary")

        # 오디오
        with col2:
            with st.container(border=True):
                st.markdown("##### 🎵 오디오")
                st.markdown("<div style='height: 42px'></div>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("오디오 저장", key="btn_aud_ex"):
                    with st.spinner("변환 중..."):
                        f = download_audio_for_ai(info['webpage_url'])
                        if f:
                            with open(f, "rb") as file:
                                st.download_button("💾 받기", file, "audio.mp3", "audio/mpeg", type="primary")

        # 썸네일
        with col3:
            with st.container(border=True):
                st.markdown("##### 🖼️ 썸네일")
                st.image(info.get('thumbnail'), use_container_width=True)
                st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                img_data = requests.get(info.get('thumbnail')).content
                st.download_button("💾 받기", img_data, "thumb.jpg", "image/jpeg", type="primary")

# ==========================================
# [탭 2] 자막/번역 (수정됨: 재시도 안내 문구 추가)
# ==========================================
with t2:
    st.markdown("#### 📝 자막 생성 및 번역")
    st.caption("AI가 영상을 분석하여 자막을 생성합니다. (시간이 조금 걸릴 수 있습니다)")
    
    default_sub = shared_url if shared_url else ""
    with st.container(border=True):
        c_in, c_btn = st.columns([3, 1])
        with c_in: 
            url_sub = st.text_input("자막 링크", value=default_sub, placeholder="🔗 링크를 입력하세요", label_visibility="collapsed", key="sub_url")
        with c_btn:
            if st.button("🚀 생성 시작", type="primary", key="sub_go"):
                if url_sub:
                    st.session_state['sub_result'] = []
                    
                    start_time = time.time()
                    progress_text = "작업을 준비하고 있습니다..."
                    my_bar = st.progress(0, text=progress_text)
                    
                    found = False
                    
                    # 1단계: 공식 자막
                    my_bar.progress(20, text="1. 공식 자막을 검색하고 있습니다...")
                    try:
                        vid_id = parse_qs(urlparse(url_sub).query)['v'][0]
                        raw = YouTubeTranscriptApi.get_transcript(vid_id, languages=['ko', 'en'])
                        st.session_state['sub_result'] = [{'start':l['start'], 'duration':l.get('duration',3.0), 'text':l['text']} for l in raw]
                        found = True
                        my_bar.progress(100, text="공식 자막을 찾았습니다!")
                        time.sleep(0.5)
                        my_bar.empty()
                        st.success(f"✅ 완료!")
                    except: pass
                    
                    # 2단계: AI 분석
                    if not found:
                        my_bar.progress(40, text="2. 오디오를 다운로드 중입니다...")
                        f = download_audio_for_ai(url_sub)
                        
                        if f:
                            try:
                                my_bar.progress(60, text="3. AI 모델(Whisper)을 준비 중입니다...")
                                model = load_whisper_model(SELECTED_MODEL)
                                
                                my_bar.progress(80, text="4. 영상을 분석하고 있습니다 (잠시만 기다려주세요)...")
                                res = model.transcribe(f, fp16=False)
                                
                                st.session_state['sub_result'] = [{'start':s['start'], 'duration':s['end']-s['start'], 'text':s['text']} for s in res['segments']]
                                
                                my_bar.progress(100, text="완료!")
                                end_time = time.time()
                                elapsed_time = end_time - start_time
                                time.sleep(0.5)
                                my_bar.empty() 
                                st.success(f"✅ 분석 완료! (총 {int(elapsed_time)}초 소요)")
                            except Exception as e:
                                my_bar.empty()
                                st.error(f"⚠️ 분석 중 오류가 발생했습니다: {str(e)}")
                            finally:
                                if os.path.exists(f): os.remove(f)
                        else:
                            my_bar.empty()
                            # [수정] 에러 메시지를 '재시도 안내'로 변경
                            st.warning("⚠️ **연결이 지연되고 있습니다. '생성 시작' 버튼을 한 번 더 눌러주세요!**")
                            st.caption("(유튜브 보안으로 인해 첫 시도는 차단될 수 있습니다. 다시 클릭하면 정상 작동합니다.)")

    # [추가] 팁 메시지 (항상 보이도록 배치)
    st.info("💡 **Tip:** 만약 '오디오 다운로드 실패'가 뜨면, **버튼을 다시 한 번 클릭**해 주세요. (서버 연결 갱신)")

    if st.session_state['sub_result']:
        data = st.session_state['sub_result']
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.container(border=True):
            col_tool1, col_tool2, col_tool3 = st.columns([1, 2, 1])
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

        col_view, col_ctrl = st.columns([2, 1])
        
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
# [탭 3] 키워드 분석 (AI 제거 -> 태그/자막 기반 초고속 모드)
# ==========================================
with t3:
    st.markdown("#### 📊 영상 태그 & 키워드 분석")
    st.caption("유튜버가 등록한 **공식 태그**와 **자막**을 기반으로 빠르게 분석합니다. (AI 음성 분석 제외)")
    
    default_an = shared_url if shared_url else ""
    c_in, c_btn = st.columns([3, 1])
    with c_in: url_an = st.text_input("링크", value=default_an, placeholder="영상 링크 입력", label_visibility="collapsed", key="an_url")
    with c_btn:
        if st.button("분석 시작", type="primary", key="an_go"):
            if url_an:
                start_time = time.time()
                
                # 로딩바 초기화
                my_bar = st.progress(0, text="데이터를 조회하고 있습니다...")
                
                temp_data = []
                video_tags = []
                
                # 1. 태그(메타데이터) 추출 (50%)
                my_bar.progress(50, text="1. 공식 태그(해시태그) 수집 중...")
                try:
                    meta = get_video_info(url_an)
                    video_tags = meta.get('tags', [])
                except: pass

                # 2. 공식 자막 추출 (80%) - 자막이 있으면 내용 분석까지 가능
                my_bar.progress(80, text="2. 자막 데이터 확인 중...")
                try:
                    vid_id = parse_qs(urlparse(url_an).query)['v'][0]
                    raw = YouTubeTranscriptApi.get_transcript(vid_id, languages=['ko', 'en'])
                    temp_data = [{'text':l['text']} for l in raw]
                except: pass
                
                # 완료 처리
                my_bar.progress(100, text="완료!")
                time.sleep(0.3)
                my_bar.empty()
                
                # 결과 저장
                st.session_state['analyze_result'] = temp_data
                st.session_state['video_tags'] = video_tags
                
                elapsed = int(time.time() - start_time)
                
                if video_tags or temp_data:
                    st.success(f"✅ 분석 완료! (총 {elapsed}초 소요)")
                else:
                    st.warning("⚠️ 분석할 데이터(태그 또는 자막)를 찾지 못했습니다.")

    # === 결과 화면 출력 ===
    
    # 1. 업로더 공식 태그 (가장 중요)
    if 'video_tags' in st.session_state and st.session_state['video_tags']:
        with st.container(border=True):
            st.markdown("#### 🏷️ 업로더 공식 태그 (Hidden Tags)")
            st.caption("유튜버가 검색 노출을 위해 영상에 심어둔 핵심 키워드입니다.")
            
            tags_html = ""
            for t in st.session_state['video_tags']:
                tags_html += f"<span style='background-color:#f1f3f5; padding:6px 12px; border-radius:20px; margin-right:8px; margin-bottom:8px; display:inline-block; font-size:15px; font-weight:600; color:#333; border:1px solid #dee2e6;'>#{t}</span> "
            st.markdown(tags_html, unsafe_allow_html=True)
    
    # 2. 내용 빈도수 분석 (자막이 있는 경우에만 표시)
    if st.session_state['analyze_result']:
        data = st.session_state['analyze_result']
        full_text = " ".join([d['text'] for d in data])
        
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("#### 🏆 최다 언급 단어 (Top 10)")
                st.caption("자막 내용을 바탕으로 분석했습니다.")
                words = [w for w in full_text.split() if len(w) >= 2]
                if words:
                    df = pd.DataFrame(Counter(words).most_common(10), columns=['단어', '빈도']).set_index('단어')
                    st.bar_chart(df, color="#FF4B4B", horizontal=True)
        with c2:
            with st.container(border=True):
                st.markdown("#### 🕵️‍♀️ 대본 검색")
                q = st.text_input("자막 내용 검색", key="k_search")
                if q:
                    found = [d['text'] for d in data if q in d['text']]
                    st.success(f"총 {len(found)}번 발견!")
                    for text in found[:3]: st.markdown(f"- ...{text.replace(q, f'**{q}**')}...")
    
    elif 'video_tags' in st.session_state and st.session_state['video_tags']:
        # 태그는 찾았는데 자막이 없는 경우 안내 메시지
        st.info("ℹ️ 이 영상은 자막(CC)이 없어서 상세 내용 분석/검색은 건너뛰었습니다. (공식 태그만 표시됨)")

# ==========================================
# [탭 4] BGM 검색
# ==========================================
with t4:
    st.markdown("#### 🎵 배경음악(BGM) 검색")
    st.caption("배경음악 제목과 가수를 찾아줍니다.")
    
    default_bgm = shared_url if shared_url else ""
    c_in, c_btn = st.columns([3, 1])
    with c_in: url_bgm = st.text_input("링크", value=default_bgm, placeholder="영상 링크 입력", label_visibility="collapsed", key="bgm_url")
    with c_btn:
        if st.button("음악 찾기", type="primary", key="bgm_go"):
            if url_bgm:
                st.info("⏳ 약 30~50초 소요")
                start_time = time.time()
                
                with st.status("분석 중...", expanded=True) as status:
                    st.write("오디오 추출 중...")
                    f = download_audio_for_ai(url_bgm)
                    if f:
                        st.write("데이터베이스 조회 중...")
                        res = find_bgm(f)
                        st.session_state['music_result'] = res
                        if os.path.exists(f): os.remove(f)
                        status.update(label="완료!", state="complete", expanded=False)
                    else: 
                        status.update(label="실패", state="error")
                        st.error("오디오 추출 실패")

    if st.session_state['music_result']:
        res = st.session_state['music_result']
        if 'track' in res:
            track = res['track']
            with st.container(border=True):
                i1, i2 = st.columns([1, 2])
                with i1: st.image(track['images']['coverart'], use_container_width=True)
                with i2:
                    st.subheader(track['title'])
                    st.markdown(f"**아티스트:** {track['subtitle']}")
                    if 'sections' in track:
                        for s in track['sections']:
                            if s['type']=='VIDEO' and 'youtubeurl' in s:
                                st.markdown(f"[▶️ 유튜브에서 듣기]({s['youtubeurl']})")
        else: st.warning("음악 정보를 찾을 수 없습니다.")
