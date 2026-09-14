import streamlit as st
import pandas as pd
import plotly.express as px

# 대시보드 기본 설정
st.set_page_config(page_title="sQ-Gate 품질활동 대시보드", layout="centered")

st.title("sQ-Gate 일정 및 품질활동 관리 시스템")

# 회원님의 구글 스프레드시트 연동 주소
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1KSlG8TUgbB-yIuLksuLnjjxFZBvEfhomx-ynTkxncIc/export?format=xlsx"

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
    df_sched.columns = df_sched.columns.str.strip()
    df_check.columns = df_check.columns.str.strip()
    
    # 병합셀 및 공백 보정 (Project, Gate, Category까지 모두 자동 채우기)
    df_check['Project'] = df_check['Project'].ffill()
    df_check['Gate'] = df_check['Gate'].ffill()
    if 'Category' in df_check.columns:
        df_check['Category'] = df_check['Category'].ffill()

    project_list = df_sched['Project'].dropna().unique()
    
    if len(project_list) == 0:
        st.warning("선택할 수 있는 프로젝트가 없습니다.")
        st.stop()
        
    selected_project = st.selectbox("프로젝트 선택", project_list)
    
    p_rows = df_sched[df_sched['Project'] == selected_project]
    p_check = df_check[df_check['Project'] == selected_project]

    if not p_rows.empty:
        # 안전한 담당자 정보 추출 (오류 해결 핵심 구간)
        owner_info = "미지정"
        if 'Owner' in p_rows.columns:
            valid_owners = p_rows['Owner'].dropna()
            if not valid_owners.empty:
                owner_info = str(valid_owners.iloc[0])

        timeline_data = []
        today = pd.Timestamp.now().normalize()

        for i in range(1, 9):
            q_name = f"Q{i}"
            t_col = f"Q{i}_Target"
            d_col = f"Q{i}_Dead"

            # 해당 열이 존재하는지 안전하게 체크 후 첫 번째 값 가져오기
            target_val = p_rows[t_col].dropna() if t_col in p_rows.columns else pd.Series(dtype='object')
            dead_val = p_rows[d_col].dropna() if d_col in p_rows.columns else pd.Series(dtype='object')

            if not target_val.empty and not dead_val.empty:
                target_dt = pd.to_datetime(target_val.iloc[0]).replace(tzinfo=None)
                dead_dt = pd.to_datetime(dead_val.iloc[0]).replace(tzinfo=None)
                
                gate_check = p_check[p_check['Gate'].str.strip() == q_name]
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
                    "Gate": q_name,
                    "Start": target_dt,
                    "End": dead_dt,
                    "Progress": progress,
                    "D-Day": d_day_str,
                    "Raw_D_Day": d_day
                })

        if timeline_data:
            rdf = pd.DataFrame(timeline_data)

            st.info(f"품질담당자: {owner_info}")
            st.metric("종합 품질활동 진척률", f"{int(rdf['Progress'].mean())}%")
            st.markdown("---")
            
            st.subheader("Gate별 완료율 및 마감 현황")
            fig = px.bar(
                rdf, x="Progress", y="Gate", 
                text=rdf['D-Day'],
                orientation='h', color="Progress", color_continuous_scale="YlGnBu", range_x=[0, 100]
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False, height=300, margin=dict(l=10, r=10, t=10, b=10))
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            st.markdown("---")

            st.subheader("Gate별 마감 일정")
            display_df = rdf[["Gate", "End", "D-Day", "Progress", "Raw_D_Day"]].copy()
            display_df['End'] = display_df['End'].dt.strftime('%m-%d')
            display_df.columns = ["Gate", "마감일", "남은일수", "완료율(%)", "Raw_D_Day"]

            def highlight_delay(row):
                styles = [''] * len(row)
                if row['Raw_D_Day'] < 0 and row['완료율(%)'] < 100:
                    styles = ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
                return styles

            st.dataframe(
                display_df.style.apply(highlight_delay, axis=1), 
                use_container_width=True, 
                hide_index=True,
                column_config={"Raw_D_Day": None}
            )

            st.markdown("---")

            # 하단 영역 2: 세부 활동 점검 (상위 카테고리 포함)
            st.subheader("Gate별 세부 활동 상황")
            selected_gate = st.selectbox("활동을 확인할 품질 게이트 선택", rdf['Gate'].unique())
            active_check = p_check[p_check['Gate'].str.strip() == selected_gate]
            
            if len(active_check) > 0:
                show_check = active_check[["Category", "Activity", "Status"]].copy()
                show_check['Status'] = show_check['Status'].fillna("대기")
                show_check.columns = ["상위 카테고리", "수행 활동", "상태"]
                
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
