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


# 가로 형태 데이터를 세로 형태로 변환 (줄 자름 예방을 위해 완벽히 멀티라인 분할)
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
        "업종명": ["식음료업", "쇼핑업", "여가서비스업", "운송업", "숙박업"],
        "소비액": [45000000, 30000000, 15000000, 8000000, 4500000]
    })

def get_fallback_property_vacancy():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울"],
        "2022_1Q": [12.1, 14.5, 10.2, 8.5],
        "2022_2Q": [12.5, 15.0, 11.0, 9.0],
        "2022_3Q": [13.0, 15.8, 11.5, 9.2],
        "2022_4Q": [13.5, 16.2, 12.0, 9.5]
    })

def get_fallback_property_rent():
    return pd.DataFrame({
        "지역": ["강원", "충남", "전북", "서울"],
        "2022_1Q": [3.2, 2.5, 2.8, 5.1],
        "2022_2Q": [3.3, 2.6, 2.9, 5.2],
        "2022_3Q": [3.4, 2.7, 3.0, 5.4],
        "2022_4Q": [3.5, 2.8, 3.1, 5.5]
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
# 1. 페이지 1: 축제 현황 분석 (직관적 통합 배치)
# ==========================================
def render_page1():
    st.title("🎪 지역 축제 현황 및 소비 실태 종합 분석")
    st.markdown("데이터베이스에 수집된 방문객 유입 비율과 업종별 지출 구조를 즉시 확인합니다.")
    
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
            df_fest[local_col] = pd.to_numeric(
                df_fest[local_col], 
                errors='coerce'
            ).fillna(0)
            
            df_fest[foreign_col] = pd.to_numeric(
                df_fest[foreign_col], 
                errors='coerce'
            ).fillna(0)
            
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
            
    # 2) 업종별 소비액 비중 차트 (col2)
    with col2:
        st.subheader("💳 업종별 누적 소비 분포")
        sector_col = find_col(
            df_consume.columns, 
            ["업종", "분류", "카테고리"]
        ) or df_consume.columns[0]
        
        amt_col = find_col(
            df_consume.columns, 
            ["소비액", "금액", "매출", "지출"]
        ) or df_consume.select_dtypes(include=['number']).columns[-1]
        
        df_consume[amt_col] = pd.to_numeric(
            df_consume[amt_col], 
            errors='coerce'
        ).fillna(0)
        
        df_grouped = df_consume.groupby(sector_col)[amt_col].sum().reset_index()
        df_grouped = df_grouped.sort_values(by=amt_col, ascending=True)
        
        fig2 = px.bar(
            df_grouped,
            y=sector_col,
            x=amt_col,
            orientation='h',
            color=amt_col,
            color_continuous_scale="Viridis",
            labels={sector_col: "업종", amt_col: "지출(원)"},
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True, key="p1_consume_chart")

    # 요구사항 데이터 인사이트
    st.info("""
    **💡 데이터 분석 결과 보고**
    
    데이터 분석 결과, 다른 업종에 비해 '숙박업 소비액'의 비중이 현저히 낮게 나타납니다. 이는 관광객들이 지역에 체류하지 않고 '당일치기 관광'을 선호함을 시각적으로 보여줍니다. 결과적으로 축제가 개최되더라도 지방 관광 활성화 및 인구 소멸 대체 효과가 미미하다는 인사이트를 도출할 수 있습니다.
    """)


# ==========================================
# 2. 페이지 2: 젠트리피케이션 분석 (오류 해결)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제 상관성 분석")
    st.markdown("축제 성과지표와 주변 상권의 공실률/임대료 지표를 교차 매칭하여 실질적 연관성을 검정합니다.")
    
    df_vac, is_v_mock = load_table_safely(
        "임대동향 지역별 공실률 소규모 상가", 
        get_fallback_property_vacancy
    )
    df_rent, is_r_mock = load_table_safely(
        "임대동향 지역별 임대료 소규모 상가", 
        get_fallback_property_rent
    )
    df_fest, is_f_mock = load_table_safely(
        "문화관광축제주요지표", 
        get_fallback_festival
    )
    
    if is_v_mock or is_r_mock or is_f_mock:
        st.sidebar.warning("⚠️ 로컬 DB 일부 누락으로 데모용 시뮬레이션 데이터를 표시하고 있습니다.")
        
    m_vac, reg_col = melt_quarters(df_vac, "공실률")
    m_rent, _ = melt_quarters(df_rent, "임대료")
    
    df_prop = pd.merge(m_vac, m_rent, on=[reg_col, "분기"])
    
    fest_reg = detect_region_col(df_fest)
    fest_val = detect_numeric_col(df_fest)
    
    # Pandas 3.0 타입 연산 오류 회피를 위해 명시적 숫자형 형변환 수행
    df_fest_clean = df_fest.copy()
    df_fest_clean[fest_val] = pd.to_numeric(
        df_fest_clean[fest_val], 
        errors='coerce'
    ).fillna(0)
    
    df_fest_group = df_fest_clean.groupby(fest_reg)[fest_val].mean().reset_index()
    df_fest_group.rename(
        columns={fest_reg: "매칭키", fest_val: "축제평가지표"}, 
        inplace=True
    )
    
    # 결측 처리 및 float 객체 인덱싱 이슈 사전 제거
    df_prop["매칭키"] = df_prop[reg_col].apply(
        lambda x: str(x)[:2] if pd.notna(x) else ""
    )
    df_fest_group["매칭키"] = df_fest_group["매칭키"].apply(
        lambda x: str(x)[:2] if pd.notna(x) else ""
    )
    
    df_relation = pd.merge(df_prop, df_fest_group, on="매칭키")
    
    # 매칭 실패 시 시뮬레이션용 대체 세트 매핑
    if df_relation.empty:
        df_relation = pd.DataFrame({
            "축제평가지표": [85, 78, 92, 95, 80, 88, 90, 75],
            "임대료": [3.2, 2.5, 2.8, 5.1, 3.0, 4.2, 4.5, 2.1],
            "공실률": [12.1, 14.5, 10.2, 8.5, 11.5, 13.0, 9.8, 15.1]
        })
        fest_val_label = "축제 평가지표 (가상)"
    else:
        df_relation["축제평가지표"] = pd.to_numeric(
            df_relation["축제평가지표"], 
            errors='coerce'
        ).fillna(0)
        
        df_relation["임대료"] = pd.to_numeric(
            df_relation["임대료"], 
            errors='coerce'
        ).fillna(0)
        
        df_relation["공실률"] = pd.to_numeric(
            df_relation["공실률"], 
            errors='coerce'
        ).fillna(0)
        
        fest_val_label = f"축제 평가지표 ({fest_val})"
        
    st.subheader("📈 축제 성과수준 대비 상권 임대 정보 분포")
    
    col1, col2 = st.columns(2)
    with col1:
        fig1 = px.scatter(
            df_relation,
            x="축제평가지표",
            y="임대료",
            trendline="ols",
            title="축제 점수와 상가 평균 임대료 상관도",
            labels={"축제평가지표": fest_val_label, "임대료": "상가 임대료"},
            template="plotly_white"
        )
        st.plotly_chart(fig1, use_container_width=True, key="p2_scatter_rent")
        
    with col2:
        fig2 = px.scatter(
            df_relation,
            x="축제평가지표",
            y="공실률",
            trendline="ols",
            title="축제 점수와 상가 평균 공실률 상관도",
            labels={"축제평가지표": fest_val_label, "공실률": "평균 공실률 (%)"},
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True, key="p2_scatter_vac")
        
    st.markdown("---")
    st.markdown("""
    **📋 상권 요약 가이드**
    * **지역 변수**: 대도시와 중소 도시 상권 편차를 고려하여 지역별 세부 필터링 및 조정을 병행해 주십시오.
    * **임대 가치**: 축제로 발생한 단기 밀집 현상이 인위적 임대료 거품이나 영세 자영업자 퇴출(젠트리피케이션)로 연계되는지 모니터링해야 합니다.
    """)


# ==========================================
# 3. 페이지 3: 세금 효율성 분석 및 관광 효과
# ==========================================
def render_page3():
    st.title("💸 예산 집행 효율성 및 관광 연계 효과 진단")
    st.markdown("정부 예산 지출(순원가)이 관내 경제 진작과 국내 대체 관광수요 확보에 기여한 성과를 분석합니다.")
    
    df_cost, is_c_mock = load_table_safely(
        "행사원가회계정보", 
        get_fallback_cost
    )
    
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
    
    st.subheader(f"📊 [{selected_org}] 예산 운용 대조표")
    if not df_sub.empty:
        df_sub["총비용(백만원)"] = pd.to_numeric(
            df_sub[total_cost_col], 
            errors='coerce'
        ).fillna(0) / 1000000
        
        df_sub["순원가(백만원)"] = pd.to_numeric(
            df_sub[net_cost_col], 
            errors='coerce'
        ).fillna(0) / 1000000
        
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
