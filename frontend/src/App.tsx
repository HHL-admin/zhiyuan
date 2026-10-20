import { useState } from 'react';
import './App.css';
import { ThreeColumnLayout } from './components/ThreeColumnLayout';
import { LoginPage } from './components/LoginPage';
import { RegisterPage } from './components/RegisterPage';

// 主应用组件
function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('user');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [showRegister, setShowRegister] = useState(false);

  // 登录处理
  const handleLogin = (newToken: string, newUser: any) => {
    setToken(newToken);
    setUser(newUser);
  };

  // 登出
  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken('');
    setUser(null);
    setShowRegister(false);
  };

  // 注册成功后跳转到登录
  const handleRegisterSuccess = () => {
    setShowRegister(false);
  };

  // 如果未登录，显示登录或注册页面
  if (!token || !user) {
    if (showRegister) {
      return (
        <RegisterPage
          onRegisterSuccess={handleRegisterSuccess}
          onSwitchToLogin={() => setShowRegister(false)}
        />
      );
    }
    return (
      <LoginPage
        onLogin={handleLogin}
        onSwitchToRegister={() => setShowRegister(true)}
      />
    );
  }

  return <ThreeColumnLayout user={user} onLogout={handleLogout} token={token} />;
}

export default App;
