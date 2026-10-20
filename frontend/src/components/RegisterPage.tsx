import { useState, useRef, useEffect } from 'react';
import './RegisterPage.css';
import { ParticleBackground } from './ParticleBackground';
import { API_BASE_URL } from '../api/client';

interface RegisterPageProps {
  onRegisterSuccess: () => void;
  onSwitchToLogin: () => void;
}

const API_BASE = API_BASE_URL;

export function RegisterPage({ onRegisterSuccess, onSwitchToLogin }: RegisterPageProps) {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [keyCode, setKeyCode] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
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

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setSuccess('');

    // 验证密码
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      setIsLoading(false);
      return;
    }

    if (password.length < 6) {
      setError('密码长度至少为 6 位');
      setIsLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/v2/company/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key_code: keyCode, company_name: companyName, username, email, password })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : '注册失败，请检查填写内容');
      }

      setSuccess('注册成功！正在跳转到登录页...');
      setTimeout(() => {
        onRegisterSuccess();
      }, 1500);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="register-page-enhanced">
      <ParticleBackground />

      <div className="register-container">
        <div className="register-card-enhanced" ref={cardRef}>
          {/* 流光边框 */}
          <div className="card-glow"></div>

          <div className="card-content">
            {/* Logo 和标题 */}
            <div className="register-header">
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
              <h1 className="register-title">注册公司账号</h1>
              <p className="register-subtitle">凭平台老板提供的密钥注册，员工账号由上级在「用户管理」中创建</p>
            </div>

            {/* 注册表单 */}
            <form onSubmit={handleRegister} className="register-form-enhanced">
              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 8a3 3 0 100-6 3 3 0 000 6zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                  </svg>
                  用户名
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="请输入用户名"
                  required
                  className="input-enhanced"
                  minLength={2}
                />
              </div>

              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M2 3a1 1 0 011-1h10a1 1 0 011 1v10a1 1 0 01-1 1H3a1 1 0 01-1-1V3zm1 0v1l5 3 5-3V3H3zm0 2.5V13h10V5.5l-5 3-5-3z"/>
                  </svg>
                  邮箱
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="请输入邮箱"
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
                  placeholder="请输入密码（至少6位）"
                  required
                  className="input-enhanced"
                  minLength={6}
                />
              </div>

              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M11 5V4a3 3 0 10-6 0v1H4a1 1 0 00-1 1v7a1 1 0 001 1h8a1 1 0 001-1V6a1 1 0 00-1-1h-1zM7 4a1 1 0 012 0v1H7V4z"/>
                  </svg>
                  确认密码
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="再次输入密码"
                  required
                  className="input-enhanced"
                  minLength={6}
                />
              </div>

              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M11 5V4a3 3 0 10-6 0v1H4a1 1 0 00-1 1v7a1 1 0 001 1h8a1 1 0 001-1V6a1 1 0 00-1-1h-1zM7 4a1 1 0 012 0v1H7V4z"/>
                  </svg>
                  注册密钥
                </label>
                <input
                  type="text"
                  value={keyCode}
                  onChange={(e) => setKeyCode(e.target.value.trim().toUpperCase())}
                  placeholder="请输入平台老板发给你的密钥"
                  required
                  className="input-enhanced"
                />
              </div>

              <div className="form-group-enhanced">
                <label>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M2 14V3l6-2 6 2v11H9v-3H7v3H2zm3-9v2h2V5H5zm4 0v2h2V5H9zM5 8v2h2V8H5zm4 0v2h2V8H9z"/>
                  </svg>
                  公司名称
                </label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="请输入公司名称"
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

              {success && (
                <div className="success-message-enhanced">
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm3.97 6.03l-5 5a.75.75 0 01-1.06 0l-2-2a.75.75 0 111.06-1.06L6.5 9.44l4.47-4.47a.75.75 0 111.06 1.06z"/>
                  </svg>
                  {success}
                </div>
              )}

              <button
                type="submit"
                className="register-button-enhanced"
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="loading-spinner"></span>
                    注册中...
                  </>
                ) : (
                  <>
                    <span>注册</span>
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 0L6.6 1.4 12.2 7H0v2h12.2l-5.6 5.6L8 16l8-8-8-8z"/>
                    </svg>
                  </>
                )}
              </button>
            </form>

            {/* 登录入口 */}
            <div className="login-link-container">
              <span className="login-hint">已有账号？</span>
              <button
                type="button"
                className="login-link-button"
                onClick={onSwitchToLogin}
              >
                立即登录
              </button>
            </div>
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
