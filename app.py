import streamlit as st
import requests
import json
import uuid
import time
from datetime import datetime

# ==========================================
# ⚙️ 1. 基础配置与全局变量
# ==========================================
st.set_page_config(page_title="AI 全能助手 (云端同步版)", layout="wide", page_icon="🤖")

# 🔴🔴🔴 【重要】请在这里填入你在 JsonBlob 获取的 ID 🔴🔴🔴
# 格式示例：JSONBLOB_ID = "1340987654321-987654321"
JSONBLOB_ID = "请在这里填入你的JsonBlob_ID" 

# 模拟用户数据库 (账号: admin, 密码: 123456)
USERS = {
    "admin": "123456",
    "user": "123456"
}

# ==========================================
# 💾 2. 数据持久化核心 (JsonBlob 云端版)
# ==========================================
def load_all_data():
    """从云端加载所有用户数据"""
    if "请在这里" in JSONBLOB_ID:
        st.error("⚠️ 请先在代码第 16 行填入你的 JsonBlob ID！")
        return {}

    url = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {}
    except Exception as e:
        st.toast(f"云端连接失败: {e}", icon="❌")
        return {}

def save_current_user_data():
    """将当前用户数据同步保存到云端"""
    if not st.session_state.get('logged_in') or "请在这里" in JSONBLOB_ID:
        return

    # 1. 读取云端最新数据
    all_data = load_all_data()
    
    # 2. 更新当前用户数据
    username = st.session_state['username']
    all_data[username] = {
        "video_tasks": st.session_state.get('video_tasks', []),
        "chat_sessions": st.session_state.get('chat_sessions', {}),
        "current_session_id": st.session_state.get('current_session_id', "")
    }
    
    # 3. 推送回云端
    url = f"https://jsonblob.com/api/jsonBlob/{JSONBLOB_ID}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    try:
        requests.put(url, json=all_data, headers=headers, timeout=5)
    except Exception:
        pass # 静默失败，不打扰用户

def init_user_data(username):
    """登录后初始化数据"""
    all_data = load_all_data()
    user_data = all_data.get(username, {})
    
    # 恢复视频任务
    st.session_state['video_tasks'] = user_data.get('video_tasks', [])
    
    # 恢复对话记录
    saved_sessions = user_data.get('chat_sessions', {})
    if saved_sessions:
        st.session_state['chat_sessions'] = saved_sessions
        # 恢复上次选中的会话，如果找不到则默认第一个
        last_id = user_data.get('current_session_id')
        if last_id in saved_sessions:
            st.session_state['current_session_id'] = last_id
        else:
            st.session_state['current_session_id'] = list(saved_sessions.keys())[0]
    else:
        # 新用户初始化
        new_id = str(uuid.uuid4())
        st.session_state['chat_sessions'] = {
            new_id: {"title": "新对话", "messages": [{"role": "assistant", "content": "你好！我是你的云端同步助手，有什么可以帮你？"}]}
        }
        st.session_state['current_session_id'] = new_id

# ==========================================
# 🔐 3. 登录界面
# ==========================================
def login_page():
    st.markdown("<h1 style='text-align: center;'>🔐 登录 AI 助手</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        
        if st.button("登录", use_container_width=True):
            if username in USERS and USERS[username] == password:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                init_user_data(username) # 加载云端数据
                st.rerun()
            else:
                st.error("用户名或密码错误")
        
        st.info("测试账号: admin / 123456")

# ==========================================
# 💬 4. 聊天功能模块
# ==========================================
def chat_module():
    # 侧边栏：历史记录管理
    with st.sidebar:
        st.header("🗂️ 历史记录 (云端同步)")
        
        if st.button("➕ 新建对话", use_container_width=True):
            new_id = str(uuid.uuid4())
            st.session_state['chat_sessions'][new_id] = {
                "title": "新对话", 
                "messages": [{"role": "assistant", "content": "你好！我们可以开始新的话题了。"}]
            }
            st.session_state['current_session_id'] = new_id
            save_current_user_data() # 保存
            st.rerun()

        st.divider()
        
        # 显示会话列表
        sessions = st.session_state['chat_sessions']
        # 按时间倒序排列（这里简单用 keys，实际可加时间戳）
        for s_id in list(sessions.keys()):
            title = sessions[s_id]["title"]
            # 高亮当前选中的会话
            if st.button(f"💬 {title}", key=s_id, use_container_width=True, 
                         type="primary" if s_id == st.session_state['current_session_id'] else "secondary"):
                st.session_state['current_session_id'] = s_id
                st.rerun()
        
        st.divider()
        if st.button("🚪 退出登录"):
            st.session_state['logged_in'] = False
            st.rerun()

    # 主聊天界面
    current_id = st.session_state['current_session_id']
    current_session = st.session_state['chat_sessions'][current_id]
    
    st.subheader(f"当前对话：{current_session['title']}")

    # 显示消息历史
    for msg in current_session['messages']:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # 处理用户输入
    if prompt := st.chat_input("输入你的问题..."):
        # 1. 显示用户消息
        with st.chat_message("user"):
            st.write(prompt)
        
        # 2. 保存用户消息
        current_session['messages'].append({"role": "user", "content": prompt})
        
        # 3. 自动重命名对话（如果是第一句）
        if len(current_session['messages']) <= 3:
            current_session['title'] = prompt[:10] + "..."
        
        # 4. 模拟 AI 回复 (这里可以替换为真实的 API 调用)
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                time.sleep(1) # 模拟延迟
                response_text = f"收到！你刚才说的是：{prompt}。\n(这是模拟回复，数据已同步到云端)"
                st.write(response_text)
        
        # 5. 保存 AI 回复
        current_session['messages'].append({"role": "assistant", "content": response_text})
        
        # 6. 关键步骤：同步到云端
        save_current_user_data()

# ==========================================
# 🎬 5. 视频生成模块
# ==========================================
def video_module():
    st.header("🎬 AI 视频生成")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("新建任务")
        prompt = st.text_area("视频描述提示词", height=150)
        style = st.selectbox("视频风格", ["写实", "动漫", "3D渲染", "水墨风"])
        
        if st.button("🚀 开始生成", type="primary"):
            new_task = {
                "id": str(uuid.uuid4())[:8],
                "prompt": prompt,
                "style": style,
                "status": "处理中",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "result": None
            }
            st.session_state['video_tasks'].insert(0, new_task) # 插入到最前面
            save_current_user_data() # 同步到云端
            st.success("任务已提交！请在右侧查看进度。")
            time.sleep(1)
            st.rerun()

    with col2:
        st.subheader("任务列表 (云端同步)")
        tasks = st.session_state.get('video_tasks', [])
        
        if not tasks:
            st.info("暂无任务")
        
        for task in tasks:
            with st.expander(f"[{task['status']}] {task['time']} - {task['style']}"):
                st.write(f"**提示词:** {task['prompt']}")
                if task['status'] == "处理中":
                    st.progress(50)
                    # 模拟完成按钮
                    if st.button("模拟完成", key=f"btn_{task['id']}"):
                        task['status'] = "已完成"
                        task['result'] = "https://www.w3schools.com/html/mov_bbb.mp4" # 示例视频
                        save_current_user_data()
                        st.rerun()
                elif task['status'] == "已完成":
                    st.video(task['result'])

# ==========================================
# 🚀 6. 主程序入口
# ==========================================
def main():
    # 初始化 Session State
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        login_page()
    else:
        # 登录后的主界面
        tab1, tab2 = st.tabs(["💬 智能对话", "🎬 视频生成"])
        
        with tab1:
            chat_module()
        
        with tab2:
            video_module()

if __name__ == "__main__":
    main()
