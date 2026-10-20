import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { knowledgeApi } from '../api/knowledge';
import type { SourceDocument } from '../types';
import './ChatInterface.css';
import './MarkdownContent.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceDocument[];
  timestamp: Date;
}

interface ChatInterfaceProps {
  sessionId: string;
  initialMessages: Message[];
  onMessagesChange: (messages: Message[]) => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  sessionId,
  initialMessages,
  onMessagesChange,
}) => {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSources, setShowSources] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const shouldAutoScrollRef = useRef(true); // 控制是否自动滚动

  // 会话切换时重置消息
  useEffect(() => {
    setMessages(initialMessages);
  }, [sessionId, initialMessages]);

  // 消息变化时通知父组件
  useEffect(() => {
    if (messages.length > 0) {
      onMessagesChange(messages);
    }
  }, [messages]);

  // 检测用户是否在查看历史消息
  const handleScroll = () => {
    if (!messagesContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;

    // 如果用户滚动到接近底部，恢复自动滚动
    // 如果用户向上滚动查看历史，禁用自动滚动
    shouldAutoScrollRef.current = isNearBottom;
  };

  const scrollToBottom = () => {
    if (shouldAutoScrollRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // 只在应该自动滚动时才滚动
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [input]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}-${Math.random()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    shouldAutoScrollRef.current = true; // 发送新消息时启用自动滚动

    const assistantMessageId = `assistant-${Date.now()}-${Math.random()}`;
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      sources: [],
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, assistantMessage]);

    // 本地累加器，避免严格模式重复
    let accumulatedContent = '';
    // 节流更新：最多每 100ms 更新一次 UI
    let updatePending = false;

    const updateMessage = () => {
      setMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg && lastMsg.id === assistantMessageId) {
          newMessages[newMessages.length - 1] = {
            ...lastMsg,
            content: accumulatedContent,
          };
        }
        return newMessages;
      });
      updatePending = false;
    };

    try {
      // 从 localStorage 读取设置
      const settingsStr = localStorage.getItem('app_settings');
      let apiKey = '';
      let apiBaseUrl = '';
      let model = 'gpt-5.6-sol';
      let temperature = 0.7;

      if (settingsStr) {
        try {
          const settings = JSON.parse(settingsStr);
          const apiKeySetting = settings.find((s: any) => s.id === 'apiKey');
          const apiBaseUrlSetting = settings.find((s: any) => s.id === 'apiBaseUrl');
          const modelSetting = settings.find((s: any) => s.id === 'model');
          const tempSetting = settings.find((s: any) => s.id === 'temperature');

          if (apiKeySetting) apiKey = apiKeySetting.value;
          if (apiBaseUrlSetting) apiBaseUrl = apiBaseUrlSetting.value;
          if (modelSetting) model = modelSetting.value;
          if (tempSetting) temperature = parseFloat(tempSetting.value) || 0.7;

          // 调试日志：打印读取到的设置
          console.log('📥 从 localStorage 读取的设置:');
          console.log('  - apiKey:', apiKey ? `${apiKey.slice(0, 10)}...` : '(空)');
          console.log('  - apiBaseUrl:', apiBaseUrl || '(空)');
          console.log('  - model:', model);
          console.log('  - temperature:', temperature);
        } catch (e) {
          console.error('解析设置失败:', e);
        }
      }

      // 构造请求参数：只有当用户填写了值时才传递
      const queryRequest: any = {
        question: userMessage.content,
        top_k: 4,
        model: model,
        temperature: temperature,
      };

      // 只有当 API Key 不为空时才传递（覆盖后端默认值）
      if (apiKey && apiKey.trim()) {
        queryRequest.api_key = apiKey;
      }

      // 只有当 API Base URL 不为空时才传递（覆盖后端默认值）
      if (apiBaseUrl && apiBaseUrl.trim()) {
        queryRequest.api_base_url = apiBaseUrl;
      }

      // 调试日志：打印最终发送的请求
      console.log('🚀 发送给后端的请求参数:', queryRequest);

      await knowledgeApi.queryStream(
        queryRequest,
        (data) => {
          if (data.type === 'sources') {
            setMessages((prev) => {
              const newMessages = [...prev];
              newMessages[newMessages.length - 1] = {
                ...newMessages[newMessages.length - 1],
                sources: data.data,
              };
              return newMessages;
            });
          } else if (data.type === 'content') {
            // 累加到本地变量
            accumulatedContent += data.data;
            // 节流更新：如果没有待处理的更新，则安排一个（100ms 间隔）
            if (!updatePending) {
              updatePending = true;
              setTimeout(updateMessage, 100);
            }
          } else if (data.type === 'error') {
            setMessages((prev) => {
              const newMessages = [...prev];
              newMessages[newMessages.length - 1] = {
                ...newMessages[newMessages.length - 1],
                content: `[错误] 查询失败: ${data.data}`,
              };
              return newMessages;
            });
          }
        },
        (error) => {
          setMessages((prev) => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              ...newMessages[newMessages.length - 1],
              content: `[错误] 查询失败: ${error.message}`,
            };
            return newMessages;
          });
          setIsLoading(false);
        },
        () => {
          // 流式结束后，确保最后一次更新
          if (updatePending) {
            updateMessage();
          } else if (accumulatedContent) {
            updateMessage();
          }
          setIsLoading(false);
        }
      );
    } catch (error: any) {
      setMessages((prev) => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1] = {
          ...newMessages[newMessages.length - 1],
          content: `[错误] 查询失败: ${error.message}`,
        };
        return newMessages;
      });
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  return (
    <div className="deepseek-chat">
      {/* 消息列表 */}
      <div className="deepseek-messages" ref={messagesContainerRef} onScroll={handleScroll}>
        {messages.length === 0 ? (
          <div className="deepseek-welcome">
            <div className="welcome-icon">💬</div>
            <h3>智能问答助手</h3>
            <p>基于已上传的文档为您解答问题</p>
            <div className="welcome-tips">
              <div className="tip-item">
                <span className="tip-icon">📚</span>
                <span>支持文档检索</span>
              </div>
              <div className="tip-item">
                <span className="tip-icon">🤖</span>
                <span>AI 智能理解</span>
              </div>
              <div className="tip-item">
                <span className="tip-icon">⚡</span>
                <span>实时流式回复</span>
              </div>
            </div>
            <div className="welcome-notice">
              💡 无需配置，直接使用 | 也可在设置中填写您的 API Key
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <div key={msg.id} className={`deepseek-message ${msg.role}`}>
                <div className="message-avatar">
                  {msg.role === 'user' ? (
                    <div className="avatar-user">你</div>
                  ) : (
                    <img src="/images/ai-avatar.webp" alt="AI" className="avatar-bot-img" />
                  )}
                </div>

                <div className="message-body">
                  <div className="message-header">
                    <span className="message-role-name">
                      {msg.role === 'user' ? '你' : '助手'}
                    </span>
                    <span className="message-time">
                      {msg.timestamp.toLocaleTimeString('zh-CN', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>

                  <div className="message-content">
                    {msg.role === 'assistant' ? (
                      msg.content ? (
                        <div className="markdown-content">
                          <ReactMarkdown>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="thinking">
                          <span className="thinking-dot"></span>
                          <span className="thinking-dot"></span>
                          <span className="thinking-dot"></span>
                        </div>
                      )
                    ) : (
                      <p>{msg.content}</p>
                    )}
                  </div>

                  {msg.sources && msg.sources.length > 0 && (
                    <div className="message-sources">
                      <button
                        className="sources-toggle"
                        onClick={() => setShowSources(showSources === msg.id ? null : msg.id)}
                      >
                        <span className="sources-icon">📎</span>
                        <span>参考资料 ({msg.sources.length})</span>
                        <span className={`sources-arrow ${showSources === msg.id ? 'open' : ''}`}>▼</span>
                      </button>

                      {showSources === msg.id && (
                        <div className="sources-panel">
                          {msg.sources.map((source, sidx) => (
                            <div key={sidx} className="source-card">
                              <div className="source-card-header">
                                <span className="source-filename">{source.metadata.source}</span>
                                {source.score !== undefined && (
                                  <span className="source-similarity">
                                    相似度: {(1 - source.score).toFixed(3)}
                                  </span>
                                )}
                              </div>
                              <div className="source-card-content">{source.content}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* 输入区 */}
      <div className="deepseek-input-container">
        <form className="deepseek-input-form" onSubmit={handleSubmit}>
          <div className="input-wrapper">
            <textarea
              ref={textareaRef}
              className="deepseek-textarea"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
              disabled={isLoading}
              rows={1}
            />
            <button
              type="submit"
              className="deepseek-send-btn"
              disabled={isLoading || !input.trim()}
            >
              {isLoading ? (
                <span className="loading-spinner"></span>
              ) : (
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M22 2L11 13M22 2L15 22L11 13M22 2L2 9L11 13"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
