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

# 데이터베이스 파일 존재 여부 확인
if not os.path.exists(DB_FILE):
    st.error("데이터베이스 파일(project1.db)을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
    st.stop()


# 헬퍼 함수: DB 내 실제 테이블 목록 조회
def get_db_tables():
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    except Exception as e:
        st.error(f"테이블 목록을 조회하는 중 오류가 발생했습니다: {e}")
        return []
    finally:
        conn.close()


# 헬퍼 함수: 유사한 이름의 테이블 동적 매칭
def find_matching_table(target_name, available_tables):
    # 1. 정확히 일치하는 경우
    if target_name in available_tables:
        return target_name
    
    # 2. 공백 제거 후 비교
    target_stripped = target_name.replace(" ", "")
    for t in available_tables:
        if t.replace(" ", "") == target_stripped:
            return t
            
    # 3. 부분 일치 비교 (포함 관계)
    for t in available_tables:
        if target_stripped in t.replace(" ", "") or t.replace(" ", "") in target_stripped:
            return t
            
    return None


# 헬퍼 함수: 안전한 데이터 로드
def load_data_safely(table_name):
    available_tables = get_db_tables()
    matched_table = find_matching_table(table_name, available_tables)
    
    if not matched_table:
        st.warning(f"⚠️ 데이터베이스에서 '{table_name}'과 일치하거나 유사한 테이블을 찾을 수 없습니다.")
        return pd.DataFrame()
        
    conn = sqlite3.connect(DB_FILE)
    try:
        # 특정 컬럼을 지정하지 않고 전체 데이터를 먼저 가져옵니다. (Column Error 방지)
        df = pd.read_sql_query(f"SELECT * FROM `{matched_table}`", conn)
        return df
    except Exception as e:
        st.error(f"'{matched_table}' 테이블 로드 중 오류 발생: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


# 헬퍼 함수: 컬럼명 동적 매칭 (대소문자, 띄어쓰기 무시)
def find_col(columns, search_terms):
    for term in search_terms:
        for col in columns:
            clean_col = str(col).replace(" ", "").replace("·", "").replace("_", "").lower()
            clean_term = str(term).replace(" ", "").replace("·", "").replace("_", "").lower()
            if clean_term in clean_col:
                return col
    return None


# 가로 형태(Wide-format)의 분기별 데이터를 세로 형태(Long-format)로 변환
def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    
    region_col = find_col(df.columns, ["지역명", "지역", "행정구역", "시도", "구분"]) or df.columns[0]
    
    # 연도나 분기 패턴을 가진 컬럼 필터링
    quarter_cols = [
        c for c in df.columns 
        if c != region_col and (any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."]) or any(str(yr) in str(c) for yr in range(2015, 2027)))
    ]
    if not quarter_cols:
        # 패턴이 없을 경우 수치형 컬럼을 분기로 간주
        quarter_cols = df.select_dtypes(include=['number']).columns.tolist()
        quarter_cols = [c for c in quarter_cols if c != region_col]
        
    if not quarter_cols:
        quarter_cols = [c for c in df.columns if c != region_col]
        
    df_melted = df.melt(id_vars=[region_col], value_vars=quarter_cols, var_name="분기", value_name=value_name)
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col


# ==========================================
# 1. 페이지 1: 축제 현황 분석
# ==========================================
def render_page1():
    st.title("🎪 축제 현황 및 소비 트렌드 분석")
    st.markdown("문화관광축제의 주요 지표와 연도별 업종 소비 변화를 모니터링합니다.")
    
    df_festival = load_data_safely("문화관광축제주요지표")
    df_consume = load_data_safely("업종별소비액")
    
    # 1) 축제 주요 지표
    if not df_festival.empty:
        st.subheader("📍 축제별 주요 지표 비교")
        name_col = find_col(df_festival.columns, ["축제명", "행사명", "축제", "이름"]) or df_festival.columns[0]
        num_cols = df_festival.select_dtypes(include=['number']).columns.tolist()
        num_cols = [c for c in num_cols if c not in ["년도", "연도", "ID", "id"]]
        
        if num_cols:
            selected_metric = st.selectbox("분석할 지표 선택", num_cols, key="p1_metric")
            df_grouped = df_festival.groupby(name_col)[selected_metric].mean().reset_index()
            fig1 = px.bar(
                df_grouped,
                x=name_col,
                y=selected_metric,
                title=f"축제별 {selected_metric} 평균 현황",
                labels={name_col: "축제명", selected_metric: "평균값"},
                template="plotly_white"
            )
            st.plotly_chart(fig1, key="chart_fest_metric")
        else:
            st.write("시각화할 수 있는 수치형 지표 컬럼을 찾지 못했습니다.")
            st.dataframe(df_festival.head())
            
    # 2) 업종별 소비액 흐름 (동적 검색 적용하여 Column Error 원천 방지)
    if not df_consume.empty:
        st.subheader("💳 연도별 업종별 소비액 흐름")
        year_col = find_col(df_consume.columns, ["연도", "년도", "시기"]) or df_consume.columns[0]
        
        # '소비액' 단어가 들어갔거나 수치형 컬럼을 자동으로 탐색합니다.
        amt_cols = [c for c in df_consume.columns if "소비" in str(c) or "금액" in str(c) or "액" in str(c)]
        if not amt_cols:
            amt_cols = df_consume.select_dtypes(include=['number']).columns.tolist()
            amt_cols = [c for c in amt_cols if c != year_col]
            
        if amt_cols:
            # 여러 소비액 컬럼이 분리되어 있을 경우 대시보드 표현을 위해 정제
            df_consume_melted = df_consume.melt(
                id_vars=[year_col], 
                value_vars=amt_cols, 
                var_name="업종", 
                value_name="소비액"
            )
            
            # 연도별, 업종별 합계 계산
            df_grouped = df_consume_melted.groupby([year_col, "업종"])["소비액"].sum().reset_index()
            
            fig2 = px.line(
                df_grouped,
                x=year_col,
                y="소비액",
                color="업종",
                title="연도별 업종별 소비 트렌드",
                labels={year_col: "연도", "소비액": "소비액(원)", "업종": "업종명"},
                markers=True,
                template="plotly_white"
            )
            st.plotly_chart(fig2, key="chart_consume_trend")
        else:
            st.write("소비액 관련 수치 데이터를 찾을 수 없습니다.")
            st.dataframe(df_consume.head())
            
    st.info("""
    **💡 데이터 분석 핵심 인사이트**
    
    데이터 분석 결과, 다른 업종에 비해 '숙박업 소비액'의 비중이 현저히 낮게 나타납니다. 이는 관광객들이 지역에 체류하지 않고 '당일치기 관광'을 선호함을 시각적으로 보여줍니다. 결과적으로 축제가 개최되더라도 지방 관광 활성화 및 인구 소멸 대체 효과가 미미하다는 인사이트를 도출할 수 있습니다.
    """)


# ==========================================
# 2. 페이지 2: 젠트리피케이션 및 상권 분석
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션 및 상권 동향 분석")
    st.markdown("지역 상권의 소규모 및 중대형 상가 분기별 공실률과 임대료를 비교 분석합니다.")
    
    # 안전하게 테이블 로딩
    df_vac_small = load_data_safely("임대동향 지역별 공실률 소규모 상가")
    df_vac_large = load_data_safely("임대동향 지역별 공실률 중대형 상가")
    df_rent_small = load_data_safely("임대동향 지역별 임대료 소규모 상가")
    df_rent_large = load_data_safely("임대동향 지역별 임대료 중대형 상가")
    
    if not (df_vac_small.empty or df_vac_large.empty or df_rent_small.empty or df_rent_large.empty):
        m_vac_small, reg_vac_sm = melt_quarters(df_vac_small, "공실률")
        m_vac_large, reg_vac_lg = melt_quarters(df_vac_large, "공실률")
        m_rent_small, reg_rent_sm = melt_quarters(df_rent_small, "임대료")
        m_rent_large, reg_rent_lg = melt_quarters(df_rent_large, "임대료")
        
        # 공통 지역 목록 추출
        regions = sorted(list(set(m_vac_small[reg_vac_sm].dropna().unique())))
        selected_region = st.selectbox("조회할 지역을 선택하세요", regions)
        
        # 선택 지역 데이터 추출
        sub_vac_small = m_vac_small[m_vac_small[reg_vac_sm] == selected_region].copy()
        sub_vac_small["상가규모"] = "소규모 상가"
        
        sub_vac_large = m_vac_large[m_vac_large[reg_vac_lg] == selected_region].copy()
        sub_vac_large["상가규모"] = "중대형 상가"
        
        sub_rent_small = m_rent_small[m_rent_small[reg_rent_sm] == selected_region].copy()
        sub_rent_small["상가규모"] = "소규모 상가"
        
        sub_rent_large = m_rent_large[m_rent_large[reg_rent_lg] == selected_region].copy()
        sub_rent_large["상가규모"] = "중대형 상가"
        
        combined_vac = pd.concat([sub_vac_small, sub_vac_large], ignore_index=True).sort_values(by="분기")
        combined_rent = pd.concat([sub_rent_small, sub_rent_large], ignore_index=True).sort_values(by="분기")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_rent = px.line(
                combined_rent,
                x="분기",
                y="임대료",
                color="상가규모",
                title=f"[{selected_region}] 분기별 평균 임대료 추이 비교",
                markers=True,
                template="plotly_white"
            )
            st.plotly_chart(fig_rent, key="chart_rent_trend")
            
        with col2:
            fig_vac = px.line(
                combined_vac,
                x="분기",
                y="공실률",
                color="상가규모",
                title=f"[{selected_region}] 분기별 공실률 추이 비교",
                markers=True,
                template="plotly_white"
            )
            st.plotly_chart(fig_vac, key="chart_vac_trend")
    else:
        st.info("💡 분석에 필요한 임대동향 관련 테이블 중 일부를 찾지 못했습니다. 상단 디버깅 도구를 사용하여 테이블 명을 확인해 보십시오.")
        
    st.markdown("---")
    st.subheader("⚙️ 통제 변수 및 분석 가이드라인")
    st.markdown("""
    - **지역 간 격차 통제**: 상권 규모 및 도시 등급 차이로 인한 왜곡을 피하기 위해, 특정 단일 지역을 기준으로 필터링하여 일대일 시계열 추이를 정밀 비교하는 방식을 권장합니다.
    - **상가 규모 통제**: '소규모 상가'와 '중대형 상가'는 입점 브랜드 구성 및 임대료 방침이 크게 다릅니다. 이들을 그룹군별로 격리시켜 흐름을 교차 검증해야 올바른 변동 요인을 도출할 수 있습니다.
    - **외생 변수 고려**: 특정 분기의 변동이 지역축제의 변동 때문인지, 거시경제 지표(금리 변동 등)나 감염병 방역 단계 완화 시점 등 외부 충격에 의한 요인인지 변수 통제가 동반되어야 합니다.
    """)


# ==========================================
# 3. 페이지 3: 세금 효율성 분석
# ==========================================
def render_page3():
    st.title("💸 행사 예산 대비 세금 효율성 분석")
    st.markdown("축제 투입 예산 대비 소상공인 경기 신뢰 전망 지표를 대조하여 경제성 지표를 도출합니다.")
    
    df_cost = load_data_safely("행사원가회계정보")
    df_sme = load_data_safely("소상공인 지역별 실적 전망")
    
    if df_cost.empty:
        st.warning("행사원가회계정보 데이터 테이블을 불러오지 못했습니다.")
        return
        
    org_col = find_col(df_cost.columns, ["자치단체", "지자체", "지역"]) or df_cost.columns[1]
    name_col = find_col(df_cost.columns, ["행사축제명", "축제명", "행사명"]) or df_cost.columns[2]
    total_cost_col = find_col(df_cost.columns, ["총비용"]) or df_cost.columns[3]
    rev_col = find_col(df_cost.columns, ["사업수익"]) or df_cost.columns[4]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[5]
    
    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("분석 대상 자치단체 선택", org_list)
    
    df_cost_sub = df_cost[df_cost[org_col] == selected_org].copy()
    
    st.subheader(f"📊 [{selected_org}] 내 행사 소요 비용 정보")
    if not df_cost_sub.empty:
        df_cost_sub["총비용(백만원)"] = pd.to_numeric(df_cost_sub[total_cost_col], errors='coerce') / 1000000
        df_cost_sub["순원가(백만원)"] = pd.to_numeric(df_cost_sub[net_cost_col], errors='coerce') / 1000000
        
        df_cost_melted = df_cost_sub.melt(
            id_vars=[name_col], 
            value_vars=["총비용(백만원)", "순원가(백만원)"],
            var_name="비용구분", 
            value_name="금액"
        )
        
        fig_cost = px.bar(
            df_cost_melted,
            x=name_col,
            y="금액",
            color="비용구분",
            barmode="group",
            title="축제별 총비용 vs 순원가 대조 (백만 원)",
            labels={name_col: "축제명", "금액": "액수 (백만원)"},
            template="plotly_white"
        )
        st.plotly_chart(fig_cost, key="chart_tax_efficiency")
    else:
        st.write("해당 자치단체 소유의 회계 데이터가 존재하지 않습니다.")
        
    st.subheader("💡 세금 효율성 분석 및 소상공인 경기 검토")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1) 재정 자립 측면 자가 수입 비율**")
        if not df_cost_sub.empty:
            total_sum = pd.to_numeric(df_cost_sub[total_cost_col], errors='coerce').sum()
            rev_sum = pd.to_numeric(df_cost_sub[rev_col], errors='coerce').sum()
            net_sum = pd.to_numeric(df_cost_sub[net_cost_col], errors='coerce').sum()
            
            self_reliance = (rev_sum / total_sum * 100) if total_sum > 0 else 0
            st.metric("총 예산 투입액 (합계)", f"{total_sum:,.0f} 원")
            st.metric("정부 실질적 예산액 (순원가 합계)", f"{net_sum:,.0f} 원")
            st.metric("자체 수입 보전율", f"{self_reliance:.2f} %")
            
    with col2:
        st.markdown("**2) 관내 소상공인 실적 체감지수 검토**")
        sme_region_col = find_col(df_sme.columns, ["지역", "행정구역", "시도"])
        if sme_region_col and not df_sme.empty:
            # 시도 구분이 일치하는지 필터링
            df_sme_sub = df_sme[df_sme[sme_region_col].str.contains(selected_org[:2], na=False)]
            if not df_sme_sub.empty:
                st.write(f"👉 **소상공인 지역 실적 지표**")
                st.dataframe(df_sme_sub.head(3))
            else:
                st.write("해당 지자체와 일치하는 소상공인 실적 전망 데이터가 부재합니다.")
        else:
            st.write("소상공인 지역 전망 데이터가 로드되지 않았습니다.")


# ==========================================
# 4. 메인 실행 함수 및 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    
    # 개발 편의 및 실시간 스키마 확인을 위한 디버깅용 확장 패널 제공
    with st.sidebar.expander("🛠️ 실시간 DB 스키마 진단 도구"):
        st.write("현재 `project1.db`에 실재하는 테이블 목록입니다. 코드 작성 시 철자 확인용으로 활용 가능합니다.")
        tables = get_db_tables()
        if tables:
            st.code("\n".join(tables), language="text")
        else:
            st.error("테이블을 찾을 수 없습니다. DB를 점검해 주세요.")
            
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
