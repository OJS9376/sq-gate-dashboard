import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# 웹페이지 기본 설정
st.set_page_config(page_title="sQ-Gate 품질활동 대시보드", layout="wide")
st.title("sQ-Gate 일정 및 품질활동 관리 시스템")

# 1. 파일 업로드
uploaded_file = st.file_uploader("sQ-Gate 관리 엑셀 파일을 업로드해주세요 (xlsx)", type=["xlsx"])

if uploaded_file is not None:
    try:
        # 두 개의 시트를 각각 읽어옴
        df_sched = pd.read_excel(uploaded_file, sheet_name="Project_Schedule", engine='openpyxl')
        df_check = pd.read_excel(uploaded_file, sheet_name="Checklist", engine='openpyxl')
        
        df_sched.columns = df_sched.columns.str.strip()
        df_check.columns = df_check.columns.str.strip()
    except Exception as e:
        st.error(f"엑셀 로드 실패 (시트 이름 Project_Schedule 및 Checklist 확인 필요): {e}")
        st.stop()

    # 2. 프로젝트 선택 필터
    st.sidebar.header("조회 조건")
    selected_project = st.sidebar.selectbox("프로젝트 선택", df_sched['Project'].unique())
    p_data = df_sched[df_sched['Project'] == selected_project].iloc[0]

    # 3. 프로젝트별 체크리스트 진척도 자동 계산 및 타임라인 데이터 구축
    timeline_data = []
    today = datetime.now()
    
    # 선택된 프로젝트의 체크리스트만 필터링
    p_check = df_check[df_check['Project'] == selected_project]

    for i in range(1, 9):
        q_name = f"Q{i}"
        t_col = f"Q{i}_Target"
        d_col = f"Q{i}_Dead"

        if t_col in df_sched.columns and d_col in df_sched.columns and pd.notnull(p_data[t_col]):
            target_dt = pd.to_datetime(p_data[t_col])
            dead_dt = pd.to_datetime(p_data[d_col])
            
            # 해당 Gate의 체크리스트 항목 추출 및 진척도 계산
            gate_check = p_check[p_check['Gate'] == q_name]
            total_tasks = len(gate_check)
            
            if total_tasks > 0:
                completed_tasks = len(gate_check[gate_check['Status'] == "완료"])
                progress = int((completed_tasks / total_tasks) * 100)
            else:
                progress = 0 # 체크리스트 항목이 없으면 0% 시작
            
            d_day = (dead_dt - today).days
            
            timeline_data.append({
                "Gate": q_name,
                "Start": target_dt,
                "End": dead_dt,
                "Progress": progress,
                "D-Day": f"D-{d_day}" if d_day > 0 else (f"D+{-d_day}" if d_day < 0 else "D-Day"),
                "Total_Tasks": total_tasks,
                "Completed_Tasks": completed_tasks
            })

    if not timeline_data:
        st.warning("품질 게이트 일정 데이터가 없습니다.")
        st.stop()

    rdf = pd.DataFrame(timeline_data)

    # 4. 상단 요약 정보
    st.subheader(f"프로젝트 명: {selected_project} (품질담당자: {p_data['Owner']})")
    
    col1, col2 = st.columns(2)
    col1.metric("종합 품질활동 진척률", f"{int(rdf['Progress'].mean())}%")
    
    # 5. 타임라인 차트 출력
    fig = px.timeline(
        rdf,
        x_start="Start",
        x_end="End",
        y="Gate",
        color="Progress",
        color_continuous_scale="YlGnBu",
        range_color=[0, 100],
        hover_data=["D-Day", "Progress"],
        title="sQ-Gate 마일스톤 흐름 (품질활동 완료율 연동)"
    )
    fig.update_yaxes(autorange="reversed")
    fig.add_vline(x=today.strftime("%Y-%m-%d"), line_width=2, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

    # 6. 하단 영역 분할: [왼쪽] 마감 일정표  |  [오른쪽] 개발품질 할 일 (체크리스트)
    st.markdown("---")
    left_col, right_col = st.columns(2)
    
    with left_col:
        st.subheader("Gate별 마감 현황")
        display_df = rdf[["Gate", "Start", "End", "Progress", "D-Day"]].copy()
        display_df['Start'] = display_df['Start'].dt.strftime('%Y-%m-%d')
        display_df['End'] = display_df['End'].dt.strftime('%Y-%m-%d')
        display_df.columns = ["품질 게이트", "심의예정일", "최종마감일", "활동 완료율(%)", "남은 일수"]
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    with right_col:
        st.subheader("Gate별 개발품질 세부 활동 점검")
        
        # 사용자가 점검할 Gate를 선택할 수 있게 셀렉트박스 제공
        selected_gate = st.selectbox("활동을 확인할 품질 게이트 선택", rdf['Gate'].unique())
        
        # 선택된 Gate의 세부 할 일 목록 가져오기
        active_check = p_check[p_check['Gate'] == selected_gate]
        
        if len(active_check) > 0:
            show_check = active_check[["Activity", "Status"]].copy()
            show_check.columns = ["개발품질 수행 활동 (Checklist)", "진행 상태"]
            
            # 스타일링 (완료는 녹색, 진행중은 황색 등으로 시각적 구분)
            def color_status(val):
                if val == "완료": return "background-color: #d4edda; color: #155724"
                elif val == "진행중": return "background-color: #fff3cd; color: #856404"
                return "background-color: #f8d7da; color: #721c24"
                
            st.dataframe(show_check.style.applymap(color_status, subset=["진행 상태"]), use_container_width=True, hide_index=True)
        else:
            st.info("해당 Gate에는 등록된 품질 활동 체크리스트가 없습니다.")

else:
    st.info("상단의 탐색기를 통해 Project_Schedule 시트와 Checklist 시트가 포함된 엑셀 파일을 업로드해주세요.")
