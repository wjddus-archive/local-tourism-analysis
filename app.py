import os
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as px_st  # 내장 라이브러리와 구분을 위해 관례적 사용
import streamlit as st

# ==========================================
# 0. 데이터베이스 연결 및 예외 처리
# ==========================================
DB_FILE = "project1.db"  # 요청하신 db 파일명 설정


def get_db_connection(db_path):
    """SQLite 데이터베이스 연결 함수 (파일 부재 시 예외 처리)"""
    if not os.path.exists(db_path):
        st.error(
            f"❌ 데이터베이스 파일('{db_path}')을 찾을 수 없습니다. 파일 경로를 다시 확인해주세요."
        )
        st.info(
            "💡 로컬 환경에 'project1.db' 파일이 스크립트와 같은 위치에 있는지 확인하거나, GitHub에 함께 업로드했는지 확인하세요."
        )
        return None
    return sqlite3.connect(db_path)


# 페이지 기본 설정
st.set_page_config(
    page_title="지역 공공데이터 분석 대시보드", layout="wide", initial_sidebar_state="expanded"
)

# DB 연결 확인
conn = get_db_connection(DB_FILE)

if conn is not None:
    # 사이드바 메뉴 구성
    st.sidebar.title("📊 분석 메뉴")
    page = st.sidebar.radio(
        "이동할 페이지를 선택하세요", ["1. 축제 현황 분석", "2. 젠트리피케이션 문제", "3. 세금 효율성 분석"]
    )

    # ==========================================
    # 1. 축제 현황 분석 페이지
    # ==========================================
    if page == "1. 축제 현황 분석":
        st.title("🎪 문화관광축제 현황 및 소비 패턴 분석")
        st.markdown(
            "축제의 주요 지표와 업종별 소비 패턴을 분석하여 지역 관광의 실태를 파악합니다."
        )
        st.write("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📌 문화관광축제 주요 지표")
            # 축제 지표 데이터 로드
            query1 = "SELECT 축제명, 그룹명, 개최년도, 구분명, 지표값 FROM 문화관광축제주요지표"
            df_festival = pd.read_sql_query(query1, conn)

            # 필터 UI
            selected_year = st.selectbox(
                "연도 선택", sorted(df_festival["개최년도"].unique(), reverse=True), key="f_year"
            )
            df_fest_filtered = df_festival[df_festival["개최년도"] == selected_year]

            st.dataframe(df_fest_filtered, use_container_width=True)

            # 시각화 (예시: 구분명별 평균 지표값)
            fig1 = px.bar(
                df_fest_filtered,
                x="구분명",
                y="지표값",
                color="그룹명",
                barmode="group",
                title=f"{selected_year}년 주요 지표 비교",
            )
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            st.subheader("💳 업종별 소비액 및 관광 형태")
            # 업종별 소비액 데이터 로드 (조인 없이 독립적 수행)
            query2 = "SELECT 연도, `쇼핑업 소비액(천원)`, `식음료업 소비액(천원)`, `운송업 소비액(천원)`, `여가서비스업 소비액(천원)`, `숙박업 소비액(천원)` FROM 업종별소비액"
            df_spend = pd.read_sql_query(query2, conn)

            st.dataframe(df_spend, use_container_width=True)

            # 소비 구조 시각화를 위해 데이터 재구조화 (Melt)
            df_spend_melted = df_spend.melt(
                id_vars=["연도"], var_name="업종", value_name="소비액"
            )

            fig2 = px.line(
                df_spend_melted,
                x="연도",
                y="소비액",
                color="업종",
                markers=True,
                title="연도별 업종 소비 트렌드",
            )
            st.plotly_chart(fig2, use_container_width=True)

            # 💡 중요 인사이트 명시 구역
            st.warning(
                """
                ### 🚨 핵심 인사이트
                - **숙박업 비중 저조:** 전체 소비액 중 **숙박업의 소비 비중이 타 업종 대비 현저히 낮은 수준**으로 분석됩니다.
                - **당일치기 관광 중심:** 이는 관광객들이 지역 내에 체류하지 않는 **'당일치기 관광'** 형태가 주를 이루고 있음을 시사합니다.
                - **한계점:** 결과적으로 축제 개최를 통한 **지방 관광 대체 및 지역 경제 활성화 효과가 미미함**을 보여주므로, 체류형 관광 상품 개발이 시급합니다.
                """
            )

    # ==========================================
    # 2. 젠트리피케이션 문제 페이지
    # ==========================================
    elif page == "2. 젠트리피케이션 문제":
        st.title("🏙️ 축제 상권과 젠트리피케이션 분석")
        st.markdown(
            "축제 활성화가 지역 상권의 임대료와 공실률(소규모 vs 중대형 상가)에 미치는 영향을 비교합니다."
        )
        st.write("---")

        # 시도/상권 선택을 위한 컨트롤러 (통제변수 역할)
        st.sidebar.subheader("🎛️ 지역 및 상권 통제변수")

        # 임대료 데이터에서 시도 목록 추출
        query_loc = "SELECT DISTINCT 시도, 상권명 FROM `임대동향 지역별 임대료 소규모 상가`"
        df_loc = pd.read_sql_query(query_loc, conn)

        selected_sido = st.sidebar.selectbox("시도 선택", df_loc["시도"].unique())
        available_towns = df_loc[df_loc["시도"] == selected_sido]["상권명"].unique()
        selected_town = st.sidebar.selectbox("상권명 선택", available_towns)

        # 데이터 가져오기 (소규모 vs 중대형 비교)
        # 1) 소규모 상가 임대료 및 공실률
        df_rent_small = pd.read_sql_query(
            f"SELECT * FROM `임대동향 지역별 임대료 소규모 상가` WHERE 시도='{selected_sido}' AND 상권명='{selected_town}'",
            conn,
        )
        df_empty_small = pd.read_sql_query(
            f"SELECT * FROM `임대동향 지역별 공실률 소규모 상가` WHERE 시도='{selected_sido}' AND 상권명='{selected_town}'",
            conn,
        )

        # 2) 중대형 상가 임대료 및 공실률
        df_rent_large = pd.read_sql_query(
            f"SELECT * FROM `임대동향 지역별 임대료 중대형 상가` WHERE 시도='{selected_sido}' AND 상권명='{selected_town}'",
            conn,
        )
        df_empty_large = pd.read_sql_query(
            f"SELECT * FROM `임대동향 지역별 공실률 중대형 상가` WHERE 시도='{selected_sido}' AND 상권명='{selected_town}'",
            conn,
        )

        # 분석용 데이터 재구성 (분기별 컬럼 -> 행 변환)
        def reshape_market_data(df, value_name, scale):
            if df.empty:
                return pd.DataFrame()
            cols = [c for c in df.columns if "1Q" in c or "2Q" in c or "3Q" in c or "4Q" in c]
            df_melt = df.melt(id_vars=["시도", "상권명"], value_vars=cols, var_name="분기", value_name=value_name)
            df_melt["규모"] = scale
            return df_melt

        df_r_s = reshape_market_data(df_rent_small, "임대료", "소규모")
        df_r_l = reshape_market_data(df_rent_large, "임대료", "중대형")
        df_rent_all = pd.concat([df_r_s, df_r_l], ignore_index=True)

        df_e_s = reshape_market_data(df_empty_small, "공실률", "소규모")
        df_e_l = reshape_market_data(df_empty_large, "공실률", "중대형")
        df_empty_all = pd.concat([df_e_s, df_e_l], ignore_index=True)

        # 시각화 화면 배치
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"📈 {selected_town} 상권 임대료 추이 (소규모 vs 중대형)")
            if not df_rent_all.empty:
                fig_rent = px.line(
                    df_rent_all,
                    x="분기",
                    y="임대료",
                    color="규모",
                    markers=True,
                    title="분기별 ㎡당 임대료 비교",
                )
                st.plotly_chart(fig_rent, use_container_width=True)
            else:
                st.info("선택한 상권의 임대료 데이터가 없습니다.")

        with col2:
            st.subheader(f"📉 {selected_town} 상권 공실률 추이 (소규모 vs 중대형)")
            if not df_empty_all.empty:
                fig_empty = px.line(
                    df_empty_all,
                    x="분기",
                    y="공실률",
                    color="규모",
                    markers=True,
                    title="분기별 공실률(%) 비교",
                )
                st.plotly_chart(fig_empty, use_container_width=True)
            else:
                st.info("선택한 상권의 공실률 데이터가 없습니다.")

        # 축제 지표 참고용 데이터 띄우기
        st.subheader("🎪 해당 지역 관련 문화관광축제 지표")
        df_fest_ref = pd.read_sql_query(
            "SELECT 개최년도, 축제명, 구분명, 지표값 FROM 문화관광축제주요지표", conn
        )
        st.dataframe(df_fest_ref.head(10), use_container_width=True)

    # ==========================================
    # 3. 세금 효율성 분석 페이지
    # ==========================================
    elif page == "3. 세금 효율성 분석":
        st.title("💰 행사원가 및 세금 효율성 분석")
        st.markdown(
            "축제 및 행사 투입 비용 대비 소상공인 실적 전망과 축제 지표를 비교하여 예금 집행의 효율성을 평가합니다."
        )
        st.write("---")

        # 1. 행사원가회계정보
        st.subheader("💵 1. 행사원가 회계 정보")
        query_cost = "SELECT 년도, 자치단체, `행사·축제명`, 총비용, 사업수익, 순원가 FROM 행사원가회계정보"
        df_cost = pd.read_sql_query(query_cost, conn)
        st.dataframe(df_cost, use_container_width=True)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📊 자치단체별 행사 총비용 규모")
            fig_cost = px.bar(
                df_cost.groupby("자치단체")["총비용"].sum().reset_index(),
                x="자치단체",
                y="총비용",
                title="지자체별 투자된 총 행사 비용",
            )
            st.plotly_chart(fig_cost, use_container_width=True)

        with col2:
            # 2. 소상공인 지역별 실적 전망
            st.subheader("📈 2. 소상공인 지역별 체감/전망 경기")
            query_biz = "SELECT 지역, 기준날짜, 체감, 전망 FROM `소상공인 지역별 실적 전망`"
            df_biz = pd.read_sql_query(query_biz, conn)

            # 시각화를 위해 평균값 계산
            df_biz_avg = df_biz.groupby("지역")[["체감", "전망"]].mean().reset_index()
            fig_biz = px.scatter(
                df_biz_avg,
                x="체감",
                y="전망",
                text="지역",
                title="지역별 소상공인 경기 체감 vs 전망 (평균)",
            )
            fig_biz.update_traces(textposition="top center")
            st.plotly_chart(fig_biz, use_container_width=True)

        # 3. 문화관광축제 지표 종합 비교
        st.subheader("🎪 3. 문화관광축제 성과 지표 요약")
        query_fest_idx = "SELECT 축제명, 구분명, AVG(지표값) as 평균지표값 FROM 문화관광축제주요지표 GROUP BY 축제명, 구분명"
        df_fest_idx = pd.read_sql_query(query_fest_idx, conn)
        st.dataframe(df_fest_idx, use_container_width=True)

        st.info(
            "💡 **효율성 분석 가이드:** 지자체별 '총비용' 투입 대비 소상공인의 '체감/전망' 지표의 향상 여부 및 '축제 평균 지표값'의 정량적 크기를 비교하여 투입 대비 효과(ROI)를 도출할 수 있습니다."
        )

    # 연결 종료
    conn.close()
