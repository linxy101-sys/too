import streamlit as st
import requests
import json
import uuid
import time
from datetime import datetime

# ==========================================
# ⚙️ 1. 基础配置与全局变量
# ==========================================
st.set_page_config(page_title="AI 全能助手", layout="wide", page_icon="🤖")

# ✅ 已填入你的 ID
JSONBLOB_ID = "019b8e81-d5d4-7220-81e8-7ea251e98c38"

# 模拟用户数据库
USERS = {
    "admin": "123456",
    "user": "123456"
}

# ==========================================
# 💾 2. 数据持久化核心 (JsonBlob)
# ==========================================
def load_all_data():
    """从云端加载数据，增加容错处理"""
    url = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"
    headers = {
        "Content-Type": "application/json", 
        "Accept": "application/json",
        "User-Agent": "StreamlitApp/1.0" # 伪装成浏览器，防止被拦截
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            return response.json()
        else:
            # 如果云端是空的或者报错，返回空字典，不让程序崩溃
            return {}
    except Exception as e:
        print(f"云端连接警告: {e}")
        return {}

def save_current_user_data():
    """保存数据到云端"""
    if not st.session_state.get('logged_in'):
        return

    # 1. 读取最新数据
    all_data = load_all_data()
    
    # 2. 更新当前用户
    username = st.session_state['username']
    all_data[username] = {
        "video_tasks": st.session_state.get('video_tasks', []),
        "chat_sessions": st.session_state.get('chat_sessions', {}),
        "current_session_id": st.session_state.get('current_session_id', "")
    }
    
    # 3. 推送更新
    url = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    try:
        requests.put(url, json=all_data, headers=headers, timeout=3)
    except Exception:
        pass 

def init_user_data(username):
    """初始化用户数据"""
    all_data = load_all_data()
    user_data = all_data.get(username, {})
    
    st.session_state['video_tasks'] = user_data.get('video_tasks', [])
    
    saved_sessions = user_data.get('chat_sessions', {})
    if saved_sessions:
        st.session_state['chat_sessions'] = saved_sessions
        last_id = user_data.get('current_session_id')
        if last_id in saved_sessions:
            st.session_state['current_session_id'] = last_id
        else:
            st.session_state['current_session_id'] = list(saved_sessions.keys())[0]
    else:
        new_id = str(uuid.uuid4())
        st.session_state['chat_sessions'] = {
            new_id: {"title": "新对话", "messages": [{"role": "assistant", "content": "你好！我是你的云端同步助手。"}]}
        }
        st.session_state['current_session_id'] = new_id

# ==========================================
# 🔐 3. 登录界面
# ==========================================
def login_page():
    st.markdown("<h1 style='text-align: center;'>🔐 登录</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        if st.button("登录", use_container_width=True):
            if username in USERS and USERS[username] == password:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                with st.spinner("正在同步云端数据..."):
                    init_user_data(username)
                st.rerun()
            else:
                st.error("账号或密码错误")
        st.info("测试账号: admin / 123456")

# ==========================================
# 💬 4. 聊天模块
# ==========================================
def chat_module():
    with st.sidebar:
        st.header("🗂️ 历史记录")
        if st.button("➕ 新建对话", use_container_width=True):
            new_id = str(uuid.uuid4())
            st.session_state['chat_sessions'][new_id] = {
                "title": "新对话", 
                "messages": [{"role": "assistant", "content": "你好！"}]
            }
            st.session_state['current_session_id'] = new_id
            save_current_user_data()
            st.rerun()
        
        st.divider()
        sessions = st.session_state['chat_sessions']
        for s_id in list(sessions.keys()):
            if st.button(f"💬 {sessions[s_id]['title']}", key=s_id, use_container_width=True):
                st.session_state['current_session_id'] = s_id
                st.rerun()
        
        st.divider()
        if st.button("🚪 退出"):
            st.session_state['logged_in'] = False
            st.rerun()

    current_id = st.session_state['current_session_id']
    current_session = st.session_state['chat_sessions'][current_id]
    
    st.subheader(current_session['title'])
    
    for msg in current_session['messages']:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if prompt := st.chat_input("输入内容..."):
        with st.chat_message("user"):
            st.write(prompt)
        current_session['messages'].append({"role": "user", "content": prompt})
        
        if len(current_session['messages']) <= 3:
            current_session['title'] = prompt[:10]
            
        with st.chat_message("assistant"):
            response = f"收到：{prompt} (数据已云端同步)"
            st.write(response)
        current_session['messages'].append({"role": "assistant", "content": response})
        
        save_current_user_data()

# ==========================================
# 🎬 5. 视频模块
# ==========================================
def video_module():
    st.header("🎬 视频生成")
    col1, col2 = st.columns(2)
    with col1:
        prompt = st.text_area("提示词")
        if st.button("生成"):
            new_task = {
                "id": str(uuid.uuid4())[:8],
                "prompt": prompt,
                "status": "处理中",
                "time": datetime.now().strftime("%H:%M")
            }
            st.session_state['video_tasks'].insert(0, new_task)
            save_current_user_data()
            st.rerun()
            
    with col2:
        tasks = st.session_state.get('video_tasks', [])
        for task in tasks:
            with st.expander(f"{task['time']} - {task['prompt'][:10]}"):
                st.write(task['status'])

# ==========================================
# 🚀 主程序
# ==========================================
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page()
    else:
        tab1, tab2 = st.tabs(["对话", "视频"])
        with tab1: chat_module()
        with tab2: video_module()

if __name__ == "__main__":
    main()
