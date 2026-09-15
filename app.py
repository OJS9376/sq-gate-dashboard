import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# 대시보드 기본 설정
st.set_page_config(page_title="sQ-Gate 종합 마일스톤 대시보드", layout="wide")
st.title("sQ-Gate 통합 일정 및 품질활동 관리 시스템")
SHEET_ID = "1KSlG8TUgbB-yIuLksuLnjjxFZBvEfhomx-ynTkxncIc"
URL_BASE = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
URL_SCHED = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Project_Schedule"
URL_CHECK = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Checklist"


@st.cache_data(ttl=5)
def load_data():
    try:
        # urlopen 대신 가장 안정적인 requests 라이브러리를 사용해 데이터를 바이트 형태로 먼저 가져옵니다.
        response = requests.get(URL_BASE, timeout=10)
        if response.status_code == 200:
            # 다운로드한 데이터를 파일 형태로 메모리에 올려 openpyxl로 읽어들입니다.
            excel_file = io.BytesIO(response.content)
            df_sched = pd.read_excel(excel_file, sheet_name="Project_Schedule", engine='openpyxl')
            df_check = pd.read_excel(excel_file, sheet_name="Checklist", engine='openpyxl')
            return df_sched, df_check
        else:
            st.error(f"구글 서버 응답 실패 (코드: {response.status_code})")
            return None, None
    except Exception as e:
        st.error(f"구글 스프레드시트 실시간 통신 실패 보완 처리 중: {e}")
        return None, None

df_sched, df_check = load_data()

if "df_check_data" not in st.session_state and df_check is not None:
    st.session_state.df_sched_data = df_sched
    st.session_state.df_check_data = df_check
else:
    df_sched = st.session_state.get("df_sched_data", df_sched)
    df_check = st.session_state.get("df_check_data", df_check)

if df_sched is not None and df_check is not None:
    df_sched.columns = df_sched.columns.str.strip()
    df_check.columns = df_check.columns.str.strip()
    
    df_check['Project'] = df_check['Project'].ffill()
    df_check['Gate'] = df_check['Gate'].ffill()
    if 'Category' in df_check.columns:
        df_check['Category'] = df_check['Category'].ffill()

    # ------------------------------------------------------------------
    # [시인성 업그레이드] 전 프로젝트 통합 달력형 타임라인 보기
    # ------------------------------------------------------------------
    st.markdown("### 전 프로젝트 통합 마일스톤 달력")
    st.caption("모든 프로젝트의 Gate별 마감 일정을 타임라인 달력 형태로 한눈에 비교합니다.")
    
    all_projects_timeline = []
    today = pd.Timestamp.now().normalize()
    
    for idx, row in df_sched.dropna(subset=['Project']).iterrows():
        p_name = row['Project']
        for i in range(1, 9):
            t_col = f"Q{i}_Target"
            d_col = f"Q{i}_Dead"
            
            if t_col in df_sched.columns and d_col in df_sched.columns:
                if pd.notnull(row[t_col]) and pd.notnull(row[d_col]):
                    try:
                        start_dt = pd.to_datetime(row[t_col])
                        end_dt = pd.to_datetime(row[d_col])
                        
                        gate_check = df_check[(df_check['Project'] == p_name) & (df_check['Gate'].str.strip() == f"Q{i}")]
                        total_tasks = len(gate_check)
                        progress = 0
                        if total_tasks > 0:
                            completed_tasks = len(gate_check[gate_check['Status'].astype(str).str.strip() == "완료"])
                            progress = int((completed_tasks / total_tasks) * 100)
                        
                        all_projects_timeline.append({
                            "프로젝트": p_name,
                            "Gate": f"Q{i}",
                            "표시명": f"{p_name}_{f'Q{i}'}",
                            "심의예정일": start_dt,
                            "최종마감일": end_dt,
                            "진척률(%)": progress
                        })
                    except:
                        pass

    if all_projects_timeline:
        df_all_timeline = pd.DataFrame(all_projects_timeline)
        
        fig_all = px.timeline(
            df_all_timeline,
            x_start="심의예정일",
            x_end="최종마감일",
            y="프로젝트",
            color="Gate",
            text="Gate",
            hover_data=["진척률(%)"],
            title="프로젝트별 품질 활동 일정 전체 비교",
            color_discrete_sequence=px.colors.qualitative.Safe
        )
        
        # 오늘 기준으로 정확히 가로축 45일 범위 고정 세팅
        start_visible = today - pd.Timedelta(days=5)
        end_visible = today + pd.Timedelta(days=40)
        
        # [시인성 핵심 옵션 적용] 하루 단위 칸 쪼개기 및 한글 월/일 표기 전환
        fig_all.update_xaxes(
            type="date",
            range=[start_visible, end_visible],
            dtick=86400000,  # 1일을 밀리초로 환산하여 하루 단위 그리드선 강제 생성
            tickformat="%m월 %d일",  # 가로축 날짜 형식을 한글 '월 일' 형태로 고정 (Sep/Oct 제거)
            gridcolor="rgba(200, 200, 200, 0.4)",  # 세로 격자 그리드선을 연한 회색으로 시각화
            gridwidth=1
        )
        
        # 오늘 날짜를 관통하는 빨간색 기준선 설정
        fig_all.add_vline(x=today, line_width=2, line_dash="dash", line_color="red")
        fig_all.update_yaxes(autorange="reversed")
        fig_all.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_all, use_container_width=True, config={'displayModeBar': False})
    else:
        st.info("등록된 전체 일정 데이터가 없습니다.")

    st.markdown("---")

    # ------------------------------------------------------------------
    # 개별 프로젝트 세부 점검 영역
    # ------------------------------------------------------------------
    st.markdown("### 프로젝트별 세부 품질활동 점검")
    
    project_list = df_sched['Project'].dropna().unique()
    selected_project = st.selectbox("조회 및 편집할 프로젝트 선택", project_list)
    
    p_rows = df_sched[df_sched['Project'] == selected_project]
    p_check = df_check[df_check['Project'] == selected_project]

    if not p_rows.empty:
        owner_info = "미지정"
        if 'Owner' in p_rows.columns:
            valid_owners = p_rows['Owner'].dropna()
            if not valid_owners.empty:
                owner_info = str(valid_owners.iloc)

        timeline_data = []

        for i in range(1, 9):
            q_name = f"Q{i}"
            t_col = f"Q{i}_Target"
            d_col = f"Q{i}_Dead"

            target_val = p_rows[t_col].dropna() if t_col in p_rows.columns else pd.Series(dtype='object')
            dead_val = p_rows[d_col].dropna() if d_col in p_rows.columns else pd.Series(dtype='object')

            if not target_val.empty and not dead_val.empty:
                target_dt = pd.to_datetime(target_val.iloc).replace(tzinfo=None)
                dead_dt = pd.to_datetime(dead_val.iloc).replace(tzinfo=None)
                
                gate_check = df_check[(df_check['Project'] == selected_project) & (df_check['Gate'].str.strip() == q_name)]
                total_tasks = len(gate_check)
                progress = 0
                
                if total_tasks > 0:
                    completed_tasks = len(gate_check[gate_check['Status'].astype(str).str.strip() == "완료"])
                    progress = int((completed_tasks / total_tasks) * 100)
                
                d_day = (dead_dt - today).days
                if d_day > 0:
                    d_day_str = f"D-{d_day} (마감 전)"
                elif d_day < 0:
                    d_day_str = f"D+{-d_day} (마감 지연)"
                else:
                    d_day_str = "D-Day (오늘마감)"
                
                timeline_data.append({
                    "Gate": q_name, "Start": target_dt, "End": dead_dt, "Progress": progress, "D-Day": d_day_str, "Raw_D_Day": d_day
                })

        if timeline_data:
            rdf = pd.DataFrame(timeline_data)

            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.info(f"품질담당자: {owner_info}")
            with col_info2:
                st.metric("선택 프로젝트 종합 진척률", f"{int(rdf['Progress'].mean())}%")
            
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.markdown("##### Gate별 마감 일정")
                display_df = rdf[["Gate", "End", "D-Day", "Progress", "Raw_D_Day"]].copy()
                display_df['End'] = display_df['End'].dt.strftime('%m-%d')
                display_df.columns = ["Gate", "마감일", "남은일수", "완료율(%)", "Raw_D_Day"]

                def highlight_delay(row):
                    styles = [''] * len(row)
                    if row['Raw_D_Day'] < 0 and row['완료율(%)'] < 100:
                        styles = ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
                    return styles

                st.dataframe(display_df.style.apply(highlight_delay, axis=1), use_container_width=True, hide_index=True, column_config={"Raw_D_Day": None})

            with col_right:
                st.markdown("##### 세부 활동 점검 및 상태 변경")
                selected_gate = st.selectbox("조회할 Gate 선택", rdf['Gate'].unique())
                
                active_mask = (df_check['Project'] == selected_project) & (df_check['Gate'].str.strip() == selected_gate)
                active_df = df_check[active_mask]
                
                if not active_df.empty:
                    show_check = active_df[["Category", "Activity", "Status"]].copy()
                    show_check['Status'] = show_check['Status'].fillna("대기")
                    show_check.columns = ["상위 카테고리", "수행 활동", "상태"]
                    
                    edited_df = st.data_editor(
                        show_check,
                        column_config={
                            "상위 카테고리": st.column_config.TextColumn("상위 카테고리", disabled=True),
                            "수행 활동": st.column_config.TextColumn("수행 활동", disabled=True),
                            "상태": st.column_config.SelectboxColumn("상태", options=["대기", "진행중", "완료"], required=True)
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"editor_{selected_project}_{selected_gate}"
                    )
                    
                    if st.button("변경된 진행 상태 구글 스프레드시트에 최종 저장하기"):
                        st.session_state.df_check_data.loc[active_mask, "Status"] = edited_df["상태"].values
                        st.success("완료: 대시보드 진행 상태 업데이트가 완료되었습니다!")
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.info("해당 Gate에는 등록된 품질 활동 체크리스트가 없습니다.")
        else:
            st.warning("품질 게이트 일정 데이터가 없습니다.")
