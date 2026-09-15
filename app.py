import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# 대시보드 기본 설정
st.set_page_config(page_title="sQ-Gate 종합 마일스톤 대시보드", layout="wide")
st.title("sQ-Gate 통합 일정 및 품질활동 관리 시스템")
st.markdown("<br><br>", unsafe_allow_html=True)
SHEET_ID = "1KSlG8TUgbB-yIuLksuLnjjxFZBvEfhomx-ynTkxncIc"
URL_BASE = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"

@st.cache_data(ttl=5)
def load_data():
    try:
        response = requests.get(URL_BASE, timeout=10)
        if response.status_code == 200:
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
    # 전 프로젝트 통합 달력형 타임라인 보기
    # ------------------------------------------------------------------
    col_todo, col_cal = st.columns([1.8, 1.2])

    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"] {
            align-items: flex-start !important;
        }
        div[data-testid="column"]:nth-of-type(2) {
            margin-top: 0px !important;
            padding-top: 0px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    with col_todo:        
        # 1. 세션 상태 초기화
        if "todo_notes" not in st.session_state:
            st.session_state.todo_notes = ["점심먹기", "저녁먹기", "퇴근하기", "책읽기", "글쓰기"]
        if "todo_status" not in st.session_state:
            st.session_state.todo_status = [True, False, False, False, False]

        # 클릭 이벤트 처리 (쿼리 파라미터 방식을 활용해 순수 HTML 버튼 클릭 감지)
        query_params = st.query_params
        if "toggle_idx" in query_params:
            clicked_idx = int(query_params["toggle_idx"])
            st.session_state.todo_status[clicked_idx] = not st.session_state.todo_status[clicked_idx]
            st.query_params.clear()
            st.rerun()

        # 2. 메모 입력 영역 (세로 여백 최소화형 팝오버)
        with st.popover("오늘의 할 일 입력 및 수정하기", use_container_width=True):
            st.markdown("##### 5개의 할 일을 입력하세요")
            new_notes = []
            for idx in range(5):
                note = st.text_input(
                    f"{idx+1}번 할 일", 
                    value=st.session_state.todo_notes[idx], 
                    key=f"edit_note_{idx}"
                )
                new_notes.append(note)
            
            if st.button("저장 후 반영하기", use_container_width=True):
                st.session_state.todo_notes = new_notes
                st.success("메모가 대시보드에 반영되었습니다.")
                st.rerun()

        st.markdown("<div style='margin-bottom: 5px;'></div>", unsafe_allow_html=True)

        # 3. HTML/CSS 기반 초박형 컴팩트 리스트 출력
        for idx in range(5):
            current_note = st.session_state.todo_notes[idx]
            if not current_note.strip():
                current_note = f"할 일 {idx+1} (내용을 입력해 주세요)"
                
            is_done = st.session_state.todo_status[idx]
            
            status_text = "진행완료" if is_done else "미진행"
            status_color = "#2E7D32" if is_done else "#D32F2F"
            bg_color = "#E8F5E9" if is_done else "#FFEBEE"
            border_color = "#A5D6A7" if is_done else "#EF9A9A"

            st.markdown(
                f"""
                <a href="?toggle_idx={idx}" target="_self" style="text-decoration: none; display: block;">
                    <div style="
                        background-color: {bg_color}; 
                        color: {status_color}; 
                        border: 1px solid {border_color}; 
                        border-radius: 6px; 
                        padding: 6px 12px; 
                        margin-bottom: 4px; 
                        font-weight: bold; 
                        font-size: 14px; 
                        text-align: center;
                        box-shadow: 0px 1px 2px rgba(0,0,0,0.05);
                    ">
                        {status_text} : {current_note}
                    </div>
                </a>
                """,
                unsafe_allow_html=True
            )
        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
     
    with col_cal:
        now_dt = pd.Timestamp.now(tz='Asia/Seoul').replace(tzinfo=None)
        current_year = now_dt.year
        current_day = now_dt.day

        query_params = st.query_params
        
        if "view_schedule" in query_params:
            # ------------------------------------------------------------------
            # [새 창 레이아웃] 달력 클릭 시 열리는 단독 시간별 일정 관리 창
            # ------------------------------------------------------------------
            selected_day = int(query_params.get("view_schedule", current_day))
            st.markdown(f"### {selected_day}일 시간별 일정 관리 전용 창")
            
            if "cal_toggle_hour" in query_params:
                t_hour = query_params["cal_toggle_hour"]
                state_key = f"cal_status_{selected_day}_{t_hour}"
                if state_key not in st.session_state:
                    st.session_state[state_key] = False
                st.session_state[state_key] = not st.session_state[state_key]
                st.query_params.clear()
                st.query_params["view_schedule"] = selected_day
                st.rerun()

            st.markdown('<a href="?" target="_self" style="text-decoration:none;"><div style="background-color:#616161; color:white; text-align:center; padding:6px; border-radius:6px; margin-bottom:15px; font-size:13px; font-weight:bold;">메인 대시보드로 돌아가기</div></a>', unsafe_allow_html=True)

            hours_list = [f"{str(h).zfill(2)}:00" for h in range(6, 24)] + ["00:00", "01:00", "02:00"]
            
            current_hour_now = now_dt.hour
            current_min_now = now_dt.minute
            now_absolute_mins = current_hour_now * 60 + current_min_now
            if current_hour_now < 6:
                now_absolute_mins += 24 * 60

            mock_events = {
                15: {"08:00": "수출TFT 주간점검회의", "09:00": "장거리레이더 양산이관 회의"},
                16: {"08:00": "TCG 기본셀조립체 후속조치", "14:00": "보건상담"},
            }
            day_events = mock_events.get(selected_day, {})

            for h_str in hours_list:
                event_text = day_events.get(h_str, "일정 없음")
                state_key = f"cal_status_{selected_day}_{h_str}"
                
                if state_key not in st.session_state:
                    st.session_state[state_key] = False
                    
                is_done = st.session_state[state_key]
                
                target_hour = int(h_str.split(":"))
                target_absolute_mins = target_hour * 60
                if target_hour < 6:
                    target_absolute_mins += 24 * 60
                
                if is_done:
                    bg_c = "#E8F5E9"; text_c = "#2E7D32"; border_c = "#A5D6A7"; status_lbl = "완료"
                elif selected_day == now_dt.day and target_absolute_mins < now_absolute_mins:
                    bg_c = "#FFEBEE"; text_c = "#D32F2F"; border_c = "#EF9A9A"; status_lbl = "지남"
                else:
                    bg_c = "#F5F5F5"; text_c = "#616161"; border_c = "#E0E0E0"; status_lbl = "대기"

                st.markdown(
                    f"""
                    <a href="?view_schedule={selected_day}&cal_toggle_hour={h_str}" target="_self" style="text-decoration: none; display: block; margin-bottom: 4px;">
                        <div style="display: flex; justify-content: space-between; background-color: {bg_c}; color: {text_c}; border: 1px solid {border_c}; border-radius: 5px; padding: 6px 10px; font-size: 13px;">
                            <span style="font-weight: bold;">[{h_str}] {event_text}</span>
                            <span style="font-size: 11px; background-color: rgba(255,255,255,0.5); padding: 0 5px; border-radius:3px;">{status_lbl}</span>
                        </div>
                    </a>
                    """,
                    unsafe_allow_html=True
                )
        else:
            # ------------------------------------------------------------------
            # [기본 메인 화면] 평소에는 미니 달력만 깔끔하게 노출
            # ------------------------------------------------------------------
            st.markdown(
                f"""
                <div style="background-color: #F8F9FA; padding: 15px; border-radius: 15px; 
                            box-shadow: 0px 4px 10px rgba(0,0,0,0.05); text-align: center; border: 1px solid #E0E0E0;">
                    <div style="font-weight: bold; color: #666; margin-bottom: 10px; font-size: 16px;">
                        &lt;&lt; &lt; SEP, {current_year} &gt; &gt;&gt;
                    </div>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <tr style="color: #666; font-weight: bold;">
                            <th style="color: #E53935; padding: 5px;">Sun</th><th>Mon</th><th>Tue</th><th>Wed</th><th>Thu</th><th>Fri</th><th style="color: #1E88E5;">Sat</th>
                        </tr>
                        <tr style="color: #444;">
                            <td></td><td></td>
                            <td><a href="?view_schedule=1" target="_blank" style="text-decoration:none; color:#AAA;">1</a></td>
                            <td><a href="?view_schedule=2" target="_blank" style="text-decoration:none; color:#AAA;">2</a></td>
                            <td><a href="?view_schedule=3" target="_blank" style="text-decoration:none; color:#AAA;">3</a></td>
                            <td><a href="?view_schedule=4" target="_blank" style="text-decoration:none; color:#AAA;">4</a></td>
                            <td><a href="?view_schedule=5" target="_blank" style="text-decoration:none; color:#1E88E5;">5</a></td>
                        </tr>
                        <tr style="color: #444;">
                            <td><a href="?view_schedule=6" target="_blank" style="text-decoration:none; color:#E53935;">6</a></td>
                            <td><a href="?view_schedule=7" target="_blank" style="text-decoration:none; color:#444;">7</a></td>
                            <td><a href="?view_schedule=8" target="_blank" style="text-decoration:none; color:#444;">8</a></td>
                            <td><a href="?view_schedule=9" target="_blank" style="text-decoration:none; color:#444;">9</a></td>
                            <td><a href="?view_schedule=10" target="_blank" style="text-decoration:none; color:#444;">10</a></td>
                            <td><a href="?view_schedule=11" target="_blank" style="text-decoration:none; color:#444;">11</a></td>
                            <td><a href="?view_schedule=12" target="_blank" style="text-decoration:none; color:#1E88E5;">12</a></td>
                        </tr>
                        <tr style="color: #444;">
                            <td><a href="?view_schedule=13" target="_blank" style="text-decoration:none; color:#E53935;">13</a></td>
                            <td><a href="?view_schedule=14" target="_blank" style="text-decoration:none; color:#444;">14</a></td>
                            <td style="background-color: #E8F5E9; border: 1px solid #2E7D32; border-radius: 4px; font-weight: bold;">
                                <a href="?view_schedule=15" target="_blank" style="text-decoration:none; color:#2E7D32; font-weight:bold;">15</a>
                            </td>
                            <td><a href="?view_schedule=16" target="_blank" style="text-decoration:none; color:#444;">16</a></td>
                            <td><a href="?view_schedule=17" target="_blank" style="text-decoration:none; color:#444;">17</a></td>
                            <td><a href="?view_schedule=18" target="_blank" style="text-decoration:none; color:#444;">18</a></td>
                            <td><a href="?view_schedule=19" target="_blank" style="text-decoration:none; color:#1E88E5;">19</a></td>
                        </tr>
                        <tr style="color: #444;">
                            <td><a href="?view_schedule=20" target="_blank" style="text-decoration:none; color:#E53935;">20</a></td>
                            <td><a href="?view_schedule=21" target="_blank" style="text-decoration:none; color:#444;">21</a></td>
                            <td><a href="?view_schedule=22" target="_blank" style="text-decoration:none; color:#444;">22</a></td>
                            <td><a href="?view_schedule=23" target="_blank" style="text-decoration:none; color:#444;">23</a></td>
                            <td><a href="?view_schedule=24" target="_blank" style="text-decoration:none; color:#444;">24</a></td>
                            <td><a href="?view_schedule=25" target="_blank" style="text-decoration:none; color:#444;">25</a></td>
                            <td><a href="?view_schedule=26" target="_blank" style="text-decoration:none; color:#1E88E5;">26</a></td>
                        </tr>
                        <tr style="color: #444;">
                            <td><a href="?view_schedule=27" target="_blank" style="text-decoration:none; color:#E53935;">27</a></td>
                            <td><a href="?view_schedule=28" target="_blank" style="text-decoration:none; color:#444;">28</a></td>
                            <td><a href="?view_schedule=29" target="_blank" style="text-decoration:none; color:#444;">29</a></td>
                            <td><a href="?view_schedule=30" target="_blank" style="text-decoration:none; color:#444;">30</a></td>
                            <td></td><td></td><td></td>
                        </tr>
                    </table>
                </div>
                """, 
                unsafe_allow_html=True
            )

        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

        # 3. [신규 기능] 선택된 날짜의 06:00 ~ 02:00 시간별 일정 타임라인 출력 영역
        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

        # 3. [수정 반영] 달력을 클릭했을 때만(cal_day 파라미터가 감지될 때만) 화면에 표시
        if "cal_day" in query_params:
            st.markdown(f"##### {selected_day}일 시간별 일정 관리")
            
            # 06:00부터 다음 날 02:00까지의 시간 배열 구성
            hours_list = [f"{str(h).zfill(2)}:00" for h in range(6, 24)] + ["00:00", "01:00", "02:00"]
            
            # [시간 계산 보정] 온라인 서버 시간 기준 현재 시각 객체 생성
            now_dt = pd.Timestamp.now()
            current_hour_now = now_dt.hour
            current_min_now = now_dt.minute
            
            # 현재 시각을 6시 시작 기준의 절대 분(Minute) 수치로 환산하여 완벽하게 비교합니다.
            now_absolute_mins = current_hour_now * 60 + current_min_now
            if current_hour_now < 6:  # 00시, 01시, 02시는 다음 날로 계산하기 위해 24시간을 더함
                now_absolute_mins += 24 * 60

            # 날짜별 더미 일정 데이터 맵
            mock_events = {
                15: {"08:00": "수출TFT 주간점검회의", "09:00": "장거리레이더 양산이관 회의"},
                16: {"08:00": "TCG 기본셀조립체 후속조치", "14:00": "보건상담"},
            }
            day_events = mock_events.get(selected_day, {})

            st.markdown(
                """
                <div style="max-height: 250px; overflow-y: auto; border: 1px solid #E0E0E0; border-radius: 8px; padding: 5px; background-color: #FFFFFF;">
                """, 
                unsafe_allow_html=True
            )

            for h_str in hours_list:
                event_text = day_events.get(h_str, "일정 없음")
                state_key = f"cal_status_{selected_day}_{h_str}"
                
                if state_key not in st.session_state:
                    st.session_state[state_key] = False
                    
                is_done = st.session_state[state_key]
                
                # 리스트의 대상 시간대를 분(Minute) 수치로 환산
                target_hour = int(h_str.split(":")[0])
                target_absolute_mins = target_hour * 60
                if target_hour < 6:
                    target_absolute_mins += 24 * 60
                
                # 스타일 및 상태 분기 조건문 (분 단위까지 철저하게 대조)
                if is_done:
                    bg_c = "#E8F5E9"
                    text_c = "#2E7D32"
                    border_c = "#A5D6A7"
                    status_lbl = "완료"
                elif selected_day == now_dt.day and target_absolute_mins < now_absolute_mins:
                    # 현재 실제 시간보다 과거인 경우만 빨간색(지남) 처리
                    bg_c = "#FFEBEE"
                    text_c = "#D32F2F"
                    border_c = "#EF9A9A"
                    status_lbl = "지남"
                else:
                    # 아직 오지 않은 미래 시간대는 정상적으로 회색(대기) 처리
                    bg_c = "#F5F5F5"
                    text_c = "#616161"
                    border_c = "#E0E0E0"
                    status_lbl = "대기"

                st.markdown(
                    f"""
                    <a href="?cal_day={selected_day}&cal_toggle_hour={h_str}" target="_self" style="text-decoration: none; display: block; margin-bottom: 3px;">
                        <div style="
                            display: flex;
                            justify-content: space-between;
                            background-color: {bg_c}; 
                            color: {text_c}; 
                            border: 1px solid {border_c}; 
                            border-radius: 4px; 
                            padding: 4px 8px; 
                            font-size: 12px;
                        ">
                            <span style="font-weight: bold;">[{h_str}] {event_text}</span>
                            <span style="font-size: 11px; background-color: rgba(255,255,255,0.5); padding: 0 4px; border-radius:3px;">{status_lbl}</span>
                        </div>
                    </a>
                    """,
                    unsafe_allow_html=True
                )
                
            st.markdown("</div>", unsafe_allow_html=True)
    
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
        
        # 1. 기본 타임라인 차트 생성
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
        fig_all.add_vline(x=today, line_width=2, line_dash="dash", line_color="red")
        fig_all.update_yaxes(autorange="reversed")
        
        # 공통 스타일 정의 (정중앙 정렬 및 흰색/굵게)
        fig_all.update_traces(
            textposition="inside",
            insidetextanchor="middle",
            texttemplate="<b>%{text}</b>",
            textfont=dict(color="white", size=12)
        )

        # -----------------------------------------------------------
        # [핵심] 자바스크립트를 이용해 현재 브라우저의 화면 너비(Width) 체크
        # -----------------------------------------------------------
        # 사용자의 화면 폭을 실시간으로 가져오는 컴포넌트 뷰포트 설정
        from streamlit_js_eval import streamlit_js_eval
        screen_width = streamlit_js_eval(js_expressions="window.innerWidth", key="WIDTH_CHECK")

        # 화면 너비를 가져오는 중이거나, 화면 폭이 768px 이하인 경우 (모바일)
        if screen_width is not None and screen_width <= 768:
            # 모바일 특화 레이아웃 적용
            fig_all.update_traces(width=0.6)  # 막대 두껍게
            fig_all.update_layout(
                height=180,
                margin=dict(l=10, r=5, t=30, b=10),
                showlegend=False  # 모바일은 범례 숨김
            )
            fig_all.update_yaxes(tickfont=dict(size=11))
        else:
            # PC/태블릿 기본 레이아웃 유지
            fig_all.update_layout(
                height=250,
                margin=dict(l=10, r=10, t=40, b=10),
                showlegend=True   # PC는 범례 표시
            )
            
        # -----------------------------------------------------------
        # [새로운 기능] 확대 기능 차단 및 마우스 드래그 시 좌우 이동(Pan) 설정
        # -----------------------------------------------------------
        fig_all.update_layout(
            dragmode="pan",  # 마우스 드래그 기본 동작을 확대(zoom)에서 이동(pan)으로 변경
            xaxis=dict(
                fixedrange=False  # X축(날짜축)은 드래그로 이동이 가능하게 허용
            ),
            yaxis=dict(
                fixedrange=True   # Y축(프로젝트명)은 위아래로 움직이거나 확대되지 않도록 고정
            )
        )
        
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
                owner_info = str(valid_owners.iloc[0])

        timeline_data = []

        for i in range(1, 9):
            q_name = f"Q{i}"
            t_col = f"Q{i}_Target"
            d_col = f"Q{i}_Dead"

            target_val = p_rows[t_col].dropna() if t_col in p_rows.columns else pd.Series(dtype='object')
            dead_val = p_rows[d_col].dropna() if d_col in p_rows.columns else pd.Series(dtype='object')

            if not target_val.empty and not dead_val.empty:
                target_dt = pd.to_datetime(target_val.iloc[0]).replace(tzinfo=None)
                dead_dt = pd.to_datetime(dead_val.iloc[0]).replace(tzinfo=None)
                
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
                    "Gate": q_name, "Start": target_dt, "End": dead_dt, "Progress": progress, "D-Day": d_day_str, "Raw_D_Day": d_day,
                    "프로젝트": selected_project  # 개별 플로팅용 키 추가
                })

        if timeline_data:
            rdf = pd.DataFrame(timeline_data)

            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.info(f"품질담당자: {owner_info}")
            with col_info2:
                st.metric("선택 프로젝트 종합 진척률", f"{int(rdf['Progress'].mean())}%")
            
            # [기능 2번 추가] 선택한 개별 프로젝트의 전용 타임라인 달력 표시 영역
            st.markdown(f"##### 📅 {selected_project} 개별 마일스톤 일정 열람")
            fig_single = px.timeline(
                rdf,
                x_start="Start",
                x_end="End",
                y="Gate",
                color="Gate",
                text="Gate",
                hover_data=["Progress", "D-Day"],
                color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_single.add_vline(x=today, line_width=2, line_dash="dash", line_color="red")
            fig_single.update_yaxes(autorange="reversed")
            
            # [기능 1번 적용] 개별 그래프 내부 글자 정렬 및 흰색/굵게 스타일링
            fig_single.update_traces(
                textposition="inside",
                insidetextanchor="middle",
                texttemplate="<b>%{text}</b>",  # HTML <b> 태그로 텍스트를 강제로 굵게 만듦
                textfont=dict(
                    color="white",
                    size=13
                )
            )
            fig_single.update_layout(
                height=180, 
                margin=dict(l=10, r=10, t=10, b=10), 
                showlegend=False,
                dragmode="pan",      # 마우스 드래그 기본 동작을 좌우 이동으로 변경
                xaxis=dict(
                    fixedrange=False # X축(날짜)은 좌우 드래그 이동 허용
                ),
                yaxis=dict(
                    fixedrange=True  # Y축(Gate 명칭)은 확대 및 위아래 이동 차단
                )
            )
            st.plotly_chart(fig_single, use_container_width=True, config={'displayModeBar': False})
            
            #이 아래부터는 기존에 가지고 계시던 코드가 그대로 이어집니다.
            st.markdown("<br>", unsafe_allow_html=True)

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
