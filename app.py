import streamlit as st
import requests
import json
import time
import base64
import uuid
import os
import re
import pandas as pd  # 需要 pandas 处理表格
from datetime import datetime

# ==========================================
# 🔐 1. 账号管理配置
# ==========================================
USERS = {
    "admin": "admin888",  # 管理员账号
    "guest": "123456",
    "vip": "vip666"
}

# 默认额度配置
DEFAULT_QUOTA = 20

# ==========================================
# 🔧 2. 系统配置
# ==========================================
try:
    API_KEY = st.secrets.get("API_KEY", "sk-hr1jWTbl00qsSrKY6mGf6H8GTTV5Zh0jkzjYb2z7igv9CRcg")
except FileNotFoundError:
    API_KEY = "sk-hr1jWTbl00qsSrKY6mGf6H8GTTV5Zh0jkzjYb2z7igv9CRcg"

BASE_URL = "https://xinyuanai666.com"
VIDEO_CREATE_URL = f"{BASE_URL}/v1/video/create"
VIDEO_QUERY_URL = f"{BASE_URL}/v1/video/query" 
VIDEO_MODEL = "veo3.1-components"
CHAT_URL = f"{BASE_URL}/v1/chat/completions"
CHAT_MODEL = "gemini-3-flash-preview" 
IMAGE_MODEL = "gemini-3-pro-image-preview"

# 云端存储 ID
JSONBLOB_ID = "019b8e81-d5d4-7220-81e8-7ea251e98c38"

# ==========================================
# 💾 3. 数据持久化核心
# ==========================================

def load_all_data():
    """从云端加载所有用户的数据"""
    url = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"
    headers = {
        "Content-Type": "application/json", 
        "Accept": "application/json",
        "User-Agent": "StreamlitApp/1.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {}
    except Exception as e:
        print(f"云端加载失败: {e}")
        return {}

def save_current_user_data():
    """普通用户保存：只更新自己的数据"""
    if not st.session_state.get('logged_in') or not st.session_state.get('username'):
        return

    all_data = load_all_data()
    username = st.session_state['username']
    
    # 保留原有的额度设置，防止被覆盖
    existing_quota = all_data.get(username, {}).get('quota_limit', DEFAULT_QUOTA)
    
    all_data[username] = {
        "video_tasks": st.session_state.get('video_tasks', []),
        "image_tasks": st.session_state.get('image_tasks', []),
        "chat_sessions": st.session_state.get('chat_sessions', {}),
        "current_session_id": st.session_state.get('current_session_id', ""),
        "quota_limit": existing_quota # 👈 关键：保存额度信息
    }
    
    _push_to_blob(all_data)

def save_full_data_admin(all_data):
    """管理员保存：更新全量数据（用于修改额度）"""
    _push_to_blob(all_data)

def _push_to_blob(data):
    url = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    try:
        requests.put(url, json=data, headers=headers, timeout=5)
    except Exception as e:
        print(f"云端保存失败: {e}")

def init_user_data(username):
    """初始化用户数据"""
    all_data = load_all_data()
    user_data = all_data.get(username, {})
    
    st.session_state['video_tasks'] = user_data.get('video_tasks', [])
    st.session_state['image_tasks'] = user_data.get('image_tasks', [])
    st.session_state['quota_limit'] = user_data.get('quota_limit', DEFAULT_QUOTA) # 加载额度
    
    saved_sessions = user_data.get('chat_sessions', {})
    if saved_sessions:
        st.session_state['chat_sessions'] = saved_sessions
        last_id = user_data.get('current_session_id')
        st.session_state['current_session_id'] = last_id if last_id in saved_sessions else list(saved_sessions.keys())[0]
    else:
        default_id = str(uuid.uuid4())
        st.session_state['chat_sessions'] = {default_id: {"title": "默认对话", "messages": []}}
        st.session_state['current_session_id'] = default_id

# ==========================================
# 👮 4. 额度控制逻辑
# ==========================================
def get_usage_count():
    """获取当前用户已使用次数"""
    v_count = len(st.session_state.get('video_tasks', []))
    i_count = len(st.session_state.get('image_tasks', []))
    return v_count + i_count

def check_quota_available():
    """检查是否有剩余额度"""
    used = get_usage_count()
    limit = st.session_state.get('quota_limit', DEFAULT_QUOTA)
    return used < limit

# ==========================================
# 🛠️ 核心功能函数
# ==========================================
def check_login(username, password):
    return USERS.get(username) == password

def log_action(action, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] User: {st.session_state.get('username', 'Unknown')} | Action: {action} | {details}")

# --- 视频相关 ---
def submit_video_task(prompt, negative_prompt, aspect_ratio, duration):
    log_action("SUBMIT_VIDEO", f"Prompt: {prompt[:20]}...")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": VIDEO_MODEL, "prompt": prompt, "negative_prompt": negative_prompt,
        "aspect_ratio": aspect_ratio, "duration_seconds": duration 
    }
    try:
        r = requests.post(VIDEO_CREATE_URL, headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return (True, data.get('id'), "提交成功") if data.get('id') else (False, None, f"无ID: {data}")
        return False, None, f"HTTP {r.status_code}: {r.text}"
    except Exception as e:
        return False, None, f"连接错误: {str(e)}"

def check_video_status(task_id):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    params = {"id": task_id}
    try:
        r = requests.get(VIDEO_QUERY_URL, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            res = r.json()
            status = res.get('status') or res.get('state') or res.get('task_status')
            vid_url = None
            if 'video_url' in res and res['video_url']: vid_url = res['video_url']
            elif 'data' in res and len(res['data']) > 0: vid_url = res['data'][0]['url']
            elif 'url' in res: vid_url = res['url']
            if vid_url: status = 'succeeded'
            return status, vid_url
        else:
            return "unknown", None
    except Exception:
        return "unknown", None

# --- 图片相关 ---
def generate_image_via_chat(prompt):
    log_action("GENERATE_IMAGE", f"Prompt: {prompt[:20]}...")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": IMAGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    try:
        r = requests.post(CHAT_URL, headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            content = data['choices'][0]['message']['content']
            return True, content
        else:
            return False, f"Error {r.status_code}: {r.text}"
    except Exception as e:
        return False, f"Request failed: {str(e)}"

# --- 对话相关 ---
def chat_with_gemini(messages):
    log_action("CHAT", "Sending message to Gemini")
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": CHAT_MODEL, "messages": messages, "stream": True}
    try:
        return requests.post(CHAT_URL, headers=headers, json=payload, stream=True, timeout=60)
    except Exception as e:
        return str(e)

def encode_image(file):
    return base64.b64encode(file.getvalue()).decode('utf-8') if file else None

def extract_prompts_from_text(text):
    prompts = []
    anchor_content = ""
    anchor_match = re.search(r'(?:通用(?:Prompt)?(?:前缀)?|Style Anchor).*?[:：]\s*(.*)', text, re.IGNORECASE)
    if anchor_match:
        raw_anchor = anchor_match.group(1).strip().split('\n')[0]
        anchor_content = raw_anchor.replace('`', '').replace(')', '').replace('）', '').strip()
    
    lines = text.split('\n')
    for line in lines:
        if '|' in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 3 and '---' not in line:
                candidate = parts[2] 
                if len(candidate) > 10 and not candidate.startswith('视觉详细指令'):
                    prompts.append(candidate)
    if not prompts:
        list_pattern = r'(?:^|\n)\s*(?:[•\*\-\d\.]+)\s*(?:镜头|Scene).*?[:：]\s*(\[Style Anchor\].*?)(?=\n|$)'
        prompts = re.findall(list_pattern, text, re.IGNORECASE)
    if not prompts:
        anchor_pattern = r'(\[Style Anchor\].*?)(?=\n|$)'
        prompts = re.findall(anchor_pattern, text)

    final_prompts = []
    for p in prompts:
        p = p.replace('**', '').strip() 
        final_prompts.append(p)
    return final_prompts, anchor_content

def extract_copy_blocks(text):
    blocks = []
    pattern = r'(?:^|\n)\s*(?:\d+\.\s*)?【(.*?)】([\s\S]*?)(?=(?:\n\s*(?:\d+\.\s*)?【)|$)'
    matches = re.findall(pattern, text)
    for title, content in matches:
        if "文案" in title or "粘贴" in title or "脚本" in title:
            blocks.append({"title": title, "content": content.strip()})
    return blocks

# ==========================================
# 🖥️ 页面主逻辑
# ==========================================
st.set_page_config(page_title="AI 工作台", layout="wide", page_icon="✨", initial_sidebar_state="auto")

# --- CSS 样式 ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    .video-card { background-color: #f8f9fa; border-radius: 12px; padding: 16px; margin-bottom: 12px; border: 1px solid #eee; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .stButton button { border-radius: 8px; font-weight: 500; transition: all 0.2s; }
    .quota-box { padding: 10px; background: #e6f3ff; border-radius: 8px; border: 1px solid #b6d4fe; margin-bottom: 20px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- 登录界面 ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.markdown("## 🔒 请登录 AI 工作台")
    username = st.text_input("用户名")
    password = st.text_input("密码", type="password")
    if st.button("登录", type="primary", use_container_width=True):
        if check_login(username, password):
            st.session_state['logged_in'] = True
            st.session_state['username'] = username
            with st.spinner("正在同步云端数据..."):
                init_user_data(username)
            log_action("LOGIN", "Success")
            st.rerun()
        else:
            st.error("用户名或密码错误")
    st.stop()

# --- 初始化 Session State ---
if 'video_tasks' not in st.session_state: st.session_state['video_tasks'] = []
if 'image_tasks' not in st.session_state: st.session_state['image_tasks'] = []
if 'chat_sessions' not in st.session_state:
    default_id = str(uuid.uuid4())
    st.session_state['chat_sessions'] = {default_id: {"title": "默认对话", "messages": []}}
    st.session_state['current_session_id'] = default_id
if 'video_page' not in st.session_state: st.session_state['video_page'] = 1
if 'pending_prompts' not in st.session_state: st.session_state['pending_prompts'] = []
if 'user_edited_anchor' not in st.session_state: st.session_state['user_edited_anchor'] = ""
if 'quota_limit' not in st.session_state: st.session_state['quota_limit'] = DEFAULT_QUOTA

# 确保 current_session_id 有效
if st.session_state['current_session_id'] not in st.session_state['chat_sessions']:
    if st.session_state['chat_sessions']:
        st.session_state['current_session_id'] = list(st.session_state['chat_sessions'].keys())[0]
    else:
        new_id = str(uuid.uuid4())
        st.session_state['chat_sessions'] = {new_id: {"title": "默认对话", "messages": []}}
        st.session_state['current_session_id'] = new_id

current_sess_id = st.session_state['current_session_id']
current_session = st.session_state['chat_sessions'][current_sess_id]

# --- 侧边栏 ---
with st.sidebar:
    st.title(f"✨ 欢迎, {st.session_state['username']}")
    
    # 📊 额度展示
    used_count = get_usage_count()
    limit_count = st.session_state['quota_limit']
    st.markdown(f"""
    <div class="quota-box">
        <b>📊 额度使用</b><br>
        <span style="font-size: 1.5em; color: {'red' if used_count >= limit_count else 'green'}">
            {used_count} / {limit_count}
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("退出登录", use_container_width=True):
        save_current_user_data()
        st.session_state['logged_in'] = False
        st.rerun()
    st.divider()
    
    # 菜单选项
    options = ["🎬 视频生成", "🎨 图片生成", "💬 智能对话"]
    if st.session_state['username'] == "admin":
        options.append("👑 管理后台") # 👈 仅管理员可见
        
    app_mode = st.radio("功能切换", options, index=0)
    st.divider()
    
    if app_mode == "🎬 视频生成":
        st.subheader("新建视频任务")
        running_count = len([t for t in st.session_state['video_tasks'] if t['status'] not in ['succeeded', 'failed']])
        st.progress(running_count / 10, text=f"队列: {running_count}/10")
        
        v_ratio = st.selectbox("比例", ["9:16", "16:9", "1:1"])
        v_dur = st.slider("时长 (s)", 5, 10, 5)
        v_neg = st.text_area("负向提示词", "low quality, blurry", height=60)
        v_prompt = st.text_area("提示词", height=100, placeholder="描述视频内容...")
        
        if st.button("🚀 提交视频", type="primary", disabled=(running_count >= 10), use_container_width=True):
            if not check_quota_available():
                st.error("❌ 额度已用尽，请联系管理员充值！")
            elif v_prompt:
                suc, tid, msg = submit_video_task(v_prompt, v_neg, v_ratio, v_dur)
                if suc:
                    st.toast("任务已提交")
                    st.session_state['video_tasks'].insert(0, {
                        "id": tid, "prompt": v_prompt, "status": "queued", 
                        "video_url": None, "created_at": datetime.now().strftime("%H:%M:%S"),
                        "last_check": 0,
                        "params": {"neg": v_neg, "ratio": v_ratio, "dur": v_dur}
                    })
                    st.session_state['video_page'] = 1
                    save_current_user_data()
                    st.rerun()
                else:
                    st.error(msg)
        
        if st.button("🗑️ 清空视频记录", use_container_width=True):
            st.session_state['video_tasks'] = []
            save_current_user_data()
            st.rerun()

    elif app_mode == "🎨 图片生成":
        st.subheader("新建绘图任务")
        img_prompt = st.text_area("画面描述", height=120, placeholder="一只赛博朋克风格的猫，霓虹灯背景...")
        
        if st.button("🎨 开始绘图", type="primary", use_container_width=True):
            if not check_quota_available():
                st.error("❌ 额度已用尽，请联系管理员充值！")
            elif img_prompt:
                with st.spinner("AI 正在绘图，请稍候..."):
                    success, result = generate_image_via_chat(img_prompt)
                    if success:
                        st.session_state['image_tasks'].insert(0, {
                            "prompt": img_prompt,
                            "result": result,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        save_current_user_data()
                        st.success("绘图完成！")
                        st.rerun()
                    else:
                        st.error(f"绘图失败: {result}")
        
        if st.button("🗑️ 清空图片记录", use_container_width=True):
            st.session_state['image_tasks'] = []
            save_current_user_data()
            st.rerun()

    elif app_mode == "💬 智能对话":
        st.subheader("对话列表")
        if st.button("➕ 新建对话", use_container_width=True):
            new_id = str(uuid.uuid4())
            st.session_state['chat_sessions'][new_id] = {
                "title": f"对话 {datetime.now().strftime('%H:%M')}", "messages": []
            }
            st.session_state['current_session_id'] = new_id
            save_current_user_data()
            st.rerun()
            
        session_ids = list(st.session_state['chat_sessions'].keys())
        for sess_id in reversed(session_ids):
            sess = st.session_state['chat_sessions'][sess_id]
            btn_type = "primary" if sess_id == current_sess_id else "secondary"
            col_s1, col_s2 = st.columns([4, 1])
            with col_s1:
                if st.button(f"📄 {sess['title']}", key=f"btn_{sess_id}", type=btn_type, use_container_width=True):
                    st.session_state['current_session_id'] = sess_id
                    st.rerun()
            with col_s2:
                if st.button("❌", key=f"del_{sess_id}", use_container_width=True):
                    if len(st.session_state['chat_sessions']) > 1:
                        del st.session_state['chat_sessions'][sess_id]
                        if sess_id == current_sess_id:
                            st.session_state['current_session_id'] = list(st.session_state['chat_sessions'].keys())[0]
                        save_current_user_data()
                        st.rerun()

# --- 主界面逻辑 ---
if app_mode == "👑 管理后台" and st.session_state['username'] == "admin":
    st.header("👑 管理后台")
    
    # 加载全量数据
    all_data = load_all_data()
    
    tab1, tab2 = st.tabs(["📊 生成记录监控", "💳 额度管理"])
    
    with tab1:
        st.subheader("全站生成记录")
        records = []
        for user, data in all_data.items():
            # 收集视频记录
            for task in data.get('video_tasks', []):
                records.append({
                    "用户": user,
                    "类型": "视频",
                    "内容/提示词": task.get('prompt', '')[:50] + "...",
                    "状态/结果": task.get('status', 'unknown'),
                    "时间": task.get('created_at', 'N/A')
                })
            # 收集图片记录
            for task in data.get('image_tasks', []):
                records.append({
                    "用户": user,
                    "类型": "图片",
                    "内容/提示词": task.get('prompt', '')[:50] + "...",
                    "状态/结果": "Success",
                    "时间": task.get('time', 'N/A')
                })
        
        if records:
            df = pd.DataFrame(records)
            # 简单的按时间排序（假设时间格式大致可比，或者直接展示）
            st.dataframe(df, use_container_width=True)
        else:
            st.info("暂无生成记录")

    with tab2:
        st.subheader("用户额度管理")
        
        # 准备编辑数据
        user_list = list(USERS.keys()) # 仅显示配置表中的用户，或者 all_data.keys()
        
        # 创建一个表单来批量更新
        with st.form("quota_form"):
            updated_quotas = {}
            for user in user_list:
                user_cloud_data = all_data.get(user, {})
                current_limit = user_cloud_data.get('quota_limit', DEFAULT_QUOTA)
                used = len(user_cloud_data.get('video_tasks', [])) + len(user_cloud_data.get('image_tasks', []))
                
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    st.markdown(f"**{user}**")
                with c2:
                    st.markdown(f"已用: {used}")
                with c3:
                    new_val = st.number_input(f"额度上限 ({user})", min_value=0, value=int(current_limit), key=f"q_{user}")
                    updated_quotas[user] = new_val
                st.divider()
            
            if st.form_submit_button("💾 保存额度配置"):
                for user, limit in updated_quotas.items():
                    if user not in all_data:
                        all_data[user] = {}
                    all_data[user]['quota_limit'] = limit
                
                save_full_data_admin(all_data)
                st.success("额度已更新！")
                time.sleep(1)
                st.rerun()

elif app_mode == "🎬 视频生成":
    st.subheader("视频任务列表")
    
    if not st.session_state['video_tasks']:
        st.info("👈 请在左侧提交新任务")
    
    VIDEOS_PER_PAGE = 5
    total_tasks = len(st.session_state['video_tasks'])
    total_pages = max(1, (total_tasks + VIDEOS_PER_PAGE - 1) // VIDEOS_PER_PAGE)
    
    if st.session_state['video_page'] > total_pages: st.session_state['video_page'] = total_pages
    if st.session_state['video_page'] < 1: st.session_state['video_page'] = 1
    
    current_page = st.session_state['video_page']
    start_idx = (current_page - 1) * VIDEOS_PER_PAGE
    end_idx = start_idx + VIDEOS_PER_PAGE
    page_tasks = st.session_state['video_tasks'][start_idx:end_idx]
    
    active_tasks = False
    checks_performed = 0 
    
    for i, task in enumerate(page_tasks):
        real_idx = start_idx + i
        status_label = task['status'] or "unknown"
        is_finished = status_label.lower() in ['succeeded', 'success', 'completed', 'failed', 'error']
        
        if not is_finished:
            active_tasks = True
            if checks_performed < 2 and time.time() - task.get('last_check', 0) > 5:
                new_stat, v_url = check_video_status(task['id'])
                st.session_state['video_tasks'][real_idx]['last_check'] = time.time()
                checks_performed += 1 
                
                changed = False
                if new_stat and new_stat != "unknown":
                    st.session_state['video_tasks'][real_idx]['status'] = new_stat
                    changed = True
                if v_url:
                    st.session_state['video_tasks'][real_idx]['video_url'] = v_url
                    st.session_state['video_tasks'][real_idx]['status'] = 'succeeded'
                    changed = True
                if changed: 
                    save_current_user_data()
                    st.rerun()

    for i, task in enumerate(page_tasks):
        real_idx = start_idx + i
        status_label = task['status'] or "unknown"
        is_finished = status_label.lower() in ['succeeded', 'success', 'completed', 'failed', 'error']
        
        with st.container():
            st.markdown(f"""<div class="video-card">""", unsafe_allow_html=True)
            c1, c2 = st.columns([4, 1]) 
            with c1:
                badge_color = "orange" if status_label == 'queued' else "green" if status_label == 'succeeded' else "gray"
                st.markdown(f"**状态**: :{badge_color}[{status_label.upper()}] &nbsp; <small style='color:#999'>{task['created_at']}</small>", unsafe_allow_html=True)
                st.markdown(f"<small>{task['prompt']}</small>", unsafe_allow_html=True)
                
                if st.button("🔄 重试", key=f"retry_{real_idx}"):
                    if not check_quota_available():
                        st.error("❌ 额度不足")
                    else:
                        params = task.get("params", {})
                        r_neg = params.get("neg", "low quality, blurry")
                        r_ratio = params.get("ratio", "9:16")
                        r_dur = params.get("dur", 8)
                        
                        suc, tid, msg = submit_video_task(task['prompt'], r_neg, r_ratio, r_dur)
                        if suc:
                            st.toast("重试任务已提交")
                            st.session_state['video_tasks'].insert(0, {
                                "id": tid, "prompt": task['prompt'], "status": "queued", 
                                "video_url": None, "created_at": datetime.now().strftime("%H:%M:%S"),
                                "last_check": 0,
                                "params": {"neg": r_neg, "ratio": r_ratio, "dur": r_dur}
                            })
                            st.session_state['video_page'] = 1
                            save_current_user_data()
                            st.rerun()
                        else:
                            st.error(f"重试失败: {msg}")

            with c2:
                if task.get('video_url'):
                    st.video(task['video_url'])
                else:
                    st.markdown(f"""
                    <div style="width:100%;height:100px;background:#eee;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#888;font-size:0.8rem;">
                        { "⏳ 生成中..." if not is_finished else "❌ 失败" }
                    </div>
                    """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    if total_pages > 1:
        c_p1, c_p2, c_p3 = st.columns([1, 3, 1])
        with c_p1:
            if st.button("◀ 上一页", disabled=(current_page == 1), use_container_width=True):
                st.session_state['video_page'] -= 1
                st.rerun()
        with c_p2:
            st.markdown(f"<div style='text-align:center; padding-top:5px;'>第 {current_page} / {total_pages} 页</div>", unsafe_allow_html=True)
        with c_p3:
            if st.button("下一页 ▶", disabled=(current_page == total_pages), use_container_width=True):
                st.session_state['video_page'] += 1
                st.rerun()

    if active_tasks:
        time.sleep(3)
        st.rerun()

elif app_mode == "🎨 图片生成":
    st.subheader("图片生成历史")
    
    if not st.session_state['image_tasks']:
        st.info("👈 请在左侧输入描述并点击“开始绘图”")
    
    for idx, task in enumerate(st.session_state['image_tasks']):
        with st.container():
            st.markdown(f"""<div class="video-card">""", unsafe_allow_html=True)
            st.markdown(f"**时间**: {task['time']}")
            st.markdown(f"**提示词**: {task['prompt']}")
            st.divider()
            st.markdown(task['result'])
            st.markdown("</div>", unsafe_allow_html=True)

elif app_mode == "💬 智能对话":
    c_t1, c_t2 = st.columns([5, 1])
    with c_t1:
        new_title = st.text_input("对话标题", value=current_session['title'], key=f"title_{current_sess_id}", label_visibility="collapsed")
    with c_t2:
        if new_title != current_session['title']:
            st.session_state['chat_sessions'][current_sess_id]['title'] = new_title
            save_current_user_data()
            st.rerun()

    with st.container():
        with st.form(key=f"chat_form_{current_sess_id}", clear_on_submit=True):
            col_in1, col_in2 = st.columns([6, 1])
            with col_in1:
                user_input = st.text_area("输入消息...", height=80, key="input_area", label_visibility="collapsed", placeholder="在此输入消息，Shift+Enter 换行")
            with col_in2:
                st.markdown("<br>", unsafe_allow_html=True)
                submit_btn = st.form_submit_button("发送 🚀", use_container_width=True)
            
            uploaded_files = st.file_uploader("📎 添加图片", type=['png', 'jpg'], accept_multiple_files=True, key=f"up_{current_sess_id}", label_visibility="collapsed")

    if submit_btn and user_input:
        user_msg = {"role": "user", "content": user_input, "images": []}
        api_content = [{"type": "text", "text": user_input}]
        
        if uploaded_files:
            for f in uploaded_files:
                b64 = encode_image(f)
                user_msg["images"].append(b64)
                api_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        
        st.session_state['chat_sessions'][current_sess_id]['messages'].append(user_msg)
        save_current_user_data()
        
        api_msgs = []
        for m in current_session['messages']:
            content_to_send = m['content']
            if m["images"]:
                c_list = [{"type": "text", "text": content_to_send}]
                for img in m["images"]:
                    c_list.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
                api_msgs.append({"role": m["role"], "content": c_list})
            else:
                api_msgs.append({"role": m["role"], "content": content_to_send})
        
        st.session_state['chat_sessions'][current_sess_id]['messages'].append({"role": "assistant", "content": "Thinking...", "images": []})
        
        resp = chat_with_gemini(api_msgs)
        full_resp = ""
        if isinstance(resp, str):
            full_resp = f"Error: {resp}"
        else:
            for chunk in resp.iter_lines():
                if chunk:
                    try:
                        chunk_str = chunk.decode('utf-8').replace('data: ', '')
                        if chunk_str == '[DONE]': break
                        data = json.loads(chunk_str)
                        delta = data['choices'][0]['delta'].get('content', '')
                        full_resp += delta
                    except: pass
        
        st.session_state['chat_sessions'][current_sess_id]['messages'][-1]['content'] = full_resp
        save_current_user_data()
        st.rerun()

    st.divider()

    confirm_container = st.container()

    chat_container = st.container()
    with chat_container:
        for idx, msg in enumerate(reversed(current_session['messages'])):
            with st.chat_message(msg["role"]):
                if msg.get("images"):
                    cols = st.columns(len(msg["images"]))
                    for i, img in enumerate(msg["images"]):
                        cols[i].image(base64.b64decode(img), use_container_width=True)
                st.markdown(msg["content"])
                
                if msg["role"] == "assistant":
                    c_act1, c_act2 = st.columns([1, 5])
                    with c_act1:
                        if st.button("🎬 提取脚本", key=f"extract_{idx}"):
                            prompts, anchor = extract_prompts_from_text(msg["content"])
                            if prompts:
                                st.session_state['pending_prompts'] = prompts
                                st.session_state['user_edited_anchor'] = anchor 
                                st.toast(f"已提取 {len(prompts)} 个分镜！")
                                st.rerun()
                            else:
                                st.warning("未检测到脚本格式")
                    
                    copy_blocks = extract_copy_blocks(msg["content"])
                    if copy_blocks:
                        for block in copy_blocks:
                            with st.expander(f"📋 复制 {block['title']} (点击右上角)"):
                                st.code(block['content'], language=None)
                    else:
                        with st.expander("📋 复制全文"):
                            st.code(msg["content"], language=None)

    if st.session_state['pending_prompts']:
        with confirm_container:
            with st.expander("🎬 确认提交视频任务", expanded=True):
                st.markdown("##### 1. 确认通用前缀 (Style Anchor)")
                st.text_input("如果提取不准确，请手动修改：", key="user_edited_anchor")
                current_anchor = st.session_state['user_edited_anchor']
                
                st.markdown("##### 2. 配置生成参数")
                c_p1, c_p2, c_p3 = st.columns(3)
                with c_p1:
                    batch_ratio = st.selectbox("比例", ["9:16", "16:9", "1:1"], index=0, key="batch_ratio")
                with c_p2:
                    batch_dur = st.slider("时长 (s)", 5, 10, 8, key="batch_dur")
                with c_p3:
                    batch_neg = st.text_input("负向提示词", value="low quality, blurry", key="batch_neg")

                st.markdown("##### 3. 确认分镜脚本")
                selected_indices = []
                for i, p in enumerate(st.session_state['pending_prompts']):
                    display_p = p
                    if current_anchor:
                        display_p = p.replace('`[Style Anchor]`', current_anchor).replace('[Style Anchor]', current_anchor).replace('【Style Anchor】', current_anchor)
                    
                    if st.checkbox(f"镜头 {i+1}: {display_p[:60]}...", value=True, key=f"chk_{i}"):
                        selected_indices.append(i)
                
                if st.button("🚀 立即生成选中视频", type="primary", use_container_width=True):
                    if not check_quota_available():
                        st.error("❌ 额度不足")
                    else:
                        progress_bar = st.progress(0, text="正在提交任务...")
                        success_count = 0
                        total_selected = len(selected_indices)
                        
                        for idx, i in enumerate(selected_indices):
                            final_prompt = st.session_state['pending_prompts'][i]
                            if current_anchor:
                                final_prompt = final_prompt.replace('`[Style Anchor]`', current_anchor).replace('[Style Anchor]', current_anchor).replace('【Style Anchor】', current_anchor)
                            
                            suc, tid, msg = submit_video_task(final_prompt, batch_neg, batch_ratio, batch_dur)
                            
                            if suc:
                                st.session_state['video_tasks'].insert(0, {
                                    "id": tid, "prompt": final_prompt, "status": "queued", 
                                    "video_url": None, "created_at": datetime.now().strftime("%H:%M:%S"),
                                    "last_check": 0,
                                    "params": {"neg": batch_neg, "ratio": batch_ratio, "dur": batch_dur}
                                })
                                success_count += 1
                            else:
                                st.error(f"镜头 {i+1} 提交失败: {msg}")
                            
                            progress_bar.progress((idx + 1) / total_selected, text=f"已提交 {idx + 1}/{total_selected}")
                            time.sleep(0.5)
                        
                        st.session_state['pending_prompts'] = []
                        st.session_state['video_page'] = 1
                        save_current_user_data()
                        st.success(f"成功提交 {success_count} 个任务！")
                        time.sleep(1)
                        st.rerun()
                
                if st.button("取消", use_container_width=True):
                    st.session_state['pending_prompts'] = []
                    st.rerun()
