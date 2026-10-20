import React, { useState, useEffect } from 'react';
import { ChatInterface } from './ChatInterface';
import EnhancedDocumentUpload from './EnhancedDocumentUpload';
import EnhancedSettingsPanel from './EnhancedSettingsPanel';
import UserManagement, { type MyInfo } from './UserManagement';
import { StarryBackground } from './StarryBackground';
import './ThreeColumnLayout.css';
import { API_BASE_URL } from '../api/client';

interface ChatSession {
  id: string;
  title: string;
  lastMessage: string;
  timestamp: Date;
  messages: any[];
}

interface ThreeColumnLayoutProps {
  user: any;
  onLogout: () => void;
  token: string;
}

export const ThreeColumnLayout: React.FC<ThreeColumnLayoutProps> = ({ user, onLogout, token }) => {
  const [activeRightPanel, setActiveRightPanel] = useState<'docs' | 'users' | 'settings' | null>('docs');
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('');
  const [documents, setDocuments] = useState<any[]>([]);
  const [me, setMe] = useState<MyInfo | null>(null);

  // 初始化：创建默认会话
  useEffect(() => {
    if (chatSessions.length === 0) {
      const defaultSession: ChatSession = {
        id: Date.now().toString(),
        title: '新对话',
        lastMessage: '宝儿,有什么问题嘛?',
        timestamp: new Date(),
        messages: [
          {
            role: 'assistant',
            content: '宝儿,有什么问题嘛?',
            timestamp: new Date(),
          }
        ],
      };
      setChatSessions([defaultSession]);
      setActiveSessionId(defaultSession.id);
    }
  }, []);

  // 加载文档列表
  useEffect(() => {
    if (activeRightPanel === 'docs') {
      loadDocuments();
    }
  }, [activeRightPanel]);

  // 当前用户的层级和权限
  useEffect(() => {
    fetch(`${API_BASE_URL}/v2/me`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setMe)
      .catch(() => setMe(null));
  }, [token]);

  const loadDocuments = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/documents`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await response.json();
      // 后端返回 { documents: [...], total: N }
      setDocuments(Array.isArray(data.documents) ? data.documents : []);
    } catch (error) {
      console.error('加载文档失败:', error);
      setDocuments([]);
    }
  };

  // 新建对话
  const handleNewChat = () => {
    const newSession: ChatSession = {
      id: Date.now().toString(),
      title: '新对话',
      lastMessage: '宝儿,有什么问题嘛?',
      timestamp: new Date(),
      messages: [
        {
          role: 'assistant',
          content: '宝儿,有什么问题嘛?',
          timestamp: new Date(),
        }
      ],
    };
    setChatSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
  };

  // 切换对话
  const handleSelectSession = (sessionId: string) => {
    setActiveSessionId(sessionId);
  };

  // 删除对话
  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (chatSessions.length === 1) {
      alert('至少保留一个对话');
      return;
    }

    if (!confirm('确定删除这个对话吗？')) {
      return;
    }

    const newSessions = chatSessions.filter((s) => s.id !== sessionId);
    setChatSessions(newSessions);

    // 如果删除的是当前活动会话，切换到第一个
    if (activeSessionId === sessionId && newSessions.length > 0) {
      setActiveSessionId(newSessions[0].id);
    }
  };

  // 更新会话信息
  const handleUpdateSession = (sessionId: string, messages: any[]) => {
    setChatSessions((prev) =>
      prev.map((s) => {
        if (s.id === sessionId) {
          const lastUserMsg = messages.filter((m) => m.role === 'user').pop();
          return {
            ...s,
            title: lastUserMsg?.content.slice(0, 20) || '新对话',
            lastMessage: lastUserMsg?.content || '',
            timestamp: new Date(),
            messages,
          };
        }
        return s;
      })
    );
  };

  // 上传文档
  const handleUploadDocument = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        alert(`上传成功：${data.filename}（${data.chunks} 个知识块）`);
        loadDocuments();
      } else {
        const error = await response.json();
        alert(`上传失败: ${error.detail}`);
      }
    } catch (error: any) {
      alert(`上传失败: ${error.message}`);
    }
  };

  // 删除文档
  const handleDeleteDocument = async (filename: string) => {
    if (!confirm(`确定删除文档 "${filename}" 吗？`)) return;

    try {
      const response = await fetch(`${API_BASE_URL}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        alert('删除成功');
        loadDocuments();
      } else {
        const error = await response.json();
        alert(`删除失败: ${error.detail}`);
      }
    } catch (error: any) {
      alert(`删除失败: ${error.message}`);
    }
  };

  const activeSession = chatSessions.find((s) => s.id === activeSessionId);

  // 格式化相对时间
  const formatRelativeTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    if (hours < 24) return `${hours}小时前`;
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString('zh-CN');
  };

  return (
    <div className="three-column-layout">
      {/* 星空背景 */}
      <StarryBackground />

      {/* 顶部导航栏 */}
      <header className="top-header">
        <div className="header-left">
          <h1>知识库检索系统</h1>
        </div>
        <div className="header-right">
          <span className="user-badge">
            <span className="user-icon">👤</span>
            {me?.level_name ?? '...'}
          </span>
          <span className="username">{user.username}</span>
          <button className="logout-btn" onClick={onLogout}>退出</button>
        </div>
      </header>

      <div className="main-container">
        {/* 左侧边栏 - 会话列表 */}
        <aside className="left-sidebar">
          <div className="sidebar-header">
            <h3>💬 对话历史</h3>
            <button className="new-chat-btn" onClick={handleNewChat}>
              <span>+</span> 新对话
            </button>
          </div>
          <div className="chat-sessions">
            {chatSessions.map((session) => (
              <div
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                onClick={() => handleSelectSession(session.id)}
              >
                <div className="session-icon">💬</div>
                <div className="session-content">
                  <div className="session-title">{session.title}</div>
                  {session.lastMessage && (
                    <div className="session-preview">{session.lastMessage}</div>
                  )}
                </div>
                <div className="session-meta">
                  <div className="session-time">{formatRelativeTime(session.timestamp)}</div>
                  <button
                    className="session-delete"
                    onClick={(e) => handleDeleteSession(session.id, e)}
                    title="删除对话"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* 中间区域 - 聊天界面 */}
        <main className="center-content">
          <div className="chat-header">
            <h2>💬 智能问答</h2>
            <p className="chat-subtitle">基于文档库的智能检索与问答</p>
          </div>

          {activeSession && (
            <ChatInterface
              sessionId={activeSession.id}
              initialMessages={activeSession.messages}
              onMessagesChange={(messages) => handleUpdateSession(activeSession.id, messages)}
            />
          )}
        </main>

        {/* 右侧边栏 - 功能面板 */}
        <aside className="right-sidebar">
          <div className="sidebar-tabs">
            <button
              className={`tab-btn ${activeRightPanel === 'docs' ? 'active' : ''}`}
              onClick={() => setActiveRightPanel('docs')}
            >
              📚 文档管理
            </button>
            {(me?.permissions.generate_keys || me?.permissions.manage_users) && (
              <button
                className={`tab-btn ${activeRightPanel === 'users' ? 'active' : ''}`}
                onClick={() => setActiveRightPanel('users')}
              >
                👥 用户管理
              </button>
            )}
            <button
              className={`tab-btn ${activeRightPanel === 'settings' ? 'active' : ''}`}
              onClick={() => setActiveRightPanel('settings')}
            >
              ⚙️ 设置
            </button>
          </div>

          <div className="sidebar-content">
            {activeRightPanel === 'docs' && (
              <div className="docs-panel">
                <div className="panel-header">
                  <h3>文档库</h3>
                </div>

                {/* 使用增强的文档上传组件 */}
                {me?.permissions.upload_document && (
                  <div style={{ marginBottom: '20px' }}>
                    <EnhancedDocumentUpload onUpload={handleUploadDocument} />
                  </div>
                )}

                <div className="docs-list">
                  {documents.length === 0 ? (
                    <p className="empty-message">
                      {me && me.user_level === 1 ? '平台老板不能查看各公司的文档' : '暂无文档'}
                    </p>
                  ) : (
                    documents.map((doc) => (
                      <div key={doc.filename} className="doc-item">
                        <span className="doc-icon">📄</span>
                        <div className="doc-info">
                          <div className="doc-name">{doc.filename}</div>
                          <div className="doc-meta">
                            {doc.size < 1024 ? `${doc.size} B` : doc.size < 1048576 ? `${(doc.size / 1024).toFixed(1)} KB` : `${(doc.size / 1048576).toFixed(2)} MB`} · {doc.uploader} · {new Date(doc.upload_time.replace(' ', 'T') + 'Z').toLocaleDateString('zh-CN')}
                          </div>
                        </div>
                        {me?.permissions.delete_document && (
                          <button
                            className="delete-btn"
                            onClick={() => handleDeleteDocument(doc.filename)}
                          >
                            🗑️
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}

            {activeRightPanel === 'users' && me && (
              <UserManagement token={token} me={me} />
            )}

            {activeRightPanel === 'settings' && (
              <EnhancedSettingsPanel />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
};
