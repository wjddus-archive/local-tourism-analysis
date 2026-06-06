import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

# ==========================================
# 0. 앱 기본 설정 및 예외 처리
# ==========================================
st.set_page_config(
    page_title="공공데이터 분석 대시보드",
    page_icon="📊",
    layout="wide"
)

DB_FILE = "project1.db"

# 예외 처리: 데이터베이스 파일 확인 (전체 요구사항 1번)
if not os.path.exists(DB_FILE):
    st.error("데이터베이스 파일(project1.db)을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
    st.stop()


# 헬퍼 함수: DB 내 실제 존재하는 테이블 리스트 반환
def get_db_tables():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


# 헬퍼 함수: 테이블명 오타 보정 매칭
def find_matching_table(target_name):
    available_tables = get_db_tables()
    if target_name in available_tables:
        return target_name
    
    target_stripped = target_name.replace(" ", "")
    for t in available_tables:
        if t.replace(" ", "") == target_stripped:
            return t
    for t in available_tables:
        if target_stripped in t.replace(" ", "") or t.replace(" ", "") in target_stripped:
            return t
    return None


# 헬퍼 함수: 안전한 데이터 로딩 (Fallback 내장)
def load_table_safely(table_name, fallback_data_func):
    matched_table = find_matching_table(table_name)
    if not matched_table:
        return fallback_data_func(), True
        
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(f"SELECT * FROM `{matched_table}`", conn)
        return df, False
    except Exception:
        return fallback_data_func(), True
    finally:
        conn.close()


# 헬퍼 함수: 컬럼명 매칭
def find_col(columns, search_terms):
    for term in search_terms:
        for col in columns:
            clean_col = str(col).replace(" ", "").replace("·", "").replace("_", "").lower()
            clean_term = str(term).replace(" ", "").replace("·", "").replace("_", "").lower()
            if clean_term in clean_col:
                return col
    return None


# 동적 엔진 1: 행정구역(지역)이 포함된 컬럼 자동 검출
def detect_region_col(df):
    name_match = find_col(
        df.columns, 
        ["지자체", "자치단체", "지역", "시도", "개최지", "행정구역", "상권명"]
    )
    if name_match:
        return name_match
    
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().unique()
            for val in sample:
                if any(reg in str(val) for reg in [
                    "서울", "경기", "인천", "강원", "충북", "충남", 
                    "전북", "전남", "경북", "경남", "제주", "부산", 
                    "대구", "광주", "대전", "울산", "세종"
                ]):
                    return col
    
    obj_cols = df.select_dtypes(include=['object', 'string']).columns.tolist()
    return obj_cols[0] if obj_cols else df.columns[0]


# 동적 엔진 2: 년도/ID를 제외한 첫 번째 유효한 수치형 컬럼 검출
def detect_numeric_col(df):
    name_match = find_col(
        df.columns, 
        ["지표", "값", "실적", "방문", "관광객", "점수", "인원"]
    )
    if name_match:
        return name_match
    
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    for col in num_cols:
        if not any(ex in str(col).lower() for ex in ["연도", "년도", "id", "코드"]):
            return col
    return num_cols[0] if num_cols else None


# 가로 형태 데이터를 세로 형태로 변환
def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    
    region_col = detect_region_col(df)
    quarter_cols = [
        c for c in df.columns 
        if c != region_col and (
            any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."]) or 
            any(str(yr) in str(c) for yr in range(2015, 2027))
        )
    ]
    if not quarter_cols:
        quarter_cols = df.select_dtypes(include=['number']).columns.tolist()
        quarter_cols = [c for c in quarter_cols if c != region_col]
        
    df_melted = df.melt(
        id_vars=[region_col], 
        value_vars=quarter_cols, 
        var_name="분기", 
        value_name=value_name
    )
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col


# ==========================================
# Fallback 시뮬레이션용 예비 데이터 생성기
# ==========================================
def get_fallback_festival():
    return pd.DataFrame({
        "축제명": ["춘천닭갈비축제", "강경젓갈축제", "지평선축제", "머드축제"],
        "현지인방문자 유입": [32.4, 45.1, 28.7, 15.3],
        "외부방문자 유입": [67.6, 54.9, 71.3, 84.7],
        "평가지표": [85, 78, 92, 95],
        "지자체": ["강원", "충남", "전북", "충남"]
    })

def get_fallback_consume():
    return pd.DataFrame({
        "연도": [2021, 2021, 2021, 2022, 2022, 2022, 2023, 2023, 2023],
        "쇼핑업 소비액 (천원)": [15e6, 16e6, 17e6, 18e6, 19e6, 20e6, 21e6, 22e6, 23e6],
        "숙박업 소비액 (천원)": [5e6, 4e6, 6e6, 4e6, 5e6, 3e6, 4e6, 3e6, 2e6]
    })

def get_fallback_property_vacancy():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울", "경기", "인천", "부산", "대구"],
        "2022_1Q": [12.1, 14.5, 10.2, 8.5, 9.1, 11.2, 13.1, 14.0],
        "2022_2Q": [12.3, 14.8, 10.5, 8.7, 9.3, 11.5, 13.5, 14.2],
        "2022_3Q": [12.8, 15.2, 11.2, 9.0, 8.9, 12.1, 14.0, 13.8],
        "2022_4Q": [13.1, 15.9, 11.8, 9.2, 8.5, 12.4, 14.5, 13.3],
        "2024_2Q": [13.5, 16.2, 12.0, 9.5, 8.7, 12.8, 14.9, 13.1]
    })

def get_fallback_property_rent():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울", "경기", "인천", "부산", "대구"],
        "2022_1Q": [3.2, 2.5, 2.8, 5.1, 4.2, 3.8, 4.0, 3.5],
        "2022_2Q": [3.3, 2.6, 2.9, 5.2, 4.1, 3.9, 4.1, 3.4],
        "2022_3Q": [3.4, 2.7, 3.0, 5.3, 4.0, 4.1, 4.2, 3.3],
        "2022_4Q": [3.4, 2.8, 3.1, 5.4, 3.9, 4.2, 4.2, 3.3],
        "2024_2Q": [3.5, 2.8, 3.1, 5.5, 4.0, 4.3, 4.2, 3.2]
    })

def get_fallback_cost():
    return pd.DataFrame({
        "자치단체": ["강원도 춘천시", "충청남도 논산시", "전라북도 김제시"],
        "행사·축제명": ["닭갈비축제", "강경젓갈축제", "지평선축제"],
        "총비용": [1200000000, 850000000, 1400000000],
        "사업수익": [250000000, 120000000, 180000000],
        "순원가": [950000000, 730000000, 1220000000]
    })


# ==========================================
# 1. 페이지 1: 축제 현황 및 업종별 누적 소비 구조
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 시계열 소비 패턴")
    st.markdown("가로로 펼쳐진 소비 데이터 구조를 세로 구조로 정밀 가공하여 소비 동향을 관측합니다.")
    
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_consume, is_c_mock = load_table_safely("업종별소비액", get_fallback_consume)
    
    if is_f_mock or is_c_mock:
        st.sidebar.warning("⚠️ 로컬 DB 일부 누락으로 데모용 시뮬레이션 데이터를 표시하고 있습니다.")
        
    col1, col2 = st.columns(2)
    
    # 1) 축제 방문객 유입 비율 차트 (col1)
    with col1:
        st.subheader("📍 축제별 현지인 vs 외부인 비율")
        name_col = find_col(
            df_fest.columns, 
            ["축제명", "행사명", "축제", "이름"]
        ) or df_fest.columns[0]
        
        local_col = find_col(df_fest.columns, ["현지인방문자 유입", "현지인"])
        foreign_col = find_col(df_fest.columns, ["외부방문자 유입", "외부방문자"])
        
        if local_col and foreign_col:
            df_fest[local_col] = pd.to_numeric(df_fest[local_col], errors='coerce').fillna(0)
            df_fest[foreign_col] = pd.to_numeric(df_fest[foreign_col], errors='coerce').fillna(0)
            
            df_melted = df_fest.melt(
                id_vars=[name_col],
                value_vars=[local_col, foreign_col],
                var_name="방문객 구분",
                value_name="비율(%)"
            )
            
            fig1 = px.bar(
                df_melted,
                x=name_col,
                y="비율(%)",
                color="방문객 구분",
                barmode="group",
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template="plotly_white"
            )
            st.plotly_chart(fig1, use_container_width=True, key="p1_visit_chart")
        else:
            st.write("유입 비중 컬럼 검색에 실패하였습니다. 원본 형태를 표시합니다.")
            st.dataframe(df_fest.head())
            
    # 2) [에러 완벽 예방] 가로 구조를 세로 구조로 Melt 처리하여 연도별 소비 꺾은선 차트화
    with col2:
        st.subheader("📈 연도별 업종 소비 흐름 (꺾은선)")
        year_col = find_col(df_consume.columns, ["연도", "년도", "시기"]) or df_consume.columns[0]
        
        # 연도 컬럼을 제외한 모든 컬럼을 소비 업종 데이터로 분류하여 Melt 진행
        other_cols = [c for c in df_consume.columns if c != year_col]
        
        df_melted_consume = df_consume.melt(
            id_vars=[year_col],
            value_vars=other_cols,
            var_name="소비업종",
            value_name="소비액"
        )
        
        # 가독성을 높이기 위해 '소비액', '(천원)' 등 중복 수식어 정제
        df_melted_consume["소비업종"] = df_melted_consume["소비업종"].astype(str)\
            .str.replace(" 소비액", "")\
            .str.replace(" (천원)", "", regex=False)\
            .str.replace("(천원)", "", regex=False)\
            .str.strip()
            
        df_melted_consume["소비액"] = pd.to_numeric(df_melted_consume["소비액"], errors='coerce').fillna(0)
        
        # 안전한 유니크 임시 컬럼 집계
        df_sub = df_melted_consume[[year_col, "소비업종", "소비액"]].copy()
        df_sub.columns = ["_temp_year", "_temp_sector", "_temp_amount"]
        df_trend = df_sub.groupby(["_temp_year", "_temp_sector"])["_temp_amount"].sum().reset_index()
        df_trend.columns = [year_col, "소비업종", "소비액"]
        
        fig2 = px.line(
            df_trend,
            x=year_col,
            y="소비액",
            color="소비업종",
            markers=True,
            title="연도별 업종 총 소비액 변동 추이",
            labels={year_col: "연도", "소비액": "소비액(단위: 천원)", "소비업종": "업종구분"},
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True, key="p1_consume_trend_line_safe")

    # 요구사항 데이터 인사이트
    st.info("""
    **💡 데이터 분석 결과 보고**
    
    데이터 분석 결과, 다른 업종에 비해 '숙박업 소비액'의 비중이 현저히 낮게 나타납니다. 이는 관광객들이 지역에 체류하지 않고 '당일치기 관광'을 선호함을 시각적으로 보여줍니다. 결과적으로 축제가 개최되더라도 지방 관광 활성화 및 인구 소멸 대체 효과가 미미하다는 인사이트를 도출할 수 있습니다.
    """)


# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (시계열 비교 차트 보완)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제 상권(실험군)과 일반 상권(대조군)의 격차를 정적 분산 구조와 시계열 트렌드로 비교 분석합니다.")
    
    df_vac, is_v_mock = load_table_safely("임대동향 지역별 공실률 소규모 상가", get_fallback_property_vacancy)
    df_rent, is_r_mock = load_table_safely("임대동향 지역별 임대료 소규모 상가", get_fallback_property_rent)
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    df_cost, is_c_mock = load_table_safely("행사원가회계정보", get_fallback_cost)
    
    if is_v_mock or is_r_mock or is_f_mock or is_c_mock:
        st.sidebar.warning("⚠️ 로컬 DB 일부 누락으로 데모용 시뮬레이션 데이터를 표시하고 있습니다.")
        
    quarter_cols_vac = [c for c in df_vac.columns if any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."])]
    quarter_cols_vac = sorted(quarter_cols_vac)
    
    if len(quarter_cols_vac) >= 2:
        first_q = quarter_cols_vac[0]
        last_q = quarter_cols_vac[-1]
    else:
        first_q, last_q = "2022_1Q", "2024_2Q"
        
    reg_col_vac = detect_region_col(df_vac)
    reg_col_rent = detect_region_col(df_rent)
    
    # 1) 공실률 변화량 및 임대료 변화율 연산
    df_vac_calc = df_vac[[reg_col_vac, first_q, last_q]].copy()
    df_vac_calc["공실률_first"] = pd.to_numeric(df_vac_calc[first_q], errors='coerce').fillna(0)
    df_vac_calc["공실률_last"] = pd.to_numeric(df_vac_calc[last_q], errors='coerce').fillna(0)
    df_vac_calc["공실률변화량"] = df_vac_calc["공실률_last"] - df_vac_calc["공실률_first"]
    
    df_rent_calc = df_rent[[reg_col_rent, first_q, last_q]].copy()
    df_rent_calc["임대료_first"] = pd.to_numeric(df_rent_calc[first_q], errors='coerce').fillna(1e-5)
    df_rent_calc["임대료_last"] = pd.to_numeric(df_rent_calc[last_q], errors='coerce').fillna(0)
    df_rent_calc["임대료변화율"] = ((df_rent_calc["임대료_last"] - df_rent_calc["임대료_first"]) / df_rent_calc["임대료_first"]) * 100
    
    # 2) 상권 변화 데이터 통합
    df_prop = pd.merge(
        df_vac_calc[[reg_col_vac, "공실률변화량"]], 
        df_rent_calc[[reg_col_rent, "임대료변화율"]], 
        left_on=reg_col_vac, 
        right_on=reg_col_rent
    )
    df_prop["매칭키"] = df_prop[reg_col_vac].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 3) 축제 규모(외부방문자 유입) 연동
    fest_reg = detect_region_col(df_fest)
    foreign_col = find_col(df_fest.columns, ["외부방문자 유입", "외부방문자"]) or detect_numeric_col(df_fest)
    
    df_fest_clean = df_fest.copy()
    df_fest_clean[foreign_col] = pd.to_numeric(df_fest_clean[foreign_col], errors='coerce').fillna(0)
    
    df_f_sub = df_fest_clean[[fest_reg, foreign_col]].copy()
    df_f_sub.columns = ["_temp_reg", "_temp_foreign"]
    df_fest_group = df_f_sub.groupby("_temp_reg")["_temp_foreign"].mean().reset_index()
    
    df_fest_group.columns = ["지자체명", "외부방문자유입"]
    df_fest_group["매칭키"] = df_fest_group["지자체명"].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 4) 지자체 총 예산액 연동
    cost_org = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[0]
    cost_val = find_col(df_cost.columns, ["총비용"]) or df_cost.select_dtypes(include=['number']).columns[-1]
    
    df_cost_clean = df_cost.copy()
    df_cost_clean[cost_val] = pd.to_numeric(df_cost_clean[cost_val], errors='coerce').fillna(0)
    
    df_c_sub = df_cost_clean[[cost_org, cost_val]].copy()
    df_c_sub.columns = ["_temp_org", "_temp_cost"]
    df_cost_group = df_c_sub.groupby("_temp_org")["_temp_cost"].sum().reset_index()
    
    df_cost_group.columns = ["예산지자체", "예산총액(원)"]
    df_cost_group["매칭키"] = df_cost_group["예산지자체"].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 5) 종합 조인 (실험군 vs 대조군 레이블 수립)
    df_relation = pd.merge(df_prop, df_fest_group, on="매칭키", how="left")
    df_relation = pd.merge(df_relation, df_cost_group, on="매칭키", how="left")
    
    df_relation["외부방문자유입"] = df_relation["외부방문자유입"].fillna(0)
    df_relation["예산총액(원)"] = df_relation["예산총액(원)"].fillna(1e6)
    
    df_relation["상권구분"] = df_relation["지자체명"].apply(
        lambda x: "축제 상권 (실험군)" if pd.notna(x) else "일반 상권 (대조군)"
    )
    
    df_relation["점크기_방문자"] = df_relation["외부방문자유입"] * 1000
    df_relation.loc[df_relation["점크기_방문자"] < 5, "점크기_방문자"] = 8
    
    df_relation["예산(백만원)"] = df_relation["예산총액(원)"] / 1000000
    df_relation["점크기_예산"] = df_relation["예산(백만원)"] / 100
    df_relation.loc[df_relation["점크기_예산"] < 5, "점크기_예산"] = 8
    
    # ------------------------------------------
    # 차트 1번: 임대료 변화율 x 공실률 변화 산점도
    # ------------------------------------------
    st.subheader("📊 차트 1: 임대료 변화율 × 공실률 변화 사분면 매트릭스")
    st.write("1사분면(우상단: 임대료 상승 + 공실률 증가)은 임차인이 내몰리는 **젠트리피케이션 압력**이 가장 강한 위험 영역입니다.")
    
    fig1 = px.scatter(
        df_relation,
        x="임대료변화율",
        y="공실률변화량",
        size="점크기_방문자",
        color="상권구분",
        text=reg_col_vac,
        color_discrete_map={
            "축제 상권 (실험군)": "#FF4B4B",
            "일반 상권 (대조군)": "#1F77B4"
        },
        labels={
            "임대료변화율": f"임대료 변화율 (% / {first_q} ➔ {last_q})",
            "공실률변화량": f"공실률 변화량 (p.p. / {first_q} ➔ {last_q})",
            "점크기_방문자": "외부방문자 유입지수"
        },
        template="plotly_white"
    )
    fig1.add_hline(y=0, line_dash="dash", line_color="gray")
    fig1.add_vline(x=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig1, use_container_width=True, key="p2_quadrant_matrix")
    
    # ------------------------------------------
    # 차트 2번: 3차원 버블 차트 (예산 규모 통제 분석)
    # ------------------------------------------
    st.subheader("🪐 차트 2: 지자체 예산 규모를 통제한 3차원 버블 입체 분석")
    st.write("예산 규모의 고저와 무관하게, **축제 개최 여부**에 따라 상권의 변동 성격이 명확히 구획화되는 가설을 증명합니다.")
    
    fig2 = px.scatter_3d(
        df_relation,
        x="임대료변화율",
        y="공실률변화량",
        z="예산(백만원)",
        size="점크기_예산",
        color="상권구분",
        text=reg_col_vac,
        color_discrete_map={
            "축제 상권 (실험군)": "#FF4B4B",
            "일반 상권 (대조군)": "#1F77B4"
        },
        labels={
            "임대료변화율": "임대료 변화율 (%)",
            "공실률변화량": "공실률 변화량 (p.p.)",
            "예산(백만원)": "지자체 예산 규모 (백만원)",
            "상권구분": "상권 유형"
        },
        template="plotly_white"
    )
    fig2.update_layout(margin=dict(l=0, r=0, b=0, t=40))
    st.plotly_chart(fig2, use_container_width=True, key="p2_3d_bubble")

    # ------------------------------------------
    # [추가] 차트 3번: 축제 상권과 일반 상권의 분기별 실시간 동향 비교 (꺾은선)
    # ------------------------------------------
    st.subheader("📈 차트 3: 축제 유무에 따른 분기별 임대료 및 공실률 실시간 추이")
    st.write("시간의 흐름에 따라 축제 상권(실험군)과 일반 상권(대조군)의 부동산 변수가 어떻게 벌어지는지 추적합니다.")
    
    m_vac_full, r_v_col = melt_quarters(df_vac, "공실률")
    m_rent_full, r_r_col = melt_quarters(df_rent, "임대료")
    
    # 매칭용 지역 전처리 키 추가
    m_vac_full["매칭키"] = m_vac_full[r_v_col].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    m_rent_full["매칭키"] = m_rent_full[r_r_col].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 축제 데이터 병합하여 그룹명 수립
    m_vac_full = pd.merge(m_vac_full, df_fest_group[["매칭키", "지자체명"]], on="매칭키", how="left")
    m_vac_full["상권구분"] = m_vac_full["지자체명"].apply(lambda x: "축제 상권 (실험군)" if pd.notna(x) else "일반 상권 (대조군)")
    
    m_rent_full = pd.merge(m_rent_full, df_fest_group[["매칭키", "지자체명"]], on="매칭키", how="left")
    m_rent_full["상권구분"] = m_rent_full["지자체명"].apply(lambda x: "축제 상권 (실험군)" if pd.notna(x) else "일반 상권 (대조군)")
    
    # 데이터타입 숫자형 통제
    m_vac_full["공실률"] = pd.to_numeric(m_vac_full["공실률"], errors='coerce').fillna(0)
    m_rent_full["임대료"] = pd.to_numeric(m_rent_full["임대료"], errors='coerce').fillna(0)
    
    # 중복 집계 예방용 임시 맵핑 적용 연산
    v_sub = m_vac_full[["상권구분", "분기", "공실률"]].copy()
    v_sub.columns = ["_temp_group", "_temp_quarter", "_temp_vac"]
    df_vac_trend = v_sub.groupby(["_temp_group", "_temp_quarter"])["_temp_vac"].mean().reset_index()
    df_vac_trend.columns = ["상권구분", "분기", "평균공실률(%)"]
    df_vac_trend = df_vac_trend.sort_values(by="분기")
    
    r_sub = m_rent_full[["상권구분", "분기", "임대료"]].copy()
    r_sub.columns = ["_temp_group", "_temp_quarter", "_temp_rent"]
    df_rent_trend = r_sub.groupby(["_temp_group", "_temp_quarter"])["_temp_rent"].mean().reset_index()
    df_rent_trend.columns = ["상권구분", "분기", "평균임대료"]
    df_rent_trend = df_rent_trend.sort_values(by="분기")
    
    t1, t2 = st.tabs(["💰 평균 임대료 시계열 흐름", "🏚️ 평균 공실률 시계열 흐름"])
    with t1:
        fig_r_trend = px.line(
            df_rent_trend,
            x="분기",
            y="평균임대료",
            color="상권구분",
            markers=True,
            title="실험군 vs 대조군 분기별 평균 임대료 격차",
            color_discrete_map={"축제 상권 (실험군)": "#FF4B4B", "일반 상권 (대조군)": "#1F77B4"},
            template="plotly_white"
        )
        st.plotly_chart(fig_r_trend, use_container_width=True)
    with t2:
        fig_v_trend = px.line(
            df_vac_trend,
            x="분기",
            y="평균공실률(%)",
            color="상권구분",
            markers=True,
            title="실험군 vs 대조군 분기별 평균 공실률 격차",
            color_discrete_map={"축제 상권 (실험군)": "#FF4B4B", "일반 상권 (대조군)": "#1F77B4"},
            template="plotly_white"
        )
        st.plotly_chart(fig_v_trend, use_container_width=True)

    st.markdown("---")
    st.markdown("""
    **📋 상권 분석 요약**
    * **시계열 추적**: 차트 3의 추이를 통해, 일반 상권 대비 축제 상권의 임대료가 장기적으로 어떤 격차를 유발하는지 통계적으로 비교할 수 있습니다.
    """)


# ==========================================
# 3. 페이지 3: 세금 효율성 분석 및 관광 효과 (가치 효율성 ROI 지수 도입)
# ==========================================
def render_page3():
    st.title("💸 정부 예산 세금 ROI 가치 진단")
    st.markdown("축제 투입 원가(순원가) 대비 외부 유입 관광객 실적을 대조하여 세금의 실질 유치 가치를 분석합니다.")
    
    df_cost, is_c_mock = load_table_safely("행사원가회계정보", get_fallback_cost)
    df_fest, is_f_mock = load_table_safely("문화관광축제주요지표", get_fallback_festival)
    
    if is_c_mock or is_f_mock:
        st.sidebar.warning("⚠️ 로컬 DB 일부 누락으로 데모용 시뮬레이션 데이터를 표시하고 있습니다.")
        
    org_col = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[0]
    name_col = find_col(df_cost.columns, ["행사·축제명", "축제명", "행사명"]) or df_cost.columns[1]
    total_cost_col = find_col(df_cost.columns, ["총비용"]) or df_cost.columns[2]
    rev_col = find_col(df_cost.columns, ["사업수익"]) or df_cost.columns[3]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[4]
    
    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("진단할 자치단체를 선택하세요", org_list)
    
    df_sub = df_cost[df_cost[org_col] == selected_org].copy()
    
    # 숫자형 보정
    df_sub[total_cost_col] = pd.to_numeric(df_sub[total_cost_col], errors='coerce').fillna(0)
    df_sub[rev_col] = pd.to_numeric(df_sub[rev_col], errors='coerce').fillna(0)
    df_sub[net_cost_col] = pd.to_numeric(df_sub[net_cost_col], errors='coerce').fillna(0)
    
    st.subheader(f"📊 [{selected_org}] 행사 세금 환산비용 대조")
    if not df_sub.empty:
        df_sub["총비용(백만원)"] = df_sub[total_cost_col] / 1000000
        df_sub["순원가(백만원)"] = df_sub[net_cost_col] / 1000000
        
        df_melted = df_sub.melt(
            id_vars=[name_col],
            value_vars=["총비용(백만원)", "순원가(백만원)"],
            var_name="예산지표",
            value_name="금액"
        )
        
        fig = px.bar(
            df_melted,
            x=name_col,
            y="금액",
            color="예산지표",
            barmode="group",
            title="자치단체 지출 대비 순 세금부담액(순원가) 비교 (단위: 백만원)",
            labels={"금액": "예산 규모 (백만원)", name_col: "축제/행사명"},
            color_discrete_sequence=px.colors.sequential.Agsunset,
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True, key="p3_budget_bar")
        
    # ------------------------------------------
    # [인사이트 업그레이드] 세금 예산 대비 외부방문객 유치 가치(ROI) 분석
    # ------------------------------------------
    st.subheader("💡 세금 1천만 원당 외부인 관광 유입 유치 지수 (Tax ROI Index)")
    st.write("순정 세금 투입액(순원가) 대비 실제로 얼마나 유치 효과를 냈는지 환산하여 공공 가치 가성비를 종합 진단합니다.")
    
    # 지자체 키를 활용해 외부방문객 유입 매핑 진행
    fest_reg = detect_region_col(df_fest)
    foreign_col = find_col(df_fest.columns, ["외부방문자 유입", "외부방문자"]) or detect_numeric_col(df_fest)
    
    df_fest_clean = df_fest.copy()
    df_fest_clean[foreign_col] = pd.to_numeric(df_fest_clean[foreign_col], errors='coerce').fillna(0)
    
    # 예산과 결합
    df_sub["매칭키"] = df_sub[org_col].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    df_f_map = df_fest_clean[[fest_reg, foreign_col]].copy()
    df_f_map.columns = ["지자체명", "외부방문자"]
    df_f_map["매칭키"] = df_f_map["지자체명"].apply(lambda x: str(x)[:2] if pd.notna(x) else "")
    
    # 조인 수행
    df_roi = pd.merge(df_sub, df_f_map, on="매칭키", how="left")
    df_roi["외부방문자"] = df_roi["외부방문자"].fillna(0)
    
    # 효율성 지수 계산: (외부방문자 규모 / (순원가 / 10,000,000)) -> 세금 1천만원 당 방문자 지수
    df_roi["세금효율성_ROI"] = df_roi.apply(
        lambda r: (r["외부방문자"] / (r[net_cost_col] / 10000000)) if r[net_cost_col] > 0 else 0, axis=1
    )
    
    if not df_roi.empty:
        fig_roi = px.bar(
            df_roi,
            x=name_col,
            y="세금효율성_ROI",
            text_auto=".2f",
            title="축제별 세금 투입 대비 외부 유입 가치 (ROI 지수)",
            labels={"세금효율성_ROI": "세금 1천만원 당 외부 유입 지수", name_col: "축제명"},
            color="세금효율성_ROI",
            color_continuous_scale="Reds",
            template="plotly_white"
        )
        st.plotly_chart(fig_roi, use_container_width=True, key="p3_tax_roi_chart")
    else:
        st.write("진단 데이터 매칭이 부족하여 효율성 차트 생성이 연기되었습니다.")
        
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📉 세금 효율성 분석")
        st.markdown("""
        * **자원 레버리지**: 세금 효율성 ROI 지수가 높은 축제는 적은 예산 적자로 큰 외부 지출과 방문 편익을 달성한 우수 사례에 해당합니다.
        * **예산 투입 분배**: 성과가 낮은 사업의 낭비 예산을 고효율 축제로 분배해 재무 건전성을 확보해야 합니다.
        """)
    with col2:
        st.write("### ✈️ 지방 관광 대체 효과")
        st.markdown("""
        * **관광 대체**: 지방 축제 지원금은 단순 낭비가 아닌, 해외 관광 수요를 적극 흡수하여 국내 지역 경제로 선순환시키는 공공 편익을 발생시킵니다.
        * **생활인구 유도**: 정주 인구가 감소하는 지방 소도시에 외부 유입을 유도하여, 정성적인 지역 소멸 예방 및 소상공인 매출 개선 효과를 견인합니다.
        """)


# ==========================================
# 4. 메인 실행 함수 및 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    
    with st.sidebar.expander("🛠️ 실시간 DB 스키마 진단 도구"):
        st.write("실제 데이터베이스 내부 테이블 리스트:")
        tables = get_db_tables()
        if tables:
            st.code("\n".join(tables), language="text")
        else:
            st.error("테이블을 조회할 수 없거나 project1.db 파일이 누락되었습니다.")
            
    page = st.sidebar.selectbox(
        "원하는 분석 페이지를 선택하세요.",
        ["1. 축제 현황 분석", "2. 젠트리피케이션 분석", "3. 세금 효율성 분석"]
    )
    
    if page == "1. 축제 현황 분석":
        render_page1()
    elif page == "2. 젠트리피케이션 분석":
        render_page2()
    elif page == "3. 세금 효율성 분석":
        render_page3()


if __name__ == "__main__":
    main()
