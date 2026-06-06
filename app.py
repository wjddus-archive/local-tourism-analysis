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
        "업종명": ["식음료업", "쇼핑업", "숙박업", "식음료업", "쇼핑업", "숙박업", "식음료업", "쇼핑업", "숙박업"],
        "소비액": [41e6, 29e6, 5e6, 45e6, 30e6, 4.5e6, 52e6, 32e6, 4.2e6]
    })

def get_fallback_property_vacancy():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울", "경기", "인천", "부산", "대구"],
        "2022_1Q": [12.1, 14.5, 10.2, 8.5, 9.1, 11.2, 13.1, 14.0],
        "2024_2Q": [13.5, 16.2, 12.0, 9.5, 8.7, 12.8, 14.9, 13.1]
    })

def get_fallback_property_rent():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울", "경기", "인천", "부산", "대구"],
        "2022_1Q": [3.2, 2.5, 2.8, 5.1, 4.2, 3.8, 4.0, 3.5],
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
# 1. 페이지 1: 축제 현황 분석 (집계 에러 예방 완료)
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 시계열 소비 패턴")
    st.markdown("데이터베이스에 수집된 방문객 유입 비율과 연도별 업종 소비 동향을 관측합니다.")
    
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
            
    # 2) [에러 완벽 예방] 연도별 업종 소비 흐름 분석 (col2 - 꺾은선 차트)
    with col2:
        st.subheader("📈 연도별 업종 소비 흐름 (꺾은선)")
        year_col = find_col(df_consume.columns, ["연도", "년도", "시기"]) or df_consume.columns[0]
        sector_col = find_col(df_consume.columns, ["업종명", "업종", "분류"]) or df_consume.columns[1]
        amt_col = find_col(df_consume.columns, ["소비액", "금액", "매출"]) or df_consume.select_dtypes(include=['number']).columns[-1]
        
        # [에러 우회 솔루션] 임시 유니크 컬럼명으로 맵핑하여 중복 인서트 에러 방지
        df_sub = df_consume[[year_col, sector_col, amt_col]].copy()
        df_sub.columns = ["_temp_year", "_temp_sector", "_temp_amount"]
        df_sub["_temp_amount"] = pd.to_numeric(df_sub["_temp_amount"], errors='coerce').fillna(0)
        
        # 가공 진행
        df_trend = df_sub.groupby(["_temp_year", "_temp_sector"])["_temp_amount"].sum().reset_index()
        df_trend.columns = [year_col, sector_col, amt_col]
        
        fig2 = px.line(
            df_trend,
            x=year_col,
            y=amt_col,
            color=sector_col,
            markers=True,
            title="연도별 업종 총 소비액 변동 추이",
            labels={year_col: "연도", amt_col: "소비액 (원)", sector_col: "업종명"},
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True, key="p1_consume_trend_line")

    # 요구사항 데이터 인사이트
    st.info("""
    **💡 데이터 분석 결과 보고**
    
    데이터 분석 결과, 다른 업종에 비해 '숙박업 소비액'의 비중이 현저히 낮게 나타납니다. 이는 관광객들이 지역에 체류하지 않고 '당일치기 관광'을 선호함을 시각적으로 보여줍니다. 결과적으로 축제가 개최되더라도 지방 관광 활성화 및 인구 소멸 대체 효과가 미미하다는 인사이트를 도출할 수 있습니다.
    """)


# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (실험군 vs 대조군 프레임워크)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제 상권(실험군)과 일반 상권(대조군)의 분기별 격차를 4사분면 매트릭스와 3D 예산 통제 모델로 입증합니다.")
    
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
    
    # 그룹바이 전 컬럼 중복 삽입 회피 처리
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
            "점크기_방문자": "외부방문자 스케일"
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
    st.write("예산 총액을 점의 크기로 환산해 차트화한 결과입니다. 예산 규모의 고저와 무관하게, **축제 여부**에 따라 변동 성격이 명확히 구획화되는 가설을 증명합니다.")
    
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

    st.markdown("---")
    st.markdown("""
    **📋 분석 가이드**
    * **임대 변화율 분석**: X축 0선 우측은 임대료 상승 지역이며, Y축 0선 상단은 공실률 악화 구역입니다. 
    * **실험군 집중 지대**: 1사분면에 빨간 점(축제 상권)이 집중 분산되어 있을수록 외부 관광수요에 따른 상인 축출 압력이 증명됩니다.
    """)


# ==========================================
# 3. 페이지 3: 세금 효율성 분석 및 관광 효과 (인사이트 차트 탑재)
# ==========================================
def render_page3():
    st.title("💸 예산 집행 효율성 및 관광 연계 효과 진단")
    st.markdown("정부 예산 지출(순원가)이 관내 경제 진작과 관광 유인 편익에 기여한 성과를 분석합니다.")
    
    df_cost, is_c_mock = load_table_safely("행사원가회계정보", get_fallback_cost)
    
    if is_c_mock:
        st.sidebar.warning("⚠️ 로컬 DB 일부 누락으로 데모용 시뮬레이션 데이터를 표시하고 있습니다.")
        
    org_col = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[0]
    name_col = find_col(df_cost.columns, ["행사·축제명", "축제명", "행사명"]) or df_cost.columns[1]
    total_cost_col = find_col(df_cost.columns, ["총비용"]) or df_cost.columns[2]
    rev_col = find_col(df_cost.columns, ["사업수익"]) or df_cost.columns[3]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[4]
    
    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("진단할 자치단체를 선택하세요", org_list)
    
    df_sub = df_cost[df_cost[org_col] == selected_org].copy()
    
    # 문자열 숫자로 보정
    df_sub[total_cost_col] = pd.to_numeric(df_sub[total_cost_col], errors='coerce').fillna(0)
    df_sub[rev_col] = pd.to_numeric(df_sub[rev_col], errors='coerce').fillna(0)
    df_sub[net_cost_col] = pd.to_numeric(df_sub[net_cost_col], errors='coerce').fillna(0)
    
    # ------------------------------------------
    # 차트 1번: 투입 예산 규모 비교
    # ------------------------------------------
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
    # [추가] 차트 2번: 지율 자생력 vs 세금 의존도 인사이트 차트
    # ------------------------------------------
    st.subheader("💡 축제 재정 자력 구조 분석 (세금 의존도 vs 자체 보전율)")
    st.write("축제가 세금 지원에 전적으로 의존하는지, 아니면 티켓 및 수익 제휴를 통해 스스로 비용을 메꾸고 있는지 예산 건전성을 평가합니다.")
    
    if not df_sub.empty:
        # 비율 연산
        df_sub["자체자립도(%)"] = df_sub.apply(
            lambda r: (r[rev_col] / r[total_cost_col] * 100) if r[total_cost_col] > 0 else 0, axis=1
        )
        df_sub["세금의존도(%)"] = df_sub.apply(
            lambda r: (r[net_cost_col] / r[total_cost_col] * 100) if r[total_cost_col] > 0 else 0, axis=1
        )
        
        df_pct_melted = df_sub.melt(
            id_vars=[name_col],
            value_vars=["자체자립도(%)", "세금의존도(%)"],
            var_name="재정지표",
            value_name="비중(%)"
        )
        
        fig_pct = px.bar(
            df_pct_melted,
            y=name_col,
            x="비중(%)",
            color="재정지표",
            orientation='h',
            barmode="stack",
            title="축제별 재정 구성비 (누적 막대)",
            labels={"비중(%)": "비율 (%)", name_col: "축제명"},
            color_discrete_sequence=["#2CA02C", "#D62728"], # 초록(자립), 빨강(의존)
            template="plotly_white"
        )
        st.plotly_chart(fig_pct, use_container_width=True, key="p3_efficiency_percentage")
        
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📉 세금 지출 효율성 요약")
        st.markdown("""
        * **자생력 확보**: 정부 순정 예산 투입(순원가) 비중을 낮추고, 가용한 민간 연계 자립 수익 비중을 높여 세금 누수를 예방합니다.
        * **선택과 집중**: 성과 및 가성비가 높은 축제에 예산을 효율적으로 배분하는 정책 보완이 동반되어야 재정이 건전해집니다.
        """)
    with col2:
        st.write("### ✈️ 지방 관광 대체 효과")
        st.markdown("""
        * **내수 활성화**: 잘 정돈된 지방 콘텐츠는 외화 유출(해외 여행) 수요를 성공적으로 내수로 전환시키는 공공 간접 가치를 확보합니다.
        * **소멸 지역 기여**: 정주 인구가 부족해지는 지방 소도시에 외부 체류 인구를 정기적으로 공급하여, 소상공인의 실질 소득을 견인합니다.
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
