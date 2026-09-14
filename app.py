import streamlit as st
import pandas as pd
import plotly.express as px

# 대시보드 기본 설정
st.set_page_config(page_title="sQ-Gate 품질활동 대시보드", layout="centered")

st.title("sQ-Gate 일정 및 품질활동 관리 시스템")

# 구글 스프레드시트 연동 주소 입력 (3단계에서 바꾼 주소를 여기에 넣으세요)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1KSlG8TUgbB-yIuLksuLnjjxFZBvEfhomx-ynTkxncIc/export?format=xlsx"

# 팀원들이 접속할 때마다 구글 시트에서 새로운 데이터를 실시간으로 가져오는 함수 (캐시 10초 유지)
@st.cache_data(ttl=10)
def load_google_sheet(url):
    try:
        df_sched = pd.read_excel(url, sheet_name="Project_Schedule", engine='openpyxl')
        df_check = pd.read_excel(url, sheet_name="Checklist", engine='openpyxl')
        return df_sched, df_check
    except Exception as e:
        st.error(f"구글 스프레드시트 로드 실패: {e}")
        return None, None

df_sched, df_check = load_google_sheet(GOOGLE_SHEET_URL)

if df_sched is not None and df_check is not None:
    # 컬럼 공백 제거 및 병합셀 공백 보정 (ffill)
    df_sched.columns = df_sched.columns.str.strip()
    df_check.columns = df_check.columns.str.strip()
    df_check['Project'] = df_check['Project'].ffill()
    df_check['Gate'] = df_check['Gate'].ffill()

    # 프로젝트 선택 필터
    project_list = df_sched['Project'].dropna().unique()
    selected_project = st.selectbox("프로젝트 선택", project_list)
    
    p_rows = df_sched[df_sched['Project'] == selected_project]
    p_data = p_rows.bfill().iloc[0] if not p_rows.empty else None
    p_check = df_check[df_check['Project'] == selected_project]

    if p_data is not None:
        # 프로젝트별 체크리스트 진척도 자동 계산 및 타임라인 데이터 구축
        timeline_data = []
        today = pd.Timestamp.now().normalize()

        for i in range(1, 9):
            q_name = f"Q{i}"
            t_col = f"Q{i}_Target"
            d_col = f"Q{i}_Dead"

            target_val = p_rows[t_col].dropna()
            dead_val = p_rows[d_col].dropna()

            if not target_val.empty and not dead_val.empty:
                target_dt = pd.to_datetime(target_val.iloc[0]).replace(tzinfo=None)
                dead_dt = pd.to_datetime(dead_val.iloc[0]).replace(tzinfo=None)
                
                # 해당 Gate의 체크리스트 항목 추출 및 진척도 계산
                gate_check = p_check[p_check['Gate'].str.strip() == q_name]
                total_tasks = len(gate_check)
                progress = 0
                
                if total_tasks > 0:
                    completed_tasks = len(gate_check[gate_check['Status'].astype(str).str.strip() == "완료"])
                    progress = int((completed_tasks / total_tasks) * 100)
                
                d_day = (dead_dt - today).days
                d_day_str = f"D-{d_day}" if d_day > 0 else (f"D+{-d_day}" if d_day < 0 else "D-Day")
                
                timeline_data.append({
                    "Gate": q_name,
                    "Start": target_dt,
                    "End": dead_dt,
                    "Progress": progress,
                    "D-Day": d_day_str
                })

        if timeline_data:
            rdf = pd.DataFrame(timeline_data)

            # 상단 요약 정보
            owner_info = p_data['Owner'] if 'Owner' in p_data and pd.notnull(p_data['Owner']) else "미지정"
            st.info(f"품질담당자: {owner_info}")
            st.metric("종합 품질활동 진척률", f"{int(rdf['Progress'].mean())}%")
            st.markdown("---")
            
            # 중앙 타임라인 바 차트 출력
            st.subheader("Gate별 완료율 및 마감 현황")
            fig = px.bar(
                rdf, 
                x="Progress", 
                y="Gate", 
                text=rdf.apply(lambda r: f" {r['D-Day']} ({r['Progress']}% 완료)", axis=1),
                orientation='h',
                color="Progress",
                color_continuous_scale="YlGnBu",
                range_x=[0, 100]
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False, height=300, margin=dict(l=10, r=10, t=10, b=10))
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            st.markdown("---")

            # 하단 영역 1: Gate별 마감 일정표
            st.subheader("Gate별 마감 일정")
            display_df = rdf[["Gate", "End", "D-Day", "Progress"]].copy()
            display_df['End'] = display_df['End'].dt.strftime('%m-%d')
            display_df.columns = ["Gate", "마감일", "남은일수", "완료율(%)"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.markdown("---")

            # 하단 영역 2: 세부 활동 점검 (체크리스트)
            st.subheader("Gate별 세부 활동 상황")
            selected_gate = st.selectbox("활동을 확인할 품질 게이트 선택", rdf['Gate'].unique())
            active_check = p_check[p_check['Gate'].str.strip() == selected_gate]
            
            if len(active_check) > 0:
                show_check = active_check[["Activity", "Status"]].copy()
                show_check.columns = ["수행 활동", "상태"]
                
                def color_status(val):
                    if not isinstance(val, str):
                        return ""
                    status = val.strip()
                    if status == "완료": 
                        return "background-color: #d4edda; color: #155724;"
                    elif status == "진행중": 
                        return "background-color: #fff3cd; color: #856404;"
                    return "background-color: #f8d7da; color: #721c24;"
                    
                st.dataframe(show_check.style.map(color_status, subset=["상태"]), use_container_width=True, hide_index=True)
            else:
                st.info("해당 Gate에는 등록된 품질 활동 체크리스트가 없습니다.")
        else:
            st.warning("품질 게이트 일정 데이터가 없습니다.")
    else:
        st.warning("선택된 프로젝트의 데이터가 올바르지 않습니다.")
