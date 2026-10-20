import React, { useState } from 'react';
import './EnhancedSettingsPanel.css';

interface SettingItem {
  id: string;
  label: string;
  type: 'toggle' | 'select' | 'input' | 'password';
  value: any;
  options?: { label: string; value: string }[];
  placeholder?: string;
}

const EnhancedSettingsPanel: React.FC = () => {
  // 从 localStorage 加载设置
  const loadSettings = (): SettingItem[] => {
    const saved = localStorage.getItem('app_settings');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // 更新模型选项列表（保留用户选择的值）
        const migrated = parsed.map((setting: SettingItem) =>
          setting.id === 'model'
            ? {
                ...setting,
                options: [
                  { label: 'GPT-5.6-sol', value: 'gpt-5.6-sol' },
                  { label: 'DeepSeek Chat', value: 'deepseek-chat' },
                  { label: 'DeepSeek Reasoner (R1)', value: 'deepseek-reasoner' }
                ]
              }
            : setting
        );
        return migrated;
      } catch (e) {
        console.error('加载设置失败:', e);
      }
    }
    return [
      {
        id: 'theme',
        label: '主题模式',
        type: 'select',
        value: 'dark',
        options: [
          { label: '深色', value: 'dark' },
          { label: '浅色', value: 'light' },
          { label: '自动', value: 'auto' }
        ]
      },
      {
        id: 'notifications',
        label: '消息通知',
        type: 'toggle',
        value: true
      },
      {
        id: 'sound',
        label: '提示音',
        type: 'toggle',
        value: false
      },
      {
        id: 'apiKey',
        label: 'API Key（可选）',
        type: 'password',
        value: '',
        placeholder: '不填写则使用系统默认豆包免费额度'
      },
      {
        id: 'apiBaseUrl',
        label: 'API 中转地址（可选）',
        type: 'input',
        value: '',
        placeholder: '不填写则使用默认配置'
      },
      {
        id: 'model',
        label: 'AI 模型',
        type: 'select',
        value: 'gpt-5.6-sol',
        options: [
          { label: 'GPT-5.6-sol', value: 'gpt-5.6-sol' },
          { label: 'DeepSeek Chat', value: 'deepseek-chat' },
          { label: 'DeepSeek Reasoner (R1)', value: 'deepseek-reasoner' }
        ]
      },
      {
        id: 'temperature',
        label: '温度参数',
        type: 'input',
        value: '0.7',
        placeholder: '0.0 - 1.0'
      }
    ];
  };

  const [settings, setSettings] = useState<SettingItem[]>(loadSettings());

  // 删除 API Key（立即保存）
  const handleClearApiKey = () => {
    const newSettings = settings.map(setting =>
      setting.id === 'apiKey' ? { ...setting, value: '' } : setting
    );
    setSettings(newSettings);
    localStorage.setItem('app_settings', JSON.stringify(newSettings));
  };

  // 删除 API 中转地址（立即保存）
  const handleClearApiBaseUrl = () => {
    const newSettings = settings.map(setting =>
      setting.id === 'apiBaseUrl' ? { ...setting, value: '' } : setting
    );
    setSettings(newSettings);
    localStorage.setItem('app_settings', JSON.stringify(newSettings));
  };

  const handleToggle = (id: string) => {
    setSettings(prev =>
      prev.map(setting =>
        setting.id === id
          ? { ...setting, value: !setting.value }
          : setting
      )
    );
  };

  const handleSelectChange = (id: string, value: string) => {
    setSettings(prev =>
      prev.map(setting =>
        setting.id === id
          ? { ...setting, value }
          : setting
      )
    );
  };

  const handleInputChange = (id: string, value: string) => {
    console.log(`🔧 输入框变化: ${id} = ${value}`);
    setSettings(prev =>
      prev.map(setting =>
        setting.id === id
          ? { ...setting, value }
          : setting
      )
    );
  };

  const handleSave = () => {
    console.log('🔧 点击了保存按钮');
    console.log('🔧 当前 settings 状态:', settings);

    // 保存到 localStorage
    localStorage.setItem('app_settings', JSON.stringify(settings));

    console.log('🔧 已保存到 localStorage');
    console.log('🔧 验证保存结果:', localStorage.getItem('app_settings'));

    // 显示保存成功提示
    alert('设置已保存！');
  };

  return (
    <div className="enhanced-settings-panel">
      <div className="settings-header">
        <div className="settings-icon">⚙️</div>
        <h3>系统设置</h3>
      </div>

      <div className="settings-list">
        {settings.map((setting, index) => {
          // 隐藏空的 API Key 和 API 中转地址
          if ((setting.id === 'apiKey' || setting.id === 'apiBaseUrl') && !setting.value) {
            return null;
          }

          return (
            <div
              key={setting.id}
              className="setting-item"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="setting-label">
                <span>{setting.label}</span>
              </div>

              <div className="setting-control">
                {setting.type === 'toggle' && (
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={setting.value}
                      onChange={() => handleToggle(setting.id)}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                )}

                {setting.type === 'select' && (
                  <select
                    className="setting-select"
                    value={setting.value}
                    onChange={(e) => handleSelectChange(setting.id, e.target.value)}
                  >
                    {setting.options?.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                )}

                {setting.type === 'input' && setting.id !== 'apiBaseUrl' && (
                  <input
                    type="text"
                    className="setting-input"
                    value={setting.value}
                    placeholder={setting.placeholder}
                    onChange={(e) => handleInputChange(setting.id, e.target.value)}
                  />
                )}

                {setting.type === 'password' && (
                  <div className="input-with-delete">
                    <input
                      type="password"
                      className="setting-input"
                      value={setting.value}
                      placeholder={setting.placeholder}
                      onChange={(e) => handleInputChange(setting.id, e.target.value)}
                    />
                    {setting.value && (
                      <button
                        className="delete-btn"
                        onClick={handleClearApiKey}
                        title="删除 API Key"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                )}

                {setting.type === 'input' && setting.id === 'apiBaseUrl' && (
                  <div className="input-with-delete">
                    <input
                      type="text"
                      className="setting-input"
                      value={setting.value}
                      placeholder={setting.placeholder}
                      onChange={(e) => handleInputChange(setting.id, e.target.value)}
                    />
                    {setting.value && (
                      <button
                        className="delete-btn"
                        onClick={handleClearApiBaseUrl}
                        title="删除 API 中转地址"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 添加 API 配置按钮 */}
      {!settings.find(s => s.id === 'apiKey')?.value && (
        <div className="add-api-section">
          <button
            className="add-api-btn"
            onClick={() => {
              const input = prompt('请输入您的 API Key（可选）：');
              if (input !== null) {
                handleInputChange('apiKey', input);
              }
            }}
          >
            ＋ 添加 API Key（可选）
          </button>
          <div className="add-api-hint">
            💡 不填写即使用系统默认豆包免费额度
          </div>
        </div>
      )}

      {!settings.find(s => s.id === 'apiBaseUrl')?.value && (
        <div className="add-api-section">
          <button
            className="add-api-btn"
            onClick={() => {
              const input = prompt('请输入 API 中转地址（可选）：');
              if (input !== null) {
                handleInputChange('apiBaseUrl', input);
              }
            }}
          >
            ＋ 添加 API 中转地址（可选）
          </button>
        </div>
      )}

      <div className="settings-footer">
        <button className="save-settings-btn" onClick={handleSave}>
          <span>💾</span>
          <span>保存设置</span>
        </button>
      </div>
    </div>
  );
};

export default EnhancedSettingsPanel;
