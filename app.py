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


# 가로 형태(Wide-format)의 분기별 데이터를 세로 형태(Long-format)로 변환
def melt_quarters(df, value_name):
    if df.empty:
        return pd.DataFrame(), None
    
    region_col = find_col(df.columns, ["지역명", "지역", "행정구역", "시도", "구분"]) or df.columns[0]
    
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
# 1. 페이지 1: 축제 현황 분석 (방문 비율 비교)
# ==========================================
def render_page1():
    st.title("🎪 축제별 방문객 구성 및 유입 분포 분석")
    st.markdown("문화관광축제의 주요 방문 지표를 대조하고, **현지인 거주자 유입**과 **외부 방문자(외지인) 유입**의 형태를 면밀히 비교합니다.")
    
    df_festival = load_data_safely("문화관광축제주요지표")
    
    if not df_festival.empty:
        # 주요 컬럼 자동 검색 키워드 확장
        name_col = find_col(df_festival.columns, ["축제명", "행사명", "축제", "이름"]) or df_festival.columns[0]
        local_col = find_col(df_festival.columns, ["내지인", "내국인", "지역민", "거주민", "현지인", "현지"])
        foreign_col = find_col(df_festival.columns, ["외지인", "외국인", "관광객", "외지", "외부방문", "외부"])
        
        st.subheader("📍 축제별 현지인 vs 외부 방문자 유입 규모")
        
        # [개선] 만약 자동으로 컬럼을 매칭하지 못했을 경우 에러를 내지 않고 사용자가 직접 선택할 수 있도록 폴백 인터페이스 마련
        if not local_col or not foreign_col:
            st.warning("⚠️ 방문객 분석에 필요한 일부 컬럼을 자동으로 매칭하지 못했습니다. 아래에서 적절한 컬럼을 수동 지정해주세요.")
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                local_col = st.selectbox("현지인 / 내지인 데이터 선택", df_festival.columns.tolist(), index=0)
            with col_sel2:
                foreign_col = st.selectbox("외지인 / 외부 방문자 데이터 선택", df_festival.columns.tolist(), index=min(1, len(df_festival.columns)-1))
        
        # 전처리: 수치형 변환
        df_plot = df_festival.copy()
        df_plot[local_col] = pd.to_numeric(df_plot[local_col], errors='coerce').fillna(0)
        df_plot[foreign_col] = pd.to_numeric(df_plot[foreign_col], errors='coerce').fillna(0)
        
        # [개선] 외부 방문자 유입이 높은 순으로 정렬할 수 있는 기능 제공으로 인사이트 유도
        sort_by_external = st.checkbox("외부 방문자(외지인) 유입 비율/수량이 높은 순으로 정렬", value=True)
        if sort_by_external:
            df_plot = df_plot.sort_values(by=foreign_col, ascending=False)
            
        # 시각화를 위한 Melt 진행
        df_melted_visit = df_plot.melt(
            id_vars=[name_col],
            value_vars=[local_col, foreign_col],
            var_name="방문유형",
            value_name="수치(비율 또는 인원)"
        )
        
        fig = px.bar(
            df_melted_visit,
            x=name_col,
            y="수치(비율 또는 인원)",
            color="방문유형",
            barmode="group",
            title="축제별 내외지인 방문객 대조 모델",
            labels={name_col: "축제명", "수치(비율 또는 인원)": "방문객 지표"},
            template="plotly_white",
            color_discrete_map={local_col: "#3498db", foreign_col: "#e74c3c"} # 명확한 색상 구별
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 인사이트 세부 리포트
        st.info(f"""
        **💡 데이터 분석 핵심 인사이트 (방문 분포 관점)**
        - `{foreign_col}`(외부 방문자)의 비중이 월등히 높은 축제일수록 외부 소비 자본을 지역 상권으로 이식하는 '경제 앵커' 역할을 훌륭히 수행하고 있음을 의미합니다.
        - 다만, 외부 유입 분포가 압도적임에도 불구하고 지역 내 소비 연계(예: 숙박업, 가맹점 매출) 지표가 동반 상승하지 못한다면, 이는 체류 시간이 짧은 **'당일치기 단순 경유형 관광'**에 그치고 있다는 한계를 방증합니다.
        """)
                
    else:
        st.info("문화관광축제주요지표 데이터를 조회할 수 없습니다. 데이터베이스 파일 내부 스키마를 점검해 주세요.")


# ==========================================
# 2. 페이지 2: 젠트리피케이션 및 상권 분석
# ==========================================
def render_page2():
    st.title("🏢 젠트리피케이션과 지역 축제의 상관관계 분석")
    st.markdown("지역 축제의 활성화 및 성공 지표 수준이 주변 상권의 **임대료 상승률** 및 **공실률 변동(젠트리피케이션 부작용)**에 미치는 인과관계를 통계적으로 추적합니다.")
    
    # 데이터 로드
    df_festival = load_data_safely("문화관광축제주요지표")
    df_vac_small = load_data_safely("임대동향 지역별 공실률 소규모 상가")
    df_rent_small = load_data_safely("임대동향 지역별 임대료 소규모 상가")
    
    if not (df_festival.empty or df_vac_small.empty or df_rent_small.empty):
        # 1) 상가 임대 정보 가공 (소규모 상가 기준)
        m_vac, reg_col = melt_quarters(df_vac_small, "공실률")
        m_rent, _ = melt_quarters(df_rent_small, "임대료")
        df_property = pd.merge(m_vac, m_rent, on=[reg_col, "분기"])
        
        # 자치단체 및 시도 매칭을 위한 검색 진행
        fest_reg_col = find_col(df_festival.columns, ["지자체", "자치단체", "지역", "시도"])
        fest_val_col = find_col(df_festival.columns, ["지표", "값", "방문객수", "실적"]) or df_festival.select_dtypes(include=['number']).columns[-1]
        
        # [개선] 컬럼 자동 매칭 폴백
        if not fest_reg_col or not fest_val_col:
            st.warning("⚠️ 축제 데이터와 상권 데이터를 매칭하기 위한 핵심 지표 컬럼을 찾지 못했습니다. 아래에서 수동 매칭을 진행해주세요.")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fest_reg_col = st.selectbox("축제 지역 기준 컬럼", df_festival.columns.tolist())
            with col_f2:
                fest_val_col = st.selectbox("축제 성과(방문객 등) 지표 컬럼", df_festival.columns.tolist())

        # 축제 데이터를 지역 단위로 그룹화하여 규모 산출
        df_fest_group = df_festival.groupby(fest_reg_col)[fest_val_col].mean().reset_index()
        df_fest_group.rename(columns={fest_reg_col: "매칭지역", fest_val_col: "축제활성화지표"}, inplace=True)
        
        # 상권 데이터의 '시도/지역' 명칭 축약 매칭 지원 (예: '강원특별자치도' -> '강원')
        df_property["매칭지역"] = df_property[reg_col].apply(lambda x: str(x)[:2])
        df_fest_group["매칭지역"] = df_fest_group["매칭지역"].apply(lambda x: str(x)[:2])
        
        # 최종 결합
        df_relation = pd.merge(df_property, df_fest_group, on="매칭지역")
        
        if not df_relation.empty:
            # 안전한 수치 연산 변환
            df_relation["축제활성화지표"] = pd.to_numeric(df_relation["축제활성화지표"], errors='coerce')
            df_relation["임대료"] = pd.to_numeric(df_relation["임대료"], errors='coerce')
            df_relation["공실률"] = pd.to_numeric(df_relation["공실률"], errors='coerce')
            df_relation.dropna(subset=["축제활성화지표", "임대료", "공실률"], inplace=True)

            st.subheader("📈 축제 성과와 상권 변동 간의 계량 통계 시각화")
            
            # [개선] 젠트리피케이션과 축제의 명확한 통계적 연관성을 부여하기 위해 '상관계수(Correlation)'를 실시간 계산 및 전시
            corr_rent = df_relation["축제활성화지표"].corr(df_relation["임대료"])
            corr_vac = df_relation["축제활성화지표"].corr(df_relation["공실률"])
            
            st.markdown(f"""
            #### 📊 **연관성 분석 지표 요약**
            - 축제 활성화 지표와 **상가 임대료** 간의 피어슨 상관계수: ` {corr_rent:.2f} `
            - 축제 활성화 지표와 **상가 공실률** 간의 피어슨 상관계수: ` {corr_vac:.2f} `
            """)
            
            col1, col2 = st.columns(2)
            with col1:
                fig_scat1 = px.scatter(
                    df_relation,
                    x="축제활성화지표",
                    y="임대료",
                    trendline="ols",
                    color="매칭지역",
                    title="축제 성공 수준에 따른 상가 임대료 추세선",
                    labels={"축제활성화지표": "축제 성과 지표 (평균)", "임대료": "상가 임대료 (㎡당)"},
                    template="plotly_white"
                )
                st.plotly_chart(fig_scat1, use_container_width=True)
                
            with col2:
                fig_scat2 = px.scatter(
                    df_relation,
                    x="축제활성화지표",
                    y="공실률",
                    trendline="ols",
                    color="매칭지역",
                    title="축제 성공 수준에 따른 상가 공실률 추세선",
                    labels={"축제활성화지표": "축제 성과 지표 (평균)", "공실률": "상가 공실률 (%)"},
                    template="plotly_white"
                )
                st.plotly_chart(fig_scat2, use_container_width=True)
                
            # 심층 연관성 설명문 보완
            st.markdown("""
            **🔍 젠트리피케이션 관점에서의 상관관계 해석 가이드**
            - **임대료와의 정(+)의 상관성**: 축제가 흥행하여 유동인구가 폭발하면 상권 확장 기대감으로 인해 주변 임대료가 급격히 상승하는 초기 젠트리피케이션이 유발될 수 있습니다.
            - **공실률과의 상호작용**: 만약 축제의 낙수효과가 일시적인 축제 기간에만 머무르고 비수기 상권 보전으로 이어지지 못한다면, 높은 임대료를 견디지 못한 원주민 소상공인들이 쫓겨나 상권이 공동화되는 **'둥지 내몰림(Gentrification) 및 공실률 급증'**의 부작용으로 이어질 위험성이 존재합니다. 추세선의 우상향/우하향 강도를 통해 지역별 리스크를 평가하십시오.
            """)
        else:
            st.warning("축제 데이터와 상권 임대 데이터 간 지역명 매칭 조건을 충족하는 행이 없습니다.")
    else:
        st.info("상권 분석용 데이터를 조회할 수 없습니다. 데이터베이스 파일 구성을 점검해 주세요.")


# ==========================================
# 3. 페이지 3: 세금 효율성 분석 및 지방 관광 대체 효과
# ==========================================
def render_page3():
    st.title("💸 지자체별 예산 효율성 및 지역 불균형 진단")
    st.markdown("납세자의 세금(행사 순원가)이 각 지방자치단체의 축제 예산으로 어떻게 소모되고 있는지 평가하고, **지역에 따른 뚜렷한 재정 격차와 변화 추이**를 추적합니다.")
    
    df_cost = load_data_safely("행사원가회계정보")
    
    if df_cost.empty:
        st.warning("행사 원가 정보를 가져올 수 없어 효율성 지표 출력이 보류되었습니다.")
        return
        
    org_col = find_col(df_cost.columns, ["자치단체", "지자체", "시도", "구분"]) or df_cost.columns[1]
    name_col = find_col(df_cost.columns, ["행사축제명", "축제명", "행사명"]) or df_cost.columns[2]
    total_cost_col = find_col(df_cost.columns, ["총비용"]) or df_cost.columns[3]
    net_cost_col = find_col(df_cost.columns, ["순원가"]) or df_cost.columns[5]
    
    # 데이터 정제 및 숫자 변환
    df_cost_clean = df_cost.copy()
    df_cost_clean["총비용_숫자"] = pd.to_numeric(df_cost_clean[total_cost_col], errors='coerce').fillna(0)
    df_cost_clean["순원가_숫자"] = pd.to_numeric(df_cost_clean[net_cost_col], errors='coerce').fillna(0)
    
    # [개선] 자체 보전액 메트릭을 과감히 빼버리고, 유의미한 '지역에 따른 변화와 인사이트'를 직접적으로 도출할 수 있는 요약 뷰 신설
    st.subheader("🗺️ 1. 지자체별 축제 총 예산 규모 및 세금 의존도 비교")
    st.markdown("지자체별로 그룹화하여 축제에 쏟아붓는 총 세금의 절대적인 규모와 **순수 정부 자금 의존도**의 뚜렷한 지역별 격차를 고발합니다.")
    
    # 지자체별 집계 계산
    df_region_summary = df_cost_clean.groupby(org_col).agg(
        총투입예산_억원=("총비용_숫자", lambda x: x.sum() / 1e8),
        순세금부담_억원=("순원가_숫자", lambda x: x.sum() / 1e8),
        개최축제수=(name_col, "count")
    ).reset_index()
    
    # 세금 의존율 산출 (순원가 / 총비용)
    df_region_summary["세금의존도(%)"] = (df_region_summary["순세금부담_억원"] / df_region_summary["총투입예산_억원"] * 100).fillna(0)
    df_region_summary = df_region_summary.sort_values(by="총투입예산_억원", ascending=False)
    
    # 지자체 거시 비교 차트 출력 (지역별 격차가 선명하게 연출됨)
    fig_region = px.bar(
        df_region_summary,
        x=org_col,
        y="총투입예산_억원",
        color="세금의존도(%)",
        color_continuous_scale="YlOrRd", # 세금 의존율이 높을수록 붉고 진하게 표현
        title="지방 자치단체별 축제 투입 예산 총액 및 예산 자립성 격차 (지역별 변화 분석)",
        labels={org_col: "지방자치단체", "총투입예산_억원": "총 투입 예산 (억 원)", "세금의존도(%)": "세금 의존율 (%)"},
        template="plotly_white"
    )
    st.plotly_chart(fig_region, use_container_width=True)
    
    # 2) 개별 지자체 선택 세부 진단 (기존 기능 유지 및 고도화)
    st.markdown("---")
    st.subheader("📊 2. 특정 지자체 내 세부 행사 예산 구조 대조")
    org_list = sorted(list(df_cost_clean[org_col].dropna().unique()))
    selected_org = st.selectbox("정밀 진단할 자치단체를 선택하세요", org_list)
    
    df_cost_sub = df_cost_clean[df_cost_clean[org_col] == selected_org].copy()
    
    if not df_cost_sub.empty:
        df_cost_sub["총비용(백만원)"] = df_cost_sub["총비용_숫자"] / 1e6
        df_cost_sub["순원가(백만원)"] = df_cost_sub["순원가_숫자"] / 1e6
        
        df_cost_melted = df_cost_sub.melt(
            id_vars=[name_col], 
            value_vars=["총비용(백만원)", "순원가(백만원)"],
            var_name="예산구분", 
            value_name="금액"
        )
        
        fig_cost = px.bar(
            df_cost_melted,
            x=name_col,
            y="금액",
            color="예산구분",
            barmode="group",
            title=f"[{selected_org}] 개별 축제별 투입 총비용 vs 세금 순원가 대조",
            labels={name_col: "축제/행사명", "금액": "액수 (백만 원)"},
            template="plotly_white"
        )
        st.plotly_chart(fig_cost, use_container_width=True)
        
    # 종합 비즈니스 리포트 및 인사이트 단락
    st.markdown("---")
    st.subheader("📋 세금 예산 효율성 및 지역 불균형 종합 진단 리포트")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("### 🔍 지역 간 예산 편차의 시사점")
        st.write("""
        - 위 거시 지자체 대조 차트를 보면, 어떤 자치단체는 예산 규모가 큼에도 불구하고 비정부 수익 모델이 탄탄해 세금 의존도(순원가 비중)가 낮게 제어되는 변화를 관찰할 수 있습니다.
        - 반면 재정 자립도가 취약한 소도시형 지자체는 축제 예산의 대부분이 민간 수익 없이 순수 지방세(순원가 90% 이상)로 메워지는 **'예산 고의존 격차'** 현상이 선명하게 관찰됩니다.
        """)
        
    with col2:
        st.write("### ✈️ 지방 관광 대체 효과 연계 제언")
        st.write("""
        - **재정 격차 대응 전략**: 세금 의존도가 높은 지자체일수록 축제의 기획 목적을 1페이지에서 도출한 **'외부 방문객 유입 극대화'**와 연계시켜야 합니다.
        - 외부 외지인의 간접 소비 행위(교통, 요식, 로컬 쇼핑 등)를 통해 지역 소비세 및 지방 재정 환수 효과가 창출될 때에만, 높은 세금 투입의 기회비용 및 예산 집행 효율성이 공공 정당성을 확보할 수 있습니다.
        """)


# ==========================================
# 4. 메인 실행 함수 및 네비게이션
# ==========================================
def main():
    st.sidebar.title("📌 대시보드 메뉴")
    
    # 실시간 DB 스키마 확인을 위한 디버깅 툴팁 제공
    with st.sidebar.expander("🛠️ 실시간 DB 스키마 진단 도구"):
        st.write("현재 데이터베이스에 적재되어 있는 실제 테이블 목록입니다.")
        tables = get_db_tables()
        if tables:
            st.code("\n".join(tables), language="text")
        else:
            st.error("테이블을 조회할 수 없습니다. DB 경로를 확인하세요.")
            
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
