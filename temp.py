import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import re
import math
import threading
import time
import folium
from streamlit_folium import st_folium
import altair as alt 

# Gemini API 라이브러리
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --------------------------------------------------------------------------
# 1. 환경 설정 및 세션 상태
# --------------------------------------------------------------------------
st.set_page_config(page_title="Bu-T : 지역 상권 살리기 AI 큐레이터", page_icon="🌊", layout="wide")

custom_css = """
<style>
/* 전체 배경 - 부산 바다의 시원한 느낌 */
.stApp {
    background: linear-gradient(135deg, #E0F2FE 0%, #FFFFFF 100%);
}

/* 상단 공백 대폭 축소 및 기본 헤더 투명화 */
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
}
header {
    background-color: transparent !important;
}

/* 제목 및 텍스트 색상 포인트 */
h1, h2, h3, h4, h5 {
    color: #004E98 !important;
    font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
}

/* 메인 액션 버튼 커스텀 */
div.stButton > button, div.stFormSubmitButton > button {
    background: linear-gradient(135deg, #0078D7 0%, #00C6FF 100%) !important;
    color: white !important;
    font-size: 18px !important;
    font-weight: 800 !important;
    border: none !important;
    border-radius: 50px !important;
    padding: 12px 24px !important;
    box-shadow: 0 6px 15px rgba(0, 198, 255, 0.3) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    width: 100%;
}
div.stButton > button:hover, div.stFormSubmitButton > button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 10px 25px rgba(0, 198, 255, 0.5) !important;
    color: white !important;
}

/* 페르소나 테스트 폼 박스 스타일 */
[data-testid="stForm"] {
    background-color: rgba(255, 255, 255, 0.85);
    border-radius: 25px;
    padding: 40px;
    box-shadow: 0px 10px 30px rgba(0, 78, 152, 0.08);
    border: 2px solid #BAE6FD;
}

/* 각종 컨테이너 및 확장 패널 커스텀 */
[data-testid="stExpander"] {
    background-color: white;
    border-radius: 15px;
    box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.05);
    border: 1px solid #E0F2FE;
}

/* 상단 라디오버튼 (메뉴 탭) 배경 */
div[role="radiogroup"] {
    background-color: rgba(255, 255, 255, 0.7);
    padding: 10px;
    border-radius: 15px;
}

hr {
    border-color: #BAE6FD !important;
}

.center-text {
    text-align: center;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)


if 'test_completed' not in st.session_state:
    st.session_state.test_completed = False
if 'user_persona' not in st.session_state:
    st.session_state.user_persona = ""
if 'refresh_seed' not in st.session_state:
    st.session_state.refresh_seed = 42
if 'scroll_to_top' not in st.session_state:
    st.session_state.scroll_to_top = False

# --------------------------------------------------------------------------
# 2. 노선 정보 및 좌표
# --------------------------------------------------------------------------
ROUTE_STOPS = {
    "레드라인 (해운대 방면)": ["부산역", "UN기념공원", "부산박물관", "용호만유람선터미널", "광안리해수욕장", "마린시티(수영만요트경기장)", "동백섬", "해운대해수욕장", "센텀시티(영화의전당)", "시립미술관벡스코", "평화공원", "광복로"],
    "그린라인 (영도/남포 방면)": ["부산역", "영도대교(유라리광장)", "흰여울문화마을", "하늘전망대", "태종대", "국립해양박물관", "아르떼뮤지엄부산", "오륙도스카이워크", "용호만유람선터미널", "평화공원", "송도해수욕장(구름산책로)", "자갈치BIFF광장(용두산공원)"],
    "오렌지라인 (다대포 방면)": ["부산역", "송도해수욕장(구름산책로)", "암남공원(용궁구름다리)", "감천문화마을(감천사거리)", "다대포해수욕장(몰운대)", "아미산전망대", "부네치아장림항", "석당박물관(부산임시수도청사)", "국제시장(보수동책방골목)", "용두산공원(부산근현대역사관)"]
}

ROUTE_INFO = {
    "레드라인 (해운대 방면)": {
        "tag": "화려한 도심과 오션뷰를 만끽하는 베스트셀러",
        "desc": "부산역에서 출발해 광안리, 해운대, 센텀시티 등 부산의 화려한 도심과 환상적인 해안 경관을 만끽하는 노선입니다. 수영만 요트경기장과 마린시티의 마천루를 지나며 부산의 가장 현대적이고 이국적인 풍경을 감상할 수 있습니다.",
        "color": "red",
        "info": "⏱️ **운행정보:** 50분 간격 / 일 9회 운행 (수~일)\n\n🚌 **차량배차:** 1층·2층 버스 랜덤 배차\n\n⚠️ **주의사항:** 마지막 9회차 차량은 'UN기념공원'과 '부산박물관'을 무정차 통과합니다."
    },
    "그린라인 (영도/남포 방면)": {
        "tag": "원도심의 활기와 해안 절경을 품은 자연·역사 코스",
        "desc": "영도대교를 건너 흰여울문화마을, 태종대, 송도 등 부산의 옛 정취와 깎아지른 해안 절경을 탐방하는 노선입니다. 남포동, 자갈치시장이 있는 원도심의 활기찬 에너지를 함께 느낄 수 있습니다.",
        "color": "green",
        "info": "⏱️ **운행정보:** 50분 간격 / 일 9회 운행 (수~일)\n\n🚌 **차량배차:** 1층·2층 버스 랜덤 배차"
    },
    "오렌지라인 (다대포 방면)": {
        "tag": "아름다운 낙동강 생태자원과 환상적인 일몰 코스",
        "desc": "감천문화마을을 지나 다대포해수욕장의 그림 같은 일몰과 을숙도의 생태 자연을 만나는 감성 충만 노선입니다. '부네치아' 장림항과 아미산 전망대의 탁 트인 낙동강 뷰가 일품입니다.",
        "color": "orange",
        "info": "⏱️ **운행정보:** 80분 간격 / 일 6회 운행 (수~일)\n\n🚌 **차량배차:** 경사로 및 산지 구간 운행으로 1층 버스 전용 운행\n\n🔄 **환승꿀팁:** 송도해수욕장(송도구름산책로) 건너편 승강장 이동 후 그린라인으로 환승 가능"
    }
}

STOP_COORDS = {
    "부산역": (35.114572, 129.040259), "UN기념공원": (35.128819, 129.093905), "부산박물관": (35.130129, 129.092948),
    "용호만유람선터미널": (35.132812, 129.114482), "광안리해수욕장": (35.152945, 129.117992), "마린시티(수영만요트경기장)": (35.15679, 129.141342),
    "동백섬": (35.157764, 129.151372), "해운대해수욕장": (35.159525, 129.161033), "센텀시티(영화의전당)": (35.168467, 129.13056),
    "시립미술관벡스코": (35.167466, 129.136742), "평화공원": (35.127003, 129.101409), "광복로": (35.099909, 129.036724),
    "영도대교(유라리광장)": (35.096986, 129.035942), "흰여울문화마을": (35.079996, 129.043616), "하늘전망대": (35.072121, 129.055211),
    "태종대": (35.062254, 129.081303), "국립해양박물관": (35.078343, 129.078829), "아르떼뮤지엄부산": (35.085816, 129.075669),
    "오륙도스카이워크": (35.101561, 129.121979), "송도해수욕장(구름산책로)": (35.077331, 129.021383), "자갈치BIFF광장(용두산공원)": (35.098134, 129.03132),
    "암남공원(용궁구름다리)": (35.063142, 129.019182), "감천문화마을(감천사거리)": (35.087888, 129.004217), "다대포해수욕장(몰운대)": (35.048406, 128.965512),
    "아미산전망대": (35.052472, 128.96115), "부네치아장림항": (35.078989, 128.951268), "석당박물관(부산임시수도청사)": (35.104386, 129.019941),
    "국제시장(보수동책방골목)": (35.103087, 129.026452), "용두산공원(부산근현대역사관)": (35.10285, 129.03228)
}

STOP_KEYWORD_MAP = {
    "부산역": ["부산역", "상해거리", "차이나타운", "초량이바구길"],
    "UN기념공원": ["UN기념공원", "유엔기념공원"],
    "부산박물관": ["부산박물관"],
    "용호만유람선터미널": ["유람선", "이기대"],
    "광안리해수욕장": ["광안리", "광안대교"],
    "마린시티(수영만요트경기장)": ["마린시티", "요트경기장", "영화의거리"],
    "동백섬": ["동백섬", "누리마루"],
    "해운대해수욕장": ["해운대", "미포"],
    "센텀시티(영화의전당)": ["센텀시티", "영화의전당"],
    "시립미술관벡스코": ["시립미술관", "벡스코"],
    "평화공원": ["평화공원"],
    "광복로": ["광복로"],
    "영도대교(유라리광장)": ["영도대교", "유라리"],
    "흰여울문화마을": ["흰여울문화마을", "흰여울"],
    "하늘전망대": ["하늘전망대", "절영해안"],
    "태종대": ["태종대"],
    "국립해양박물관": ["해양박물관", "아미르공원"],
    "아르떼뮤지엄부산": ["아르떼뮤지엄"],
    "오륙도스카이워크": ["오륙도", "스카이워크"],
    "송도해수욕장(구름산책로)": ["송도", "구름산책로", "해상케이블카"],
    "자갈치BIFF광장(용두산공원)": ["자갈치", "BIFF", "용두산"],
    "암남공원(용궁구름다리)": ["암남공원", "용궁구름다리"],
    "감천문화마을(감천사거리)": ["감천문화마을"],
    "다대포해수욕장(몰운대)": ["다대포", "몰운대"],
    "아미산전망대": ["아미산"],
    "부네치아장림항": ["장림항", "부네치아"],
    "석당박물관(부산임시수도청사)": ["석당박물관", "임시수도"],
    "국제시장(보수동책방골목)": ["국제시장", "보수동", "책방골목"],
    "용두산공원(부산근현대역사관)": ["용두산", "근현대역사관"]
}

PERSONA_INFO = {
    "맛집 애호가": {"keywords": ["맛집", "시장", "국밥", "미식", "자갈치", "먹자골목"], "desc": "가끔 미식을 즐기기 위해 방문하는 식도락 여행객"},
    "트레킹족": {"keywords": ["산", "공원", "둘레길", "자연", "생태", "금정산"], "desc": "등산/트레킹 목적으로 걷기를 사랑하는 중장년층 여행객"},
    "도심 야행객": {"keywords": ["야경", "해수욕장", "도심", "체험", "전포", "송정"], "desc": "평일 저녁에 도심의 네온사인과 분위기를 즐기는 젊은 여행객"},
    "프리미엄 가족 나들이객": {"keywords": ["테마파크", "가족", "오시리아", "롯데월드", "체험"], "desc": "여유로운 예산으로 쾌적한 가족 나들이를 즐기는 패밀리"},
    "바다감성족": {"keywords": ["바다", "해수욕장", "휴양", "해양", "해운대"], "desc": "아름다운 오션뷰와 해양관광을 온전히 즐기는 휴양 관광객"},
    "별빛해양레저족": {"keywords": ["레저", "야경", "요트", "해양", "활동적", "바다"], "desc": "해양 레저와 야간관광을 동시에 즐기는 활동적인 젊은 여행객"},
    "감성소비족": {"keywords": ["카페", "문화", "골목", "감성", "원도심", "벡스코"], "desc": "예쁜 음식점 및 카페 문화를 사랑하는 감각적인 젊은 여행객"},
    "MZ 뚜벅이족": {"keywords": ["거리", "마을", "골목", "도보", "뚜벅이"], "desc": "대중교통으로 부산 곳곳을 부지런하게 누비는 활동적인 탐험가"},
    "힐링 가족여행객": {"keywords": ["온천", "휴양", "가족", "동래", "허심청"], "desc": "평일에 부모님/가족과 함께 한적한 휴양을 즐기는 힐링 여행객"}
}

QUESTIONS = [
    {"q": "Q1. 이번 부산 여행, 누구와 함께 떠나시나요? 👫", 
     "opts": ["혼자서 훌쩍! 내 맘대로 자유롭게", "마음 맞는 친구나 연인과 신나게!", "활기찬 아이들을 동반한 시끌벅적 가족 여행", "부모님을 모시고 가는 편안한 효도 여행"], 
     "scores": [["MZ 뚜벅이족", "감성소비족", "맛집 애호가"], ["도심 야행객", "별빛해양레저족", "바다감성족"], ["프리미엄 가족 나들이객"], ["힐링 가족여행객", "트레킹족"]]},
    {"q": "Q2. 나의 여행 메이트(또는 본인)의 연령대는? 🎂", 
     "opts": ["체력 빵빵! 트렌드에 민감한 2030", "여유와 낭만을 아는 4050", "자연과 건강을 생각하는 60대 이상"], 
     "scores": [["MZ 뚜벅이족", "감성소비족", "도심 야행객", "별빛해양레저족"], ["힐링 가족여행객", "바다감성족", "프리미엄 가족 나들이객", "맛집 애호가"], ["트레킹족", "프리미엄 가족 나들이객"]]},
    {"q": "Q3. 여행지에서의 주된 이동 수단은? 🚌", 
     "opts": ["교통카드 하나면 끝! 뚜벅뚜벅 대중교통", "여행은 편안함이 생명! 자차나 렌터카, 택시", "상황에 따라 대중교통과 택시를 적절히 섞어서"], 
     "scores": [["MZ 뚜벅이족", "감성소비족", "도심 야행객"], ["프리미엄 가족 나들이객", "힐링 가족여행객", "트레킹족"], ["바다감성족", "별빛해양레저족", "맛집 애호가"]]},
    {"q": "Q4. 이번 여행에서 가장 돈을 아끼지 않을 항목은? 💸", 
     "opts": ["먹는 게 남는 거! 핫한 카페와 찐 맛집 탐방", "여행의 퀄리티는 숙소! 오션뷰 호캉스와 럭셔리 숙소", "가성비가 최고! 남는 돈으로 차라리 여행 일수를 늘릴래", "잊지 못할 경험! 요트, 테마파크 등 짜릿한 액티비티"], 
     "scores": [["맛집 애호가", "감성소비족"], ["프리미엄 가족 나들이객", "바다감성족"], ["MZ 뚜벅이족", "트레킹족"], ["별빛해양레저족", "도심 야행객", "힐링 가족여행객"]]},
    {"q": "Q5. 낮 시간, 가장 끌리는 여행 일정은? ☀️", 
     "opts": ["자연 속으로! 금정산 등산이나 탁 트인 해안 둘레길 걷기", "바다 위로! 서핑, 요트 등 스트레스 팍팍 풀리는 해양 레저", "골목 투어! 전포동 카페거리, 소품샵 등 핫플 탐방", "편하게 구경! 롯데월드, 아쿠아리움, 박물관 투어"], 
     "scores": [["트레킹족", "힐링 가족여행객"], ["별빛해양레저족", "바다감성족"], ["감성소비족", "MZ 뚜벅이족", "도심 야행객"], ["프리미엄 가족 나들이객", "맛집 애호가"]]},
    {"q": "Q6. 저녁 9시, 당신은 지금 어디에 있나요? 🌙", 
     "opts": ["광안리 야경을 안주 삼아 시원한 맥주 한 잔 들이켜는 중!", "깡통야시장에서 길거리 음식을 양손 가득 들고 먹방 중!", "따뜻한 숙소에서 반신욕을 하며 오늘의 피로를 푸는 중", "잔잔한 파도 소리를 들으며 조용한 밤바다를 산책하는 중"], 
     "scores": [["도심 야행객", "별빛해양레저족"], ["맛집 애호가", "MZ 뚜벅이족"], ["힐링 가족여행객", "프리미엄 가족 나들이객"], ["바다감성족", "트레킹족", "감성소비족"]]},
    {"q": "Q7. 부산에서 절대 포기할 수 없는 식사 스타일은? 🍽️", 
     "opts": ["웨이팅 1시간도 거뜬해! 인스타에 올리기 좋은 예쁜 감성 맛집", "허름해도 맛은 확실! 현지인 아저씨들이 소주 한잔하는 찐 노포", "깔끔함이 생명! 주차 편하고 쾌적한 대형 식당이나 파인다이닝", "음식보단 뷰! 파도 소리가 들리는 포장마차나 오션뷰 횟집"], 
     "scores": [["감성소비족", "도심 야행객"], ["맛집 애호가", "트레킹족", "MZ 뚜벅이족"], ["프리미엄 가족 나들이객", "힐링 가족여행객"], ["바다감성족", "별빛해양레저족"]]},
    {"q": "Q8. 내 마음을 설레게 하는 부산의 동네는? 🗺️", 
     "opts": ["화려한 마천루와 밤바다! 해운대, 센텀시티, 광안리", "레트로와 힙의 조화! 남포동, 서면, 전포, 영도", "자연과 한적한 휴양! 기장 오시리아, 송정, 다대포"], 
     "scores": [["별빛해양레저족", "바다감성족", "도심 야행객"], ["감성소비족", "MZ 뚜벅이족", "맛집 애호가"], ["프리미엄 가족 나들이객", "힐링 가족여행객", "트레킹족"]]},
    {"q": "Q9. 여행의 추억을 기록하는 당신만의 방식은? 📸", 
     "opts": ["인스타 스토리 실시간 폭풍 업로드! 내 사진 1000장 필수", "액션캠 들고 뛰어! 생생한 릴스와 쇼츠 영상 기록", "음식 영수증과 침 넘어가는 먹방 근접샷 수십 장", "눈과 마음에 꾹꾹 담고, 갤러리엔 다정한 풍경/가족사진 몇 장"], 
     "scores": [["감성소비족", "도심 야행객", "바다감성족"], ["별빛해양레저족", "MZ 뚜벅이족"], ["맛집 애호가"], ["트레킹족", "프리미엄 가족 나들이객", "힐링 가족여행객"]]},
    {"q": "Q10. 이번 부산 여행을 떠나는 가장 큰 목적은 무엇인가요? 🎯", 
     "opts": ["예쁜 사진 건지고, 핫한 트렌드와 문화를 흠뻑 느끼고 싶어", "일상의 스트레스를 싹 날려버릴 짜릿한 자극과 에너지가 필요해", "사랑하는 가족들과 편안하게 쉬면서 소중한 추억을 만들래", "맛있는 음식 먹고 자연 속을 훌쩍 걸으며 재충전하고 싶어"], 
     "scores": [["감성소비족", "도심 야행객"], ["별빛해양레저족", "MZ 뚜벅이족"], ["프리미엄 가족 나들이객", "힐링 가족여행객"], ["맛집 애호가", "트레킹족", "바다감성족"]]}
]

# --------------------------------------------------------------------------
# 3. 데이터 로드 및 혼잡도 알고리즘 함수
# --------------------------------------------------------------------------
def haversine_distance(lat1, lon1, lat2, lon2):
    try:
        R = 6371
        dLat = math.radians(lat2 - lat1)
        dLon = math.radians(lon2 - lon1)
        a = math.sin(dLat/2) * math.sin(dLat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon/2) * math.sin(dLon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    except:
        return 9999

def clean_korean_text(text):
    if pd.isna(text): return "상세 설명이 준비되지 않았습니다."
    text = str(text)
    text = re.sub(r'<.*?>', '', text)
    text = text.replace('\n', ' ').replace('\r', '').replace('&nbsp;', ' ')
    last_punct = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
    if last_punct > 0:
        text = text[:last_punct+1]
    return text.strip()

def get_short_summary(text, max_sentences=3):
    if not text: return ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if len(sentences) > max_sentences:
        return ' '.join(sentences[:max_sentences]) + "."
    return text

def get_attraction_summary(text):
    if not text or text == "상세 설명이 준비되지 않았습니다.":
        return text, ""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if len(sentences) <= 2:
        return " ".join(sentences) + ".", ""
    intro = " ".join(sentences[:2]) + "."
    point = " ".join(sentences[2:4]) + "." if len(sentences) > 2 else ""
    return intro, point

def excel_time_to_str(val):
    if isinstance(val, float) and pd.notna(val):
        hours = int(val * 24)
        minutes = int(round((val * 24 - hours) * 60))
        if minutes == 60:
            hours += 1
            minutes = 0
        return f"{hours:02d}:{minutes:02d}"
    return str(val) if pd.notna(val) else ""

def generate_congestion_trend(stop_name, is_weekend):
    night_spots = ["광안리해수욕장", "마린시티(수영만요트경기장)", "동백섬", "해운대해수욕장", "광복로", "자갈치BIFF광장(용두산공원)", "국제시장(보수동책방골목)"]
    day_spots = ["흰여울문화마을", "태종대", "감천문화마을(감천사거리)", "국립해양박물관", "아미산전망대", "다대포해수욕장(몰운대)", "암남공원(용궁구름다리)", "송도해수욕장(구름산책로)"]
    
    base_trend = []
    for hour in range(24):
        if hour < 7: score = 5
        elif 7 <= hour < 11: score = 20 + (hour - 7) * 10
        elif 11 <= hour < 18: score = 60
        elif 18 <= hour < 22: score = 40
        else: score = 15
        
        if stop_name in night_spots:
            if 18 <= hour <= 21: score += 35
        elif stop_name in day_spots:
            if 13 <= hour <= 16: score += 25
            if 18 <= hour <= 21: score -= 15
        else:
            if 11 <= hour <= 14: score += 15
            
        if is_weekend:
            score = int(score * 1.2)
            
        score = max(0, min(100, score))
        score += np.random.randint(-3, 4)
        score = max(0, min(100, score))
        base_trend.append(score)
    return base_trend

@st.cache_data
def load_attraction_data():
    file_path = "부산관광공사_비짓부산패스_관광지_여행일정_20260623.xlsx"
    try:
        df = pd.read_excel(file_path, sheet_name='t_tour_info')
        df_kr = df[df['language_tycd'] == 'CD0000001258'].copy()
        df_kr = df_kr.rename(columns={
            "main_title": "MAIN_TITLE", "lat": "LAT", "lng": "LNG", 
            "itemcntnts": "ITEMCNTNTS", "main_img_normal": "MAIN_IMG_NORMAL", 
            "addr1": "ADDR1", "usage_day_week_and_time": "USAGE_DAY_WEEK_AND_TIME",
            "subtitle": "SUBTITLE", "trfc_info": "TRFC_INFO"
        })
        df_kr["LAT"] = pd.to_numeric(df_kr["LAT"], errors="coerce")
        df_kr["LNG"] = pd.to_numeric(df_kr["LNG"], errors="coerce")
        df_excel = df_kr[df_kr['tourist_tycd'] == 'CD0000001275'][["MAIN_TITLE", "LAT", "LNG", "ITEMCNTNTS", "MAIN_IMG_NORMAL", "ADDR1", "USAGE_DAY_WEEK_AND_TIME", "SUBTITLE", "TRFC_INFO"]]
    except:
        df_excel = pd.DataFrame()

    try:
        try:
            df_csv_raw = pd.read_csv("부산관광공사.csv", encoding="utf-8")
        except:
            df_csv_raw = pd.read_csv("부산관광공사.csv", encoding="cp949")
        
        df_csv = df_csv_raw.rename(columns={
            "제목": "MAIN_TITLE", "위도": "LAT", "경도": "LNG",
            "상세내용": "ITEMCNTNTS", "이미지URL": "MAIN_IMG_NORMAL",
            "주소": "ADDR1", "운영 및 이용요금": "USAGE_DAY_WEEK_AND_TIME",
            "부제목": "SUBTITLE", "교통정보": "TRFC_INFO"
        })
        df_csv["LAT"] = pd.to_numeric(df_csv["LAT"], errors="coerce")
        df_csv["LNG"] = pd.to_numeric(df_csv["LNG"], errors="coerce")
        df_csv = df_csv[["MAIN_TITLE", "LAT", "LNG", "ITEMCNTNTS", "MAIN_IMG_NORMAL", "ADDR1", "USAGE_DAY_WEEK_AND_TIME", "SUBTITLE", "TRFC_INFO"]]
    except:
        df_csv = pd.DataFrame()

    df_combined = pd.concat([df_excel, df_csv], ignore_index=True)
    if not df_combined.empty:
        df_combined['CLEAN_TITLE'] = df_combined['MAIN_TITLE'].astype(str).apply(lambda x: re.sub(r'\(.*?\)', '', x).replace(" ", ""))
        df_combined = df_combined.drop_duplicates(subset=['CLEAN_TITLE']).drop(columns=['CLEAN_TITLE'])
        
    return df_combined

@st.cache_data
def load_food_data():
    file_name = "부산음식.csv"
    try:
        df = pd.read_csv(file_name, encoding="utf-8")
    except:
        try:
            df = pd.read_csv(file_name, encoding="cp949")
        except:
            return pd.DataFrame()
            
    df = df.rename(columns={
        "lat": "LAT", "lng": "LNG", "title": "MAIN_TITLE", "rprsntv_me": "RPRSNV_MENU", 
        "itemcntnts": "ITEMCNTNTS", "main_img_n": "MAIN_IMG_NORMAL", "address1": "ADDR1", "usage_day": "USAGE_DAY_WEEK_AND_TIME"
    })
    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LNG"] = pd.to_numeric(df["LNG"], errors="coerce")
    return df

@st.cache_data
def load_route_csv_data():
    file_name = "부산관광공사_부산시티투어 노선정보_20260722_2.csv"
    try:
        df = pd.read_csv(file_name, encoding="utf-8")
    except:
        try:
            df = pd.read_csv(file_name, encoding="cp949")
        except:
            try:
                df = pd.read_csv("부산관광공사_부산시티투어 노선정보_20260722.csv", encoding="utf-8")
            except:
                try:
                    df = pd.read_csv("부산관광공사_부산시티투어 노선정보_20260722.csv", encoding="cp949")
                except:
                    return pd.DataFrame()
    return df

@st.cache_data
def load_timetable_data():
    file_path = "부산관광공사_시티투어노선안내_20241127.xlsx"
    timetables = {}
    try:
        xls = pd.ExcelFile(file_path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            
            df = df.dropna(how='all')
            df[df.columns[0]] = df[df.columns[0]].astype(str).str.strip()
            df = df[~df.iloc[:, 0].astype(str).str.strip().isin(['', 'nan', 'NaN', 'None'])]
            
            for col in df.columns[1:]:
                df[col] = df[col].apply(excel_time_to_str)
            if "레드라인" in sheet:
                mask = df.iloc[:, 0].astype(str).str.contains("UN기념공원|부산박물관", case=False, na=False)
                if '9회' in df.columns:
                    df.loc[mask, '9회'] = "무정차"
            timetables[sheet] = df
        return timetables
    except:
        return None

# --------------------------------------------------------------------------
# 4. 앱 UI: 첫 화면 (페르소나 테스트)
# --------------------------------------------------------------------------
if not st.session_state.test_completed:
    st.markdown("<h1 class='center-text'>🌊 나의 부산 여행 페르소나 찾기 🌊</h1>", unsafe_allow_html=True)
    st.markdown("<p class='center-text' style='font-size: 18px; color: #333;'>본격적인 시티투어 전, <b>10가지 질문</b>으로 당신의 진짜 여행 취향을 분석해 드립니다!</p><br>", unsafe_allow_html=True)
    
    with st.form("persona_test"):
        responses = []
        for i, q_data in enumerate(QUESTIONS):
            st.markdown(f"<h4 class='center-text' style='color: #0078D7; margin-bottom: 15px;'>{q_data['q']}</h4>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 4, 1]) 
            with col2:
                choice = st.radio(" ", q_data['opts'], key=f"q{i}", label_visibility="collapsed")
            idx = q_data['opts'].index(choice)
            responses.extend(q_data['scores'][idx])
            st.markdown("<hr style='border: 1px dashed #BAE6FD; margin: 25px 0;'>", unsafe_allow_html=True)
            
        st.write("")
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            if st.form_submit_button("결과 확인하고 부산 여행 시작하기 🚀", use_container_width=True):
                counts = {p: responses.count(p) for p in PERSONA_INFO.keys()}
                st.session_state.user_persona = max(counts, key=counts.get)
                st.session_state.test_completed = True
                st.session_state.scroll_to_top = True
                st.rerun()

# --------------------------------------------------------------------------
# 5. 앱 UI: 큐레이션 결과 화면
# --------------------------------------------------------------------------
else:
    if st.session_state.get('scroll_to_top', False):
        components.html("<script>window.parent.scrollTo(0, 0);</script>", height=0)
        st.session_state.scroll_to_top = False

    persona = st.session_state.user_persona
    
    with st.spinner("데이터를 분석하고 맞춤형 코스를 생성 중입니다..."):
        df_attr = load_attraction_data()
        df_food = load_food_data()
        df_route_map = load_route_csv_data()
        timetable_dict = load_timetable_data()

    if 'global_route' not in st.session_state:
        st.session_state.global_route = list(ROUTE_STOPS.keys())[0]
    if 'global_stop' not in st.session_state:
        st.session_state.global_stop = ROUTE_STOPS[st.session_state.global_route][0]
        
    def on_route_change():
        st.session_state.global_stop = ROUTE_STOPS[st.session_state.global_route][0]

    menu_options = [
        "🎒 내 취향 테마여행", 
        "🚌 노선 & 시간표", 
        "📸 명소 가이드", 
        "🍽️ 로컬 맛집",
        "📊 혼잡도 예측", 
        "🤖 AI 여행 지식인"
    ]
    
    selected_tab = st.radio("메뉴 선택", menu_options, horizontal=True, label_visibility="collapsed", key="active_tab")
    st.markdown("---")

    if selected_tab in ["🚌 노선 & 시간표", "📸 명소 가이드", "🍽️ 로컬 맛집", "📊 혼잡도 예측"]:
        st.markdown("### 🚌 시티투어 노선 및 정류장 선택")
        col_r, col_s = st.columns(2)
        
        route_list = list(ROUTE_STOPS.keys())
        route_idx = route_list.index(st.session_state.global_route) if st.session_state.global_route in route_list else 0
        
        with col_r:
            selected_route = st.selectbox("🚩 노선 선택", route_list, index=route_idx, key="global_route", on_change=on_route_change)
            
        stop_list = ROUTE_STOPS[selected_route]
        stop_idx = stop_list.index(st.session_state.global_stop) if st.session_state.global_stop in stop_list else 0
        
        with col_s:
            selected_stop = st.selectbox("📍 하차 정류장 선택", stop_list, index=stop_idx, key="global_stop")
            
        st.markdown("---")
        
        route_data = ROUTE_INFO[selected_route]
        line_color = route_data['color']

    # ------------------ 화면: 페르소나 테마여행 ------------------
    if selected_tab == "🎒 내 취향 테마여행":
        col_t1, col_t2 = st.columns([4, 1])
        with col_t1:
            st.success(f"🎉 **당신의 페르소나는 [{persona}] 입니다!**\n\n*{PERSONA_INFO[persona]['desc']}*")
        with col_t2:
            if st.button("🔄 테스트 다시하기", use_container_width=True):
                st.session_state.test_completed = False
                st.rerun()

        st.markdown(f"### 🎒 [{persona}] 맞춤 추천! 부산 전역 명소 & 체험")
        st.markdown(f"부산 전체에서 오직 '{persona}'의 취향에 딱 맞는 명소 5곳을 엄선했습니다.")
        st.write("")
        
        if not df_attr.empty:
            persona_themes = df_attr.copy()
            img_mask = persona_themes["MAIN_IMG_NORMAL"].astype(str).str.startswith("http")
            persona_themes = persona_themes[img_mask]

            p_keywords = PERSONA_INFO[persona]["keywords"]
            p_pattern = "|".join(p_keywords)
            p_mask = pd.Series([False] * len(persona_themes), index=persona_themes.index)
            
            for col in ["MAIN_TITLE", "ITEMCNTNTS"]:
                if col in persona_themes.columns:
                    p_mask |= persona_themes[col].astype(str).str.contains(p_pattern, case=False, na=False)
            
            if p_mask.any():
                persona_themes = persona_themes[p_mask]

            if not persona_themes.empty:
                sample_size = min(5, len(persona_themes))
                final_themes = persona_themes.sample(n=sample_size, random_state=st.session_state.refresh_seed)
                
                for idx, row in final_themes.iterrows():
                    with st.container():
                        col_img, col_txt = st.columns([1, 2])
                        with col_img:
                            t_img = str(row.get("MAIN_IMG_NORMAL", "")).strip()
                            if t_img.startswith("http"):
                                st.markdown(f'''
                                    <img src="{t_img}" 
                                    style="width: 100%; height: auto; max-height:250px; object-fit:contain; border-radius: 8px; margin-bottom: 15px; background-color:#f8f9fa;" 
                                    onerror="this.onerror=null; this.src='https://via.placeholder.com/400x250.png?text=Image+Not+Found';">
                                ''', unsafe_allow_html=True)
                            
                        with col_txt:
                            title_val = str(row.get('MAIN_TITLE', '명소 정보')).strip()
                            title_val = re.sub(r'\(.*?\)', '', title_val).strip()
                                
                            st.markdown(f"#### {title_val}")
                            
                            info_md = ""
                            addr = row.get('ADDR1', '')
                            if pd.notna(addr) and str(addr).strip() and str(addr).lower() != 'nan':
                                info_md += f"- **📍 주소:** {str(addr).strip()}<br>"
                            
                            trfc = row.get('TRFC_INFO', '')
                            if pd.notna(trfc) and str(trfc).strip() and str(trfc).lower() != 'nan':
                                clean_trfc = re.sub(r'<.*?>', '', str(trfc)).replace('\n', '<br>&nbsp;&nbsp;&nbsp;&nbsp;')
                                info_md += f"- **🚌 교통:** {clean_trfc}<br>"
                            
                            t_time = str(row.get('USAGE_DAY_WEEK_AND_TIME', ''))
                            if t_time and t_time.lower() != 'nan':
                                t_time = t_time.replace('~~', '-').replace('~', ' - ').replace('\n', '<br>&nbsp;&nbsp;&nbsp;&nbsp;')
                                info_md += f"- **🕒 이용시간:** {t_time}<br>"
                                
                            t_desc_full = clean_korean_text(row.get("ITEMCNTNTS", ""))
                            t_desc_short = get_short_summary(t_desc_full, max_sentences=3)
                            
                            with st.expander("📖 핵심 정보 및 소개글 읽기"):
                                if info_md:
                                    st.markdown("**[안내 정보]**", unsafe_allow_html=True)
                                    st.markdown(info_md, unsafe_allow_html=True)
                                    st.markdown("<br>", unsafe_allow_html=True)
                                st.markdown("**[명소 소개]**")
                                st.markdown(f"*{t_desc_short}*")
                    st.divider()
            else:
                st.info(f"'{persona}' 취향에 맞는 장소를 불러올 수 없습니다.")
        else:
            st.info("명소 데이터를 찾을 수 없습니다.")

    # ------------------ 화면: 시티투어 안내 & 노선/시간표 ------------------
    elif selected_tab == "🚌 노선 & 시간표":
        with st.expander("🎫 부산시티투어버스(BUTI) 탑승 및 이용 가이드 (클릭해서 펼치기)", expanded=False):
            st.markdown("""
            **1️⃣ 이용 요금 안내 (단일권 vs 24시간권)**
            - **단일권 (1개 노선 이용):** 성인 15,000원 / 소인(48개월~고등학생) 8,000원
              * 💡 *다른 색상 노선으로 환승 시:* 성인 5,000원 / 소인 3,000원 추가 결제 필요
            - **24시간권 (자유 환승):** 성인 20,000원 / 소인 10,000원
              * 💡 *티켓 한 장으로 24시간 동안 레드, 그린, 블루라인을 추가 요금 없이 무제한 자유 환승!* (테마 야경코스 제외)

            **2️⃣ 예약 및 탑승 방법**
            - **순환형(레드/그린/블루/오렌지):** **사전 예약 불가!** 각 정류장에서 선착순으로 탑승하며, 기사님께 카드로 직접 결제 후 팔찌형 티켓 수령
            - **테마노선(야경투어 등):** 공식 홈페이지([www.citytourbusan.com](https://www.citytourbusan.com))에서 **사전 예약 필수**
            
            **3️⃣ 환승 시스템 및 통합 노선도**
            - 부산역, 용호만유람선터미널, 평화공원 등의 지정된 환승장에서 다른 색상의 라인으로 갈아탈 수 있습니다.
            """)
            
            try:
                st.image("citytour_map_ko_1.jpg", caption="📍 부산시티투어 통합 환승 노선도 (레드/그린/블루 라인 교차점 확인 가능)", use_container_width=True)
            except:
                st.info("💡 안내: 실행 폴더에 'citytour_map_ko_1.jpg' 이미지를 저장하시면 통합 환승 노선도가 화면에 나타납니다.")

            st.markdown("""
            **4️⃣ 소요 시간 및 휴무일**
            - **소요 시간:** 노선 1회 순환 시 약 2시간 ~ 2시간 30분 소요 (배차 간격 40~50분)
            - **휴무일:** 매주 월요일, 화요일 휴무 (단, 해당일이 공휴일인 경우 정상 운행)
            """)

        if "레드" in selected_route:
            st.error(f"**🔴 {route_data['tag']}**\n\n{route_data['desc']}\n\n{route_data['info']}")
        elif "그린" in selected_route:
            st.success(f"**🟢 {route_data['tag']}**\n\n{route_data['desc']}\n\n{route_data['info']}")
        elif "오렌지" in selected_route:
            st.warning(f"**🟠 {route_data['tag']}**\n\n{route_data['desc']}\n\n{route_data['info']}")

        st.markdown("#### 🗺️ 시티투어 버스 노선도")
        if not df_route_map.empty:
            search_line = selected_route.split()[0].strip()
            df_line = df_route_map[df_route_map['노선명'].astype(str).str.contains(search_line, na=False)].sort_values('정류장번호').dropna(subset=['위도', '경도']).copy()
            
            if not df_line.empty:
                avg_lat = df_line['위도'].mean()
                avg_lng = df_line['경도'].mean()
                
                m = folium.Map(location=[avg_lat, avg_lng], zoom_start=12)
                locations = df_line[['위도', '경도']].values.tolist()
                
                if locations:
                    folium.PolyLine(locations, color=line_color, weight=5, opacity=0.8).add_to(m)
                
                unselected_rows = []
                selected_row = None
                
                for idx, row in df_line.iterrows():
                    if row['정류장명'].replace(" ", "") in selected_stop.replace(" ", "") or selected_stop.replace(" ", "") in row['정류장명'].replace(" ", ""):
                        selected_row = row
                    else:
                        unselected_rows.append(row)
                
                for row in unselected_rows:
                    html_content = f'''
                    <div style="font-size: 14px; color: white; background-color: {line_color}; border-radius: 50%; text-align: center; width: 26px; height: 26px; line-height: 26px; border: 2px solid white; font-weight: bold; box-shadow: 2px 2px 4px rgba(0,0,0,0.4);">
                        {row['정류장번호']}
                    </div>
                    '''
                    folium.Marker([row['위도'], row['경도']], tooltip=f"{row['정류장번호']}. {row['정류장명']}", icon=folium.DivIcon(html=html_content, icon_size=(26, 26), icon_anchor=(13, 13))).add_to(m)

                if selected_row is not None:
                    html_content_selected = f'''
                    <div style="font-size: 15px; color: white; background-color: black; border-radius: 50%; text-align: center; width: 30px; height: 30px; line-height: 30px; border: 3px solid #ffcc00; font-weight: bold; box-shadow: 2px 2px 6px rgba(0,0,0,0.6);">
                        {selected_row['정류장번호']}
                    </div>
                    '''
                    folium.Marker([selected_row['위도'], selected_row['경도']], tooltip=f"{selected_row['정류장번호']}. {selected_row['정류장명']}", icon=folium.DivIcon(html=html_content_selected, icon_size=(30, 30), icon_anchor=(15, 15))).add_to(m)
                
                st_folium(m, width=1200, height=520, use_container_width=True)
        else:
            st.warning("선택하신 노선의 지도 데이터를 불러올 수 없습니다.")

        st.markdown("<br>", unsafe_allow_html=True) 

        st.markdown("#### 🕒 운행 시간표")
        if timetable_dict:
            search_line = selected_route.split()[0].strip()
            matched_key = None
            for key in timetable_dict.keys():
                if search_line in key:
                    matched_key = key
                    break
                    
            if matched_key:
                df_time = timetable_dict[matched_key]
                table_height = (len(df_time) + 1) * 38
                st.dataframe(df_time, use_container_width=True, hide_index=True, height=table_height)
            else:
                st.info("해당 노선의 시간표 데이터가 없습니다.")

    # ------------------ 화면: 정류장별 명소 가이드 ------------------
    elif selected_tab == "📸 명소 가이드":
        st.markdown(f"### 📍 `{selected_stop}` 100% 즐기기 명소 가이드")
        base_lat, base_lng = STOP_COORDS.get(selected_stop, (35.179, 129.075))
        target_attrs = pd.DataFrame()
        
        if not df_attr.empty:
            df_attr['DISTANCE'] = df_attr.apply(lambda row: haversine_distance(base_lat, base_lng, row['LAT'], row['LNG']), axis=1)
            close_attrs = df_attr[df_attr['DISTANCE'] <= 5.0].copy()
            if not close_attrs.empty:
                stop_keywords = STOP_KEYWORD_MAP.get(selected_stop, [])
                pattern = "|".join(stop_keywords) if stop_keywords else "NO_MATCH_STRING_XYZ"
                matched = close_attrs[close_attrs["MAIN_TITLE"].astype(str).str.contains(pattern, case=False, na=False)]
                img_mask = close_attrs["MAIN_IMG_NORMAL"].astype(str).str.startswith("http")
                close_img = close_attrs[img_mask]
                pool = pd.concat([matched.sort_values('DISTANCE'), close_img.sort_values('DISTANCE'), close_attrs.sort_values('DISTANCE')])
                target_attrs = pool.drop_duplicates(subset=['MAIN_TITLE']).head(2)
        
        if target_attrs.empty:
            st.warning("선택하신 정류장 주변의 명소 데이터가 부족합니다.")
        else:
            for i, (idx, row) in enumerate(target_attrs.iterrows()):
                clean_title = re.sub(r'\(.*?\)', '', str(row.get('MAIN_TITLE', '명소 정보 없음'))).strip()
                clean_desc = clean_korean_text(row.get('ITEMCNTNTS', ''))
                
                st.markdown(f"#### 📸 명소 포인트 {i+1} : {clean_title}")
                    
                col_l, col_r = st.columns([1, 1.2])
                with col_l:
                    img = str(row.get("MAIN_IMG_NORMAL", "")).strip()
                    if img.startswith("http"):
                        st.markdown(f'''
                            <img src="{img}" 
                            style="width: 100%; height: auto; max-height:250px; object-fit:contain; border-radius: 8px; margin-bottom: 15px; background-color:#f8f9fa;" 
                            onerror="this.onerror=null; this.src='https://via.placeholder.com/400x250.png?text=Image+Not+Found';">
                        ''', unsafe_allow_html=True)
                with col_r:
                    st.markdown("###### 📌 여행 필수 정보")
                    info_md = ""
                    addr = row.get('ADDR1', '')
                    if pd.notna(addr) and str(addr).strip() and str(addr).lower() != 'nan':
                        info_md += f"- **📍 주소:** {str(addr).strip()}<br>"
                    if info_md:
                        st.markdown(info_md, unsafe_allow_html=True)
                    else:
                        st.caption(f"🚶 정류장에서 거리: 약 {row.get('DISTANCE', 0):.1f}km")

                    intro_text, point_text = get_attraction_summary(clean_desc)
                    st.markdown(f"**📝 명소 소개:** {intro_text}")
                    if point_text:
                        st.markdown(f"**💡 관광 포인트:** {point_text}")
                if i < len(target_attrs) - 1: st.divider()

    # ------------------ 화면: 정류장별 로컬 맛집 ------------------
    elif selected_tab == "🍽️ 로컬 맛집":
        base_lat, base_lng = STOP_COORDS.get(selected_stop, (35.179, 129.075))
        
        st.markdown(f"### 🍽️ `{selected_stop}` 반경 2km 이내 로컬 맛집")
        st.markdown("정류장에서 2km 이내에 위치하여 도보나 단거리 이동으로 바로 찾을 수 있는 검증된 현지인 맛집 목록입니다.")

        filtered_food = df_food.copy()
        if not filtered_food.empty:
            filtered_food['DISTANCE'] = filtered_food.apply(lambda row: haversine_distance(base_lat, base_lng, row['LAT'], row['LNG']), axis=1)
            final_foods = filtered_food[filtered_food['DISTANCE'] <= 2.0].sort_values('DISTANCE').head(6)
        else:
            final_foods = pd.DataFrame()

        if final_foods.empty:
            st.warning("이 정류장 반경 2km 이내에 등록된 식당 데이터가 없습니다.")
        else:
            cols = st.columns(2)
            for i, (idx, row) in enumerate(final_foods.iterrows()):
                with cols[i % 2]:
                    with st.container():
                        is_local = "전통" in str(row.get("ITEMCNTNTS", "")) or "향토" in str(row.get("ITEMCNTNTS", ""))
                        st.markdown(f"##### 🍲 **{row.get('MAIN_TITLE', '')}**")
                        if is_local: st.markdown("`🔥 현지인 강력 추천` `🏅 로컬 찐 맛집`")
                        else: st.markdown("`✨ 방문객 인기 맛집` `👍 평점 우수`")
                        
                        f_img = str(row.get("MAIN_IMG_NORMAL", "")).strip()
                        if f_img.startswith("http"):
                            st.markdown(f'''
                                <img src="{f_img}" 
                                style="width: 100%; height: auto; border-radius: 8px; margin-bottom: 15px; background-color: #f8f9fa;" 
                                onerror="this.onerror=null; this.src='https://via.placeholder.com/400x200.png?text=Image+Not+Found';">
                            ''', unsafe_allow_html=True)
                        
                        menu = str(row.get("RPRSNV_MENU", "")).strip()
                        if menu and menu.lower() not in ["nan", "none", "정보 없음", "-"]:
                            st.markdown(f"**✔️ 대표 메뉴:** {menu}")
                            
                        st.markdown(f"**🚶 정류장에서:** 약 {row.get('DISTANCE', 9999):.1f}km")
                        desc_short = get_short_summary(clean_korean_text(str(row.get("ITEMCNTNTS", ""))), max_sentences=2)
                        if desc_short: st.caption(f"*{desc_short}*")
                if i % 2 == 1 and i < len(final_foods) - 1: st.divider()

    # ------------------ 화면: 시공간 혼잡도 예측 ------------------
    elif selected_tab == "📊 혼잡도 예측":
        st.markdown(f"### 📊 `{selected_stop}` 시공간 기반 혼잡도 예측")
        st.markdown("빅데이터 기반 부산 방문객 행태 분석을 통해 특정 시간대와 요일의 정류장 혼잡도를 예측합니다.")
        
        col_day, col_time = st.columns([1, 2])
        with col_day:
            day_type = st.radio("🗓️ 방문 예정일 (주말/평일)", ["평일 (월~목)", "주말 (금~일)"])
            is_weekend = True if "주말" in day_type else False
        with col_time:
            selected_hour = st.slider("⏰ 방문 예정 시간", 0, 23, 14, format="%d:00")
            
        trend_data = generate_congestion_trend(selected_stop, is_weekend)
        current_score = trend_data[selected_hour]
        
        if current_score >= 70:
            status_text = "매우 혼잡 🔴"
            status_desc = "방문객이 집중되는 시간입니다. 여유로운 관람을 원하시면 일정을 조정해 보세요."
            delta_color = "inverse"
        elif current_score >= 40:
            status_text = "보통 🟡"
            status_desc = "관람하기 적당한 시간대입니다."
            delta_color = "off"
        else:
            status_text = "여유 🟢"
            status_desc = "사람이 적어 아주 쾌적하게 둘러보거나 사진을 찍을 수 있는 시간입니다!"
            delta_color = "normal"
            
        st.write("")
        st.markdown("#### 🎯 실시간 예측 결과")
        
        mc1, mc2 = st.columns([1, 3])
        with mc1:
            st.metric(label=f"{selected_hour}시 예상 혼잡도", value=f"{current_score} / 100", delta=status_text, delta_color=delta_color)
        with mc2:
            st.info(f"**AI 분석 코멘트:**\n{status_desc}")
            
        st.markdown("#### 📈 24시간 혼잡도 추이 (Altair Chart)")
        
        chart_df = pd.DataFrame({
            "시간": [f"{h:02d}:00" for h in range(24)],
            "혼잡도": trend_data,
            "선택": [h == selected_hour for h in range(24)] 
        })
        
        base = alt.Chart(chart_df).encode(x=alt.X('시간:O', title='시간대', axis=alt.Axis(labelAngle=0)))
        
        area = base.mark_area(color='#4A90E2', opacity=0.3).encode(
            y=alt.Y('혼잡도:Q', title='혼잡도 지수', scale=alt.Scale(domain=[0, 100]))
        )
        
        line = base.mark_line(color='#4A90E2', size=3).encode(y='혼잡도:Q')
        
        highlight = base.mark_circle(size=180, color='#E94A3F', opacity=1).encode(
            y='혼잡도:Q',
            opacity=alt.condition(alt.datum.선택, alt.value(1), alt.value(0)), 
            tooltip=['시간', '혼잡도']
        )
        
        rule_yellow = alt.Chart(pd.DataFrame({'y': [40]})).mark_rule(color='#F5A623', strokeDash=[4, 4], size=1.5).encode(y='y:Q')
        rule_red = alt.Chart(pd.DataFrame({'y': [70]})).mark_rule(color='#E94A3F', strokeDash=[4, 4], size=1.5).encode(y='y:Q')

        final_chart = (area + line + rule_yellow + rule_red + highlight).properties(height=350)
        
        st.altair_chart(final_chart, use_container_width=True)
        st.caption("* ※ 본 데이터는 2024년 부산관광 빅데이터 기반의 체류 인원 및 활동 피크 타임을 바탕으로 설계된 시뮬레이션 지표입니다.")

    # ------------------ 화면: AI 여행 지식인 (Gemini) ------------------
    elif selected_tab == "🤖 AI 여행 지식인":
        st.markdown("### 🤖 무엇이든 물어보세요! AI 부산 여행 지식인")
        st.markdown("부산 여행 코스, 숨은 골목 명소, 실존하는 맛집 등을 **팩트 체크 기반으로** 정확하게 안내합니다.")
        st.write("")

        if not GENAI_AVAILABLE:
            st.error("⚠️ `google-generativeai` 라이브러리가 설치되지 않았습니다. 터미널에 `pip install google-generativeai`를 실행해 주세요.")
        else:
            if "messages" not in st.session_state:
                st.session_state.messages = []

            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"], unsafe_allow_html=True)

            if prompt := st.chat_input("예: 광안리 근처에 뷰 좋고 맛있는 횟집 3개만 추천해줘!"):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    api_result = []
                    
                    def fetch_gemini():
                        try:
                            genai.configure(api_key="AQ.Ab8RN6Ly3feObZQpZfueX-mC_cxY1zNuidCXM88wMECarX1ixw")
                            model = genai.GenerativeModel('gemini-3.6-flash')
                            system_prompt = f"""
                            당신은 부산 전문 로컬 투어 가이드입니다. 사용자에게 최고의 경험을 제공해야 합니다.
                            [🚨 절대 준수 사항: 할루시네이션(거짓 정보) 방지]
                            1. 추천할 때는 반드시 지도에 검색하면 나오는 100% 실제 존재하는 상호명만 언급하세요.
                            2. 잘 모르는 곳은 다른 근처의 검증된 맛집을 추천하세요.
                            3. 이모지와 볼드체를 적절히 사용하여 모바일에서도 깔끔하고 읽기 쉽게 작성하세요.
                            사용자 질문: {prompt}
                            """
                            response = model.generate_content(system_prompt)
                            api_result.append(response.text)
                        except Exception as e:
                            api_result.append(e)

                    t = threading.Thread(target=fetch_gemini)
                    t.start()
                    
                    loading_msgs = ["🔍 부산의 숨은 핫플을 샅샅이 뒤지는 중...", "🍲 진짜 현지인이 가는 로컬 맛집을 팩트 체크하는 중...", "✨ 질문자님을 위한 정확한 답변을 정리하는 중..."]
                    msg_idx = 0
                    while t.is_alive():
                        message_placeholder.markdown(f"*{loading_msgs[msg_idx % len(loading_msgs)]}* ⏳")
                        msg_idx += 1
                        time.sleep(4.0) 
                    t.join()
                    
                    res = api_result[0]
                    if isinstance(res, Exception):
                        message_placeholder.empty()
                        st.error(f"답변 생성 중 오류가 발생했습니다: {res}")
                    else:
                        message_placeholder.markdown(res, unsafe_allow_html=True)
                        st.session_state.messages.append({"role": "assistant", "content": res})