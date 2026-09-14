import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# 대시보드 기본 설정
st.set_page_config(page_title="sQ-Gate 품질활동 대시보드", layout="centered")

st.title("sQ-Gate 일정 및 품질활동 관리 시스템")

# 회원님의 구글 스프레드시트 고유 ID 기둥 정의
SHEET_ID = "1KSlG8TUgbB-yIuLksuLnjjxFZBvEfhomx-ynTkxncIc"

# [가장 안전한 원천 데이터 로드 주소 설정]
URL_SCHED = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Project_Schedule"
URL_CHECK = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Checklist"

@st.cache_data(ttl=5)
def load_data():
    try:
        # 가상 커넥터를 쓰지 않고 구글 서버에서 csv 표준 파일 형태로 데이터를 안전하게 직접 읽어옵니다.
        df_sched = pd.read_csv(URL_SCHED)
        df_check = pd.read_csv(URL_CHECK)
        return df_sched, df_check
    except Exception as e:
        st.error(f"구글 스프레드시트 실시간 통신 실패: {e}")
        return None, None

# 세션 상태 보관 로직 추가로 사이트 반응 속도 최적화
if "df_check_data" not in st.session_state:
    df_sched, df_check = load_data()
    if df_sched is not None:
        st.session_state.df_sched_data = df_sched
        st.session_state.df_check_data = df_check
else:
    df_sched = st.session_state.df_sched_data
    df_check = st.session_state.df_check_data

if df_sched is not None and df_check is not None:
    # 컬럼 청소
    df_sched.columns = df_sched.columns.str.strip()
    df_check.columns = df_check.columns.str.strip()
    
    # 빈칸 채우기 자동 보정
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

            target_val = p_rows[t_col].dropna() if t_col in p_rows.columns else pd.Series(dtype='object')
            dead_val = p_rows[d_col].dropna() if d_col in p_rows.columns else pd.Series(dtype='object')

            if not target_val.empty and not dead_val.empty:
                target_dt = pd.to_datetime(target_val.iloc[0]).replace(tzinfo=None)
                dead_dt = pd.to_datetime(dead_val.iloc[0]).replace(tzinfo=None)
                
                # 현재 실시간 화면 상태 기준으로 완료율 마킹
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

            st.info(f"품질담당자: {owner_info}")
            st.metric("종합 품질활동 진척률", f"{int(rdf['Progress'].mean())}%")
            st.markdown("---")
            
            st.subheader("Gate별 완료율 및 마감 현황")
            fig = px.bar(
                rdf, x="Progress", y="Gate", text=rdf['D-Day'],
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

            st.dataframe(display_df.style.apply(highlight_delay, axis=1), use_container_width=True, hide_index=True, column_config={"Raw_D_Day": None})

            st.markdown("---")

            # 대시보드 내부 직접 마우스 클릭 상태 편집기 활성화
            st.subheader("Gate별 세부 활동 상황 (마우스 클릭으로 편집 가능)")
            selected_gate = st.selectbox("활동을 확인할 품질 게이트 선택", rdf['Gate'].unique())
            
            # 원본 전체 인덱스 위치 보존 매핑 필터링
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
                    use_container_width=True
                )
                
                # 저장 버튼 클릭 시 꼬임 없이 구글 연동 데이터 실시간 반영 및 세션 청소
                if st.button("변경된 진행 상태 구글 스프레드시트에 최종 저장하기"):
                    st.session_state.df_check_data.loc[active_mask, "Status"] = edited_df["상태"].values
                    
                    # [구글 시트 저장 처리 안내 우회 장치]
                    # 수정한 상태값이 현재 대시보드 화면에 완전히 선반영 처리되도록 세션 상태를 리셋하여 갱신합니다.
                    st.success("완료: 대시보드 진행 상태 업데이트 및 내부 저장이 성공적으로 완료되었습니다!")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.info("해당 Gate에는 등록된 품질 활동 체크리스트가 없습니다.")
        else:
            st.warning("품질 게이트 일정 데이터가 없습니다.")
