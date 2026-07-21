import streamlit as st
from supabase import create_client, Client
from streamlit_calendar import calendar
from datetime import datetime, timedelta

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
if "edit_target_id" not in st.session_state:
    st.session_state.edit_target_id = None

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

st.write(f"ログイン中: {st.session_state.user.email}")
if st.button("ログアウト"):
    supabase.auth.sign_out()
    st.session_state.user = None
    st.rerun()

st.divider()

# --- ポップアップ（ダイアログ）機能の定義 ---
@st.dialog("予定リスト")
def show_schedule_list(period_days: int, db_data: list):
    today = datetime.today().date()
    end_date = today + timedelta(days=period_days)
    
    st.write(f"今日（{today}）から {period_days} 日間の予定")
    
    # 指定期間内の予定を抽出
    filtered_events = []
    for row in db_data:
        start_date_obj = datetime.strptime(row["start_date"], "%Y-%m-%d").date()
        if today <= start_date_obj <= end_date:
            filtered_events.append(row)
    
    # 抽出した予定を昇順でソートして表示
    filtered_events.sort(key=lambda x: x["start_date"])
    
    if not filtered_events:
        st.write("予定はありません。")
    else:
        for ev in filtered_events:
            period_str = f"{ev['start_date']}"
            if ev['end_date'] and ev['end_date'] != ev['start_date']:
                period_str += f" 〜 {ev['end_date']}"
            st.markdown(f"- **{period_str}** : {ev['title']} ({ev['result']})")

# 4. データの取得
response = supabase.table("internships").select("*").execute()
db_data = response.data

# --- リストアップ表示ボタン ---
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("1週間の予定リストを表示"):
        show_schedule_list(7, db_data)
with col_btn2:
    if st.button("1ヶ月の予定リストを表示"):
        show_schedule_list(30, db_data)

# カレンダー用データ構造の構築（主キー id を含める）
events = []
for row in db_data:
    events.append({
        "id": str(row["id"]), # DBの主キー
        "title": row["title"],
        "start": row["start_date"],
        "end": row["end_date"] if row["end_date"] else row["start_date"],
        "extendedProps": {
            "content": row["content"],
            "result": row["result"],
            "impression": row["impression"]
        }
    })

# カレンダー表示
calendar_result = calendar(events=events, options={"initialView": "dayGridMonth"})

# 5. カレンダーのクリックイベント処理（詳細表示・編集・削除）
if "eventClick" in calendar_result and calendar_result["eventClick"]:
    clicked_event = calendar_result["eventClick"]["event"]
    props = clicked_event.get("extendedProps", {})
    event_id = clicked_event["id"]
    
    st.subheader(f"{clicked_event['title']}")
    st.write(f"**内容:** {props.get('content', '')}")
    st.write(f"**合否:** {props.get('result', '')}")
    st.write(f"**感想:** {props.get('impression', '')}")
    
    # 編集・削除ボタン
    col1, col2 = st.columns(2)
    with col1:
        if st.button("この予定を編集"):
            st.session_state.edit_target_id = event_id
    with col2:
        if st.button("この予定を削除"):
            supabase.table("internships").delete().eq("id", event_id).execute()
            st.session_state.edit_target_id = None
            st.rerun()

    # 編集フォームの表示
    if st.session_state.edit_target_id == event_id:
        st.divider()
        st.write("■ 編集モード")
        
        # 既存データの抽出（初期値設定用）
        target_row = next((item for item in db_data if str(item["id"]) == event_id), None)
        
        if target_row:
            with st.form("edit_event_form"):
                edit_title = st.text_input("インターン名", value=target_row["title"])
                edit_start = st.date_input("開始日", value=datetime.strptime(target_row["start_date"], "%Y-%m-%d").date())
                
                # 終了日の初期値設定
                default_end = target_row["end_date"]
                if default_end:
                    default_end_val = datetime.strptime(default_end, "%Y-%m-%d").date()
                else:
                    default_end_val = datetime.strptime(target_row["start_date"], "%Y-%m-%d").date()
                edit_end = st.date_input("終了日", value=default_end_val)
                
                edit_content = st.text_area("内容", value=target_row["content"] or "")
                
                # 合否セレクトボックスの初期値設定
                options = ["未定", "合格", "不合格", "辞退"]
                default_index = options.index(target_row["result"]) if target_row["result"] in options else 0
                edit_result = st.selectbox("合否", options, index=default_index)
                
                edit_impression = st.text_area("感想", value=target_row["impression"] or "")
                
                if st.form_submit_button("更新を保存"):
                    update_data = {
                        "title": edit_title,
                        "start_date": str(edit_start),
                        "end_date": str(edit_end),
                        "content": edit_content,
                        "result": edit_result,
                        "impression": edit_impression
                    }
                    supabase.table("internships").update(update_data).eq("id", event_id).execute()
                    st.session_state.edit_target_id = None
                    st.success("更新しました。")
                    st.rerun()
        if st.button("編集をキャンセル"):
            st.session_state.edit_target_id = None
            st.rerun()

st.divider()

# 6. 新規予定の登録フォーム
st.subheader("新規予定の登録")
with st.form("add_event_form"):
    new_title = st.text_input("インターン名")
    new_start = st.date_input("開始日")
    new_end = st.date_input("終了日")
    new_content = st.text_area("内容")
    new_result = st.selectbox("合否", ["未定", "合格", "不合格", "辞退"])
    new_impression = st.text_area("感想")
    
    if st.form_submit_button("登録"):
        insert_data = {
            "user_id": st.session_state.user.id,
            "title": new_title,
            "start_date": str(new_start),
            "end_date": str(new_end),
            "content": new_content,
            "result": new_result,
            "impression": new_impression
        }
        supabase.table("internships").insert(insert_data).execute()
        st.success("登録が完了しました。")
        st.rerun()