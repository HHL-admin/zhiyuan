import { useState, useRef, useEffect } from 'react';
import './LoginPage.css';
import { ParticleBackground } from './ParticleBackground';
import { API_BASE_URL } from '../api/client';

interface LoginPageProps {
  onLogin: (token: string, user: any) => void;
  onSwitchToRegister?: () => void;
}

const API_BASE = API_BASE_URL;

export function LoginPage({ onLogin, onSwitchToRegister }: LoginPageProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const cardRef = useRef<HTMLDivElement>(null);

  // 3D 倾斜效果
  useEffect(() => {
    const card = cardRef.current;
    if (!card) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      const rotateX = (y - centerY) / 20;
      const rotateY = (centerX - x) / 20;

      card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.02)`;
    };

    const handleMouseLeave = () => {
      card.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)';
    };

    card.addEventListener('mousemove', handleMouseMove);
    card.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      card.removeEventListener('mousemove', handleMouseMove);
      card.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(typeof err.detail === 'string' ? err.detail : '登录失败,请检查用户名和密码');
      }

      const data = await response.json();
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('user', JSON.stringify(data.user));
      onLogin(data.access_token, data.user);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page-enhanced">
      <ParticleBackground />

      <div className="login-container">
        <div className="login-card-enhanced" ref={cardRef}>
          {/* 流光边框 */}
          <div className="card-glow"></div>

          <div className="card-content">
            {/* Logo 和标题 */}
            <div className="login-header">
              <div className="logo-container">
                <div className="logo-ring"></div>
                <div className="logo-core">
                  <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                    <path d="M20 5 L35 12.5 L35 27.5 L20 35 L5 27.5 L5 12.5 Z"
                          stroke="url(#gradient)" strokeWidth="2" fill="none"/>
                    <circle cx="20" cy="20" r="8" fill="url(#gradient)" opacity="0.3"/>
                    <defs>
                      <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#6366f1" />
                        <stop offset="100%" stopColor="#a855f7" />
                      </linearGradient>
                    </defs>
                  </svg>
                </div>
              </div>
              <h1 className="login-title">知识库检索系统</h1>
              <p className="login-subtitle">AI-Powered Knowledge Retrieval</p>
            </div>

            {/* 登录表单 */}
            <form onSubmit={handleLogin} className="login-form-enhanced">
              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                  </svg>
                  用户名 / 邮箱
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名或邮箱"
                  required
                  className="input-enhanced"
                />
              </div>

              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M11 5V4a3 3 0 10-6 0v1H4a1 1 0 00-1 1v7a1 1 0 001 1h8a1 1 0 001-1V6a1 1 0 00-1-1h-1zM7 4a1 1 0 012 0v1H7V4z"/>
                  </svg>
                  密码
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                  required
                  className="input-enhanced"
                />
              </div>

              {error && (
                <div className="error-message-enhanced">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm1 12H7v-2h2v2zm0-3H7V4h2v5z"/>
                  </svg>
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="login-button-enhanced"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="loading-spinner"></span>
                    登录中...
                  </>
                ) : (
                  <>
                    <span>登录</span>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 0L6.6 1.4 12.2 7H0v2h12.2l-5.6 5.6L8 16l8-8-8-8z"/>
                    </svg>
                  </>
                )}
              </button>
            </form>

            {/* 注册入口 */}
            {onSwitchToRegister && (
              <div className="register-link-container">
                <span className="register-hint">还没有账号？</span>
                <button
                  type="button"
                  className="register-link-button"
                  onClick={onSwitchToRegister}
                >
                  立即注册
                </button>
              </div>
            )}
          </div>
        </div>

        {/* 装饰元素 */}
        <div className="decoration-ring ring-1"></div>
        <div className="decoration-ring ring-2"></div>
        <div className="decoration-ring ring-3"></div>
      </div>
    </div>
  );
}
