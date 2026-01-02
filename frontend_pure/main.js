// API 基础配置
const API_BASE = 'http://localhost:8000/api/chat';

// 状态管理
let currentSessionId = null;
let sessions = [];

// ==================== API 调用函数 ====================

// 获取所有会话
async function fetchSessions() {
    const response = await fetch(`${API_BASE}/sessions`);
    if (!response.ok) throw new Error('获取会话失败');
    return await response.json();
}

// 创建新会话
async function createSession(title = '新对话') {
    const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
    });
    if (!response.ok) throw new Error('创建会话失败');
    return await response.json();
}

// 删除会话
async function deleteSession(sessionId) {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: 'DELETE'
    });
    if (!response.ok) throw new Error('删除会话失败');
    return await response.json();
}

// 获取会话的所有消息
async function fetchMessages(sessionId) {
    const response = await fetch(`${API_BASE}/sessions/${sessionId}/messages`);
    if (!response.ok) throw new Error('获取消息失败');
    return await response.json();
}

// 发送消息
async function sendMessage(content) {
    const response = await fetch(`${API_BASE}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            content,
            role: 'user',
            session_id: currentSessionId
        })
    });
    if (!response.ok) throw new Error('发送消息失败');
    return await response.json();
}

// ==================== 渲染函数 ====================

// 渲染会话列表
function renderSessions() {
    const listEl = document.getElementById('sessionList');
    listEl.innerHTML = '';
    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = `session-item ${session.id === currentSessionId ? 'active' : ''}`;
        div.textContent = session.title;
        div.onclick = () => selectSession(session.id);
        listEl.appendChild(div);
    });
}

// 渲染消息列表
function renderMessages(messages) {
    const listEl = document.getElementById('messageList');
    listEl.innerHTML = '';
    messages.forEach(msg => {
        const div = document.createElement('div');
        div.className = `message message-${msg.role}`;
        div.textContent = msg.content;
        listEl.appendChild(div);
    });
    // 滚动到底部
    listEl.scrollTop = listEl.scrollHeight;
}

// ==================== 交互函数 ====================

// 选择会话
async function selectSession(sessionId) {
    currentSessionId = sessionId;
    const session = sessions.find(s => s.id === sessionId);
    document.getElementById('chatTitle').textContent = session.title;
    document.getElementById('deleteSessionBtn').style.display = 'block';
    document.getElementById('chatContainer').style.display = 'flex';
    document.getElementById('emptyState').style.display = 'none';

    renderSessions();
    await loadMessages();
}

// 加载消息
async function loadMessages() {
    if (!currentSessionId) return;
    try {
        const messages = await fetchMessages(currentSessionId);
        renderMessages(messages);
    } catch (error) {
        console.error('加载消息失败:', error);
    }
}

// 创建新会话
async function handleNewSession() {
    try {
        const newSession = await createSession();
        await loadSessions();
        await selectSession(newSession.id);
    } catch (error) {
        console.error('创建会话失败:', error);
        alert('创建会话失败');
    }
}

// 删除当前会话
async function handleDeleteSession() {
    if (!currentSessionId) return;
    if (!confirm('确定要删除这个会话吗？')) return;
    try {
        await deleteSession(currentSessionId);
        currentSessionId = null;
        await loadSessions();
        document.getElementById('chatTitle').textContent = '选择一个会话';
        document.getElementById('deleteSessionBtn').style.display = 'none';
        document.getElementById('chatContainer').style.display = 'none';
        document.getElementById('emptyState').style.display = 'flex';
        document.getElementById('messageList').innerHTML = '';
    } catch (error) {
        console.error('删除会话失败:', error);
        alert('删除会话失败');
    }
}

// 加载所有会话
async function loadSessions() {
    try {
        sessions = await fetchSessions();
        renderSessions();
    } catch (error) {
        console.error('加载会话失败:', error);
    }
}

// 发送消息
async function handleSendMessage() {
    const input = document.getElementById('messageInput');
    const content = input.value.trim();
    if (!content || !currentSessionId) return;

    input.value = '';
    try {
        await sendMessage(content);
        await loadMessages();
    } catch (error) {
        console.error('发送消息失败:', error);
        alert('发送消息失败');
    }
}

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    // 绑定按钮事件
    document.getElementById('newSessionBtn').onclick = handleNewSession;
    document.getElementById('deleteSessionBtn').onclick = handleDeleteSession;
    document.getElementById('sendBtn').onclick = handleSendMessage;

    // 绑定回车发送
    document.getElementById('messageInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // 初始加载会话列表
    loadSessions();
});
