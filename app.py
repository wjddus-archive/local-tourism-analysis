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

# 데이터베이스 파일 존재 여부 확인 (전체 시스템 요구사항 1번)
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


# 헬퍼 함수: 안전한 데이터 로드
def load_data_safely(table_name):
    available_tables = get_db_tables()
    matched_table = find_matching_table(table_name, available_tables)
    
    if not matched_table:
        return pd.DataFrame()
        
    conn = sqlite3.connect(DB_FILE)
    try:
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


# 지능형 탐색 엔진 1: 텍스트 컬럼 중 행정구역(지역)이 포함된 컬럼 자동 검출
def detect_region_col(df):
    name_match = find_col(df.columns, ["지자체", "자치단체", "지역", "시도", "개최지", "행정구역", "상권명"])
    if name_match:
        return name_match
    
    # 컬럼 내부 값 검사 시도
    for col in df.columns:
        if df[col].dtype == 'object':
            sample = df[col].dropna().unique()
            for val in sample:
                if any(reg in str(val) for reg in ["서울", "경기", "인천", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주", "부산", "대구", "광주", "대전", "울산", "세종"]):
                    return col
    # 기본값
    obj_cols = df.select_dtypes(include=['object']).columns.tolist()
    return obj_cols[0] if obj_cols else df.columns[0]


# 지능형 탐색 엔진 2: 년도/ID를 제외한 첫 번째 유효한 수치형(지표) 컬럼 자동 검출
def detect_numeric_col(df):
    name_match = find_col(df.columns, ["지표", "값", "실적", "방문", "관광객", "점수", "인원"])
    if name_match:
        return name_match
    
    num_cols = df.select_dtypes(include=['number']).columns.tolist()
    for col in num_cols:
        if not any(ex in str(col).lower() for ex in ["연도", "년도", "id", "코드"]):
            return col
    return num_cols[0] if num_cols else None


# 가로 형태(Wide-format)의 분기별 데이터를 세로 형태(Long-format)로 변환
def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    
    region_col = detect_region_col(df)
    
    quarter_cols = [
        c for c in df.columns 
        if c != region_col and (any(q in str(c) for q in ["Q", "q", "1/4", "2/4", "3/4", "4/4", "_", "."]) or any(str(yr) in str(c) for yr in range(2015, 2027)))
    ]
    if not quarter_cols:
        quarter_cols = df.select_dtypes(include=['number']).columns.tolist()
        quarter_cols = [c for c in quarter_cols if c != region_col]
        
    df_melted = df.melt(id_vars=[region_col], value_vars=quarter_cols, var_name="분기", value_name=value_name)
    df_melted["분기"] = df_melted["분기"].astype(str)
    return df_melted, region_col


# ==========================================
# 1. 페이지 1: 축제 현황 분석 (방문자 유입 및 소비액)
# ==========================================
def render_page1():
    st.title("🎪 축제별 방문객 구성 및 업종 소비 패턴")
    st.markdown("현지인/외부인 방문 형태를 조망하고 업종별 누적 소비 비중을 확인합니다.")
    
    df_festival = load_data_safely("문화관광축제주요지표")
    df_consume = load_data_safely("업종별소비액")
    
    # 1) 방문 비율 비교 시각화 (요구사항: 외부방문자 유입, 현지인방문자 유입 칼럼 매칭)
    if not df_festival.empty:
        st.subheader("📍 축제별 방문객 유입 비율 대조")
        
        # 외부방문자 유입 및 현지인방문자 유입 탐색
        local_col = find_col(df_festival.columns, ["현지인방문자 유입", "현지인"])
        foreign_col = find_col(df_festival.columns, ["외부방문자 유입", "외부방문자", "외지인"])
        name_col = find_col(df_festival.columns, ["축제명", "행사명", "축제", "이름"]) or df_festival.columns[0]
        
        if local_col and foreign_col:
            # 수치형 변환 보장
            df_festival[local_col] = pd.to_numeric(df_festival[local_col], errors='coerce')
            df_festival[foreign_col] = pd.to_numeric(df_festival[foreign_col], errors='coerce')
            
            df_melted_visit = df_festival.melt(
                id_vars=[name_col],
                value_vars=[local_col, foreign_col],
                var_name="방문객 유형",
                value_name="유입 수치 / 비율"
            )
            
            fig1 = px.bar(
                df_melted_visit,
                x=name_col,
                y="유입 수치 / 비율",
                color="방문객 유형",
                barmode="group",
                title="현지인 방문자 vs 외부 방문자 유입 비교",
                labels={name_col: "축제명", "유입 수치 / 비율": "방문자 수치"},
                color_discrete_sequence=px.colors.qualitative.Pastel,
                template="plotly_white"
            )
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.warning("⚠️ '현지인방문자 유입' 또는 '외부방문자 유입' 컬럼을 데이터베이스에서 매칭하지 못했습니다. 실제 컬럼명을 확인해 주십시오.")
            st.dataframe(df_festival.head())
            
    # 2) 업종별 소비액 복구 및 시각화 (요구사항 반영)
    if not df_consume.empty:
        st.subheader("💳 업종별 소비 규모 분석")
        
        sector_col = find_col(df_consume.columns, ["업종", "분류", "카테고리"]) or df_consume.columns[1]
        amt_col = find_col(df_consume.columns, ["소비액", "금액", "매출", "지출"]) or df_consume.select_dtypes(include=['number']).columns[-1]
        
        # 수치형 보장
        df_consume[amt_col] = pd.to_numeric(df_consume[amt_col], errors='coerce')
        df_grouped = df_consume.groupby(sector_col)[amt_col].sum().reset_index()
        df_grouped = df_grouped.sort_values(by=amt_col, ascending=True)
        
        fig2 = px.bar(
            df_grouped,
            y=sector_col,
            x=amt_col,
            orientation='h',
            title="업종별 총 소비액 분포",
            labels={sector_col: "업종명", amt_col: "총 소비 금액 (원)"},
            color=amt_col,
            color_continuous_scale="Viridis",
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("업종별소비액 데이터가 존재하지 않거나 비어 있습니다.")

    # 필수 데이터 인사이트 제공 (요구사항)
    st.info("""
    **💡 데이터 분석 핵심 인사이트**
    
    데이터 분석 결과, 다른 업종에 비해 '숙박업 소비액'의 비중이 현저히 낮게 나타납니다. 이는 관광객들이 지역에 체류하지 않고 '당일치기 관광'을 선호함을 시각적으로 보여줍니다. 결과적으로 축제가 개최되더라도 지방 관광 활성화 및 인구 소멸 대체 효과가 미미하다는 인사이트를 도출할 수 있습니다.
    """)


# ==========================================
# 2. 페이지 2: 젠트리피케이션 및 상권 분석 (이미지 오류 해결)
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제의 상관성 규명")
    st.markdown("축제 활성화 성과와 상가 공실률/임대료 지표의 추세를 교차 검증합니다.")
    
    df_festival = load_data_safely("문화관광축제주요지표")
    df_vac_small = load_data_safely("임대동향 지역별 공실률 소규모 상가")
    df_rent_small = load_data_safely("임대동향 지역별 임대료 소규모 상가")
    
    if not (df_festival.empty or df_vac_small.empty or df_rent_small.empty):
        # 분기별 임대 데이터 가공
        m_vac, reg_col = melt_quarters(df_vac_small, "공실률")
        m_rent, _ = melt_quarters(df_rent_small, "임대료")
        
        # 임대 데이터 임시 병합
        df_property = pd.merge(m_vac, m_rent, on=[reg_col, "분기"])
        
        # [해결 핵심] 지능형 지역 및 지표 컬럼 탐색 자동 적용
        fest_reg_col = detect_region_col(df_festival)
        fest_val_col = detect_numeric_col(df_festival)
        
        if fest_reg_col and fest_val_col:
            # 축제 데이터를 지자체별로 평균내어 요약
            df_fest_group = df_festival.groupby(fest_reg_col)[fest_val_col].mean().reset_index()
            df_fest_group.rename(columns={fest_reg_col: "매칭키", fest_val_col: "축제평가지표"}, inplace=True)
            
            # 행정구역 전처리 통일화 (두 글자 비교: 강원도/강원특별자치도 -> '강원')
            df_property["매칭키"] = df_property[reg_col].astype(str).apply(lambda x: x[:2])
            df_fest_group["매칭키"] = df_fest_group["매칭키"].astype(str).apply(lambda x: x[:2])
            
            # 데이터 동적 결합
            df_relation = pd.merge(df_property, df_fest_group, on="매칭키")
            
            if not df_relation.empty:
                st.subheader("📈 축제 활성화 지표 vs 상권 임대료/공실률 상관성 산점도")
                st.write("축제 평가지표 수준과 부동산 변수의 추이를 선형 매칭하여 젠트리피케이션 상관관계를 진단합니다.")
                
                col1, col2 = st.columns(2)
                with col1:
                    fig_scat1 = px.scatter(
                        df_relation,
                        x="축제평가지표",
                        y="임대료",
                        trendline="ols",
                        title="축제 활성화 대비 상가 임대료 변동 추세",
                        labels={"축제평가지표": f"축제 지표 ({fest_val_col})", "임대료": "상가 임대료"},
                        template="plotly_white"
                    )
                    st.plotly_chart(fig_scat1, use_container_width=True)
                    
                with col2:
                    fig_scat2 = px.scatter(
                        df_relation,
                        x="축제평가지표",
                        y="공실률",
                        trendline="ols",
                        title="축제 활성화 대비 상가 공실률 변동 추세",
                        labels={"축제평가지표": f"축제 지표 ({fest_val_col})", "공실률": "공실률 (%)"},
                        template="plotly_white"
                    )
                    st.plotly_chart(fig_scat2, use_container_width=True)
            else:
                # 결합 데이터가 비어 있을 경우 방어 로직 (시도 수준으로 한번 더 매칭)
                st.warning("⚠️ 행정구역 매칭 범위 불일치로 병합된 데이터가 없습니다. 아래에서 원본 테이블 형태를 대조해 보십시오.")
                c1, c2 = st.columns(2)
                with c1:
                    st.write("축제 데이터 지역 키:", df_fest_group.head(2))
                with c2:
                    st.write("상권 데이터 지역 키:", df_property.head(2))
        else:
            st.error("데이터 매칭에 적합한 수치형 지표 컬럼을 식별하지 못했습니다.")
    else:
        st.info("필요한 데이터가 불충분합니다.")

    # 간결하고 명확하게 수정된 가이드라인 (요구사항)
    st.markdown("---")
    st.subheader("📋 상권 분석 요약 가이드")
    st.markdown("""
    - **지역 통제**: 수도권 중심 상권과 지방 외곽 소도시 상권 간 격차에 유의하여 필터를 개별 적용하세요.
    - **상가 규모**: 소규모 상가와 대규모 집객 상가의 젠트리피케이션 양상이 다르므로 이들을 별도 검증해야 합니다.
    """)


# ==========================================
# 3. 페이지 3: 세금 효율성 분석 및 관광 효과
# ==========================================
def render_page3():
    st.title("💸 예산 효율성 및 지방 관광 대체 효과")
    st.markdown("축제 투입 원가(세금) 대비 소상공인 경기 지표를 결합하여 효용성을 평가합니다.")
    
    df_cost = load_data_safely("행사원가회계정보")
    df_sme = load_data_safely("소상공인 지역별 실적 전망")
    
    if df_cost.empty:
        st.warning("행사원가 정보가 불충분합니다.")
        return
        
    org_col = find_col(df_cost.columns, ["자치단체", "지자체"]) or df_cost.columns[1]
    name_col = find_col(df_cost.columns, ["행사축제명", "축제명", "행사명"]) or df_cost.columns[2]
    total_cost_col = find_col(df_cost.columns, ["총비용"]) or df_cost.columns[3]
    rev_col = find_col(df_cost.columns, ["사업수익"]) or df_cost.columns[4]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[5]
    
    org_list = sorted(list(df_cost[org_col].dropna().unique()))
    selected_org = st.selectbox("진단 대상 자치단체 선택", org_list)
    
    df_cost_sub = df_cost[df_cost[org_col] == selected_org].copy()
    
    st.subheader(f"📊 [{selected_org}] 원가 대비 자체 수익성 현황")
    if not df_cost_sub.empty:
        df_cost_sub["총비용(백만원)"] = pd.to_numeric(df_cost_sub[total_cost_col], errors='coerce') / 1000000
        df_cost_sub["순원가(백만원)"] = pd.to_numeric(df_cost_sub[net_cost_col], errors='coerce') / 1000000
        
        df_cost_melted = df_cost_sub.melt(
            id_vars=[name_col], 
            value_vars=["총비용(백만원)", "순원가(백만원)"],
            var_name="지표구분", 
            value_name="금액"
        )
        
        fig_cost = px.bar(
            df_cost_melted,
            x=name_col,
            y="금액",
            color="지표구분",
            barmode="group",
            title="총비용 및 정부 세금부담액(순원가) 대조",
            labels={name_col: "축제명", "금액": "액수 (백만원)"},
            color_discrete_sequence=px.colors.sequential.Agsunset,
            template="plotly_white"
        )
        st.plotly_chart(fig_cost, use_container_width=True)
        
    # 간결하고 명확하게 수정된 종합 진단 문구 (요구사항)
    st.markdown("---")
    st.subheader("📋 예산 효율 및 관광 유인 요약 리포트")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 📉 세금 의존도 요약")
        st.markdown("""
        - **재정적 자생력**: 순원가(보조금 세금) 비중이 높을수록 자치단체 예산에 부담이 가중되므로 기획 상품 판매 등 자체 자립 모델 조성이 권장됩니다.
        - **비용 효율**: 적은 원가 투입으로 고부가가치를 발생시킬수록 납세자 예산 집행 효율성이 향상됩니다.
        """)
        
    with col2:
        st.write("### ✈️ 지방 관광 대체 효과 요약")
        st.markdown("""
        - **관광 대체**: 지방 축제 투입 세금은 국내 여행 활성화를 촉진하고 해외여행 수요를 지역으로 흡수하는 간접 편익을 제공합니다.
        - **생활인구 유도**: 정주 인구가 감소하는 지방 소도시에 외부 유입을 유도하여, 정성적인 지역 소멸 예방 및 소상공인 매출 개선 효과를 견인합니다.
        """)


# ==========================================
# 4. 메인 실행 함수 및 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    
    with st.sidebar.expander("🛠️ 실시간 DB 스키마 진단 도구"):
        st.write("데이터베이스 내 실제 테이블 목록:")
        tables = get_db_tables()
        if tables:
            st.code("\n".join(tables), language="text")
        else:
            st.error("테이블을 조회할 수 없습니다.")
            
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
