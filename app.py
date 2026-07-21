import streamlit as st
from supabase import create_client, Client
from streamlit_calendar import calendar
from datetime import datetime, date, time

# 1. Supabaseクライアントの初期化
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# 2. セッションステートの初期化
if "user" not in st.session_state:
    st.session_state.user = None

# 3. 認証インターフェース
if st.session_state.user is None:
    st.subheader("ログイン")
    email = st.text_input("メールアドレス")
    password = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception as e:
            st.error(f"ログインエラー詳細: {e}")
    st.stop()

# --- ログイン済みのユーザーのみ実行 ---
col_head1, col_head2 = st.columns([3, 1])
with col_head1:
    st.write(f"ログイン中: {st.session_state.user.email}")
with col_head2:
    if st.button("ログアウト"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()
st.divider()

# --- ダイアログ（ポップアップ）機能の定義 ---

@st.dialog("予定リスト")
def show_schedule_list(start_d, end_d, db_data):
    st.write(f"期間: {start_d} 〜 {end_d}")
    filtered_events = []
    for row in db_data:
        row_date = datetime.fromisoformat(row["start_datetime"]).date()
        if start_d <= row_date <= end_d:
            filtered_events.append(row)
    
    filtered_events.sort(key=lambda x: x["start_datetime"])
    
    if not filtered_events:
        st.write("指定された期間内に予定はありません。")
    else:
        for ev in filtered_events:
            s_dt = datetime.fromisoformat(ev["start_datetime"]).strftime('%Y-%m-%d %H:%M')
            e_dt = datetime.fromisoformat(ev["end_datetime"]).strftime('%Y-%m-%d %H:%M')
            st.markdown(f"- **{s_dt} 〜 {e_dt}** : {ev['title']} ({ev['result']})")

@st.dialog("詳細・感想の入力", width="large")
def edit_reflections(event_id, current_reflections):
    ref = current_reflections if current_reflections else {}
    
    with st.form("reflection_form"):
        st.subheader("インターン内容")
        r_datetime = st.text_input("日時", value=ref.get("datetime", ""))
        r_work = st.text_area("どのようなワークを行ったか", value=ref.get("work", ""))
        r_impression = st.text_area("インターンの簡単な感想（どこが自分とあっているor向いていたか）", value=ref.get("impression", ""))
        
        st.subheader("会社について")
        r_strength = st.text_area("自分が感じた会社の強み(強調されていたもの)", value=ref.get("strength", ""))
        r_candidate = st.text_area("求める人物像の具体的な内容", value=ref.get("candidate", ""))
        r_competitor = st.text_area("競合他社", value=ref.get("competitor", ""))
        r_future = st.text_area("今後の注力事業", value=ref.get("future", ""))
        r_gap = st.text_area("インターン前後のイメージ", value=ref.get("gap", ""))
        
        st.subheader("学生について")
        r_level = st.text_area("学生のレベル感", value=ref.get("level", ""))
        r_excellent = st.text_area("優秀と感じた学生の特徴", value=ref.get("excellent", ""))
        r_average = st.text_area("平均的な学生の特徴", value=ref.get("average", ""))
        r_role = st.text_area("学生の中の自分の役割", value=ref.get("role", ""))
        
        st.subheader("社員について")
        r_schedule = st.text_area("1日のスケジュール、業務内容", value=ref.get("schedule", ""))
        r_emp_type = st.text_area("どんな社員が多いか", value=ref.get("emp_type", ""))
        r_rewarding = st.text_area("一番つらいorやりがいを感じる仕事", value=ref.get("rewarding", ""))
        r_stakeholder = st.text_area("業務のステークホルダー、かかわる人", value=ref.get("stakeholder", ""))
        
        if st.form_submit_button("感想を保存"):
            new_reflections = {
                "datetime": r_datetime, "work": r_work, "impression": r_impression,
                "strength": r_strength, "candidate": r_candidate, "competitor": r_competitor,
                "future": r_future, "gap": r_gap,
                "level": r_level, "excellent": r_excellent, "average": r_average, "role": r_role,
                "schedule": r_schedule, "emp_type": r_emp_type, "rewarding": r_rewarding, "stakeholder": r_stakeholder
            }
            supabase.table("internships").update({"reflections": new_reflections}).eq("id", event_id).execute()
            st.success("感想を保存しました。")
            st.rerun()

# 4. データの取得
response = supabase.table("internships").select("*").execute()
db_data = response.data

# --- 任意の期間のリストアップ表示 ---
st.subheader("予定のリストアップ")
col_d1, col_d2, col_d3 = st.columns([2, 2, 1])
with col_d1:
    filter_start = st.date_input("開始日を選択", value=date.today(), key="filter_s")
with col_d2:
    filter_end = st.date_input("終了日を選択", value=date.today(), key="filter_e")
with col_d3:
    st.write("")
    st.write("")
    if st.button("リストを表示"):
        show_schedule_list(filter_start, filter_end, db_data)

st.divider()

# --- カスタムCSSの注入（取り消し線とグレーアウトの設定） ---
st.markdown("""
<style>
/* 不合格・辞退の予定に対するスタイル */
.cancelled-event .fc-event-title,
.cancelled-event .fc-event-time,
.cancelled-event .fc-event-main {
    text-decoration: line-through;
}
</style>
""", unsafe_allow_html=True)

# カレンダー用データ構造の構築
events = []
for row in db_data:
    is_cancelled = row["result"] in ["不合格", "辞退"]
    
    events.append({
        "id": str(row["id"]),
        "title": row["title"],
        "start": row["start_datetime"],
        "end": row["end_datetime"],
        "className": ["cancelled-event"] if is_cancelled else [],
        "backgroundColor": "#a9a9a9" if is_cancelled else "#3788d8",
        "borderColor": "#a9a9a9" if is_cancelled else "#3788d8",
        "extendedProps": {
            "content": row["content"],
            "result": row["result"],
            "reflections": row["reflections"]
        }
    })

# --- カレンダー表示日を移動するUIの追加 ---
jump_date = st.date_input("カレンダーの表示日を移動", value=date.today())

# カレンダー表示設定（24時間表記および表示日移動に対応）
cal_options = {
    "initialView": "dayGridMonth",
    "initialDate": jump_date.isoformat(), # 指定した日付をカレンダーの初期表示日とする
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
    },
    "slotLabelFormat": {
        "hour": "2-digit",
        "minute": "2-digit",
        "hour12": False
    },
    "eventTimeFormat": {
        "hour": "2-digit",
        "minute": "2-digit",
        "hour12": False
    }
}
calendar_result = calendar(events=events, options=cal_options)

# 5. カレンダーのクリックイベント処理
if "eventClick" in calendar_result and calendar_result["eventClick"]:
    clicked_event = calendar_result["eventClick"]["event"]
    props = clicked_event.get("extendedProps", {})
    event_id = clicked_event["id"]
    
    st.subheader(f"{clicked_event['title']}")
    
    s_time = datetime.fromisoformat(clicked_event['start']).strftime('%Y-%m-%d %H:%M')
    e_time = datetime.fromisoformat(clicked_event['end']).strftime('%Y-%m-%d %H:%M')
    st.write(f"**日時:** {s_time} 〜 {e_time}")
    st.write(f"**基本内容:** {props.get('content', '')}")
    st.write(f"**合否:** {props.get('result', '')}")
    
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("感想を入力・編集する"):
            edit_reflections(event_id, props.get("reflections", {}))
    with col_act2:
        if st.button("この予定を削除"):
            supabase.table("internships").delete().eq("id", event_id).execute()
            st.rerun()

st.divider()

# 6. 新規予定の登録フォーム
st.subheader("新規予定の登録（基本情報）")
with st.form("add_event_form"):
    new_title = st.text_input("インターン名 / 予定名")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        new_start_d = st.date_input("開始日")
        new_start_t = st.time_input("開始時間", value=time(9, 0))
    with col_t2:
        new_end_d = st.date_input("終了日")
        new_end_t = st.time_input("終了時間", value=time(18, 0))
        
    new_content = st.text_area("内容 (前泊・移動などのメモ)")
    new_result = st.selectbox("合否", ["未定", "合格", "不合格", "辞退"])
    
    if st.form_submit_button("予定を登録"):
        start_dt = datetime.combine(new_start_d, new_start_t).isoformat()
        end_dt = datetime.combine(new_end_d, new_end_t).isoformat()
        
        insert_data = {
            "user_id": st.session_state.user.id,
            "title": new_title,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "content": new_content,
            "result": new_result,
            "reflections": {}
        }
        supabase.table("internships").insert(insert_data).execute()
        st.success("予定を登録しました。")
        st.rerun()