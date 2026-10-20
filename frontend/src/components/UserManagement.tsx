import React, { useCallback, useEffect, useState } from 'react';
import './UserManagement.css';
import { API_BASE_URL } from '../api/client';

const API = `${API_BASE_URL}/v2`;

export interface MyInfo {
  id: number;
  username: string;
  user_level: number | null;
  level_name: string;
  company_id: number | null;
  company_name: string | null;
  permissions: {
    generate_keys: boolean;
    upload_document: boolean;
    delete_document: boolean;
    manage_users: boolean;
    creatable_levels: number[];
    change_level: boolean;
    delete_user: boolean;
  };
}

interface KeyItem {
  id: number;
  key_code: string;
  used: number;
  used_by_username: string | null;
  company_name: string | null;
  expires_at: string;
  created_at: string;
}

interface Company {
  id: number;
  name: string;
  owner_username: string | null;
  member_count: number;
  created_at: string;
}

interface CompanyUser {
  id: number;
  username: string;
  email: string;
  user_level: number;
  level_name: string;
  is_self: boolean;
}

const LEVEL_NAMES: Record<number, string> = { 2: '公司老板', 3: '高级用户', 4: '低级用户' };

type RequestFn = (path: string, init?: RequestInit) => Promise<any>;
type NotifyFn = (type: 'ok' | 'err', text: string) => void;

interface Props {
  token: string;
  me: MyInfo;
}

const UserManagement: React.FC<Props> = ({ token, me }) => {
  const [message, setMessage] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);

  const request = useCallback<RequestFn>(
    async (path, init = {}) => {
      const res = await fetch(`${API}${path}`, {
        ...init,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          ...(init.headers || {}),
        },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((d: any) => d.msg).join('；')
          : data.detail;
        throw new Error(detail || `请求失败 (${res.status})`);
      }
      return data;
    },
    [token]
  );

  const notify = useCallback<NotifyFn>((type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 4000);
  }, []);

  return (
    <div className="um">
      <div className="um-me">
        <span className={`um-badge level-${me.user_level ?? 0}`}>{me.level_name}</span>
        <span className="um-me-name">{me.username}</span>
        {me.company_name && <span className="um-me-company">· {me.company_name}</span>}
      </div>

      {message && <div className={`um-msg ${message.type}`}>{message.text}</div>}

      {me.permissions.generate_keys && <PlatformPanel request={request} notify={notify} />}
      {me.permissions.manage_users && <CompanyPanel me={me} request={request} notify={notify} />}
      {!me.permissions.generate_keys && !me.permissions.manage_users && (
        <div className="um-empty">
          {me.user_level
            ? '你是低级用户：可以上传文档、查询自己的文档，没有用户管理权限。'
            : '当前账号尚未分配层级，请联系上级。'}
        </div>
      )}
    </div>
  );
};

/* ==================== 平台老板：注册密钥 ==================== */

const PlatformPanel: React.FC<{ request: RequestFn; notify: NotifyFn }> = ({ request, notify }) => {
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [days, setDays] = useState(7);
  const [newKey, setNewKey] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [k, c] = await Promise.all([request('/platform/keys'), request('/platform/companies')]);
      setKeys(k.keys);
      setCompanies(c.companies);
    } catch (e: any) {
      notify('err', e.message);
    }
  }, [request, notify]);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async () => {
    setBusy(true);
    try {
      const k = await request('/platform/keys', {
        method: 'POST',
        body: JSON.stringify({ expires_days: days }),
      });
      setNewKey(k.key_code);
      load();
    } catch (e: any) {
      notify('err', e.message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      notify('ok', `已复制 ${text}`);
    } catch {
      notify('err', '复制失败，请手动选中复制');
    }
  };

  const revoke = async (k: KeyItem) => {
    if (!confirm(`作废密钥 ${k.key_code}？`)) return;
    try {
      await request(`/platform/keys/${k.id}`, { method: 'DELETE' });
      notify('ok', '密钥已作废');
      load();
    } catch (e: any) {
      notify('err', e.message);
    }
  };

  const keyStatus = (k: KeyItem) => {
    if (k.used) {
      return `已使用 · ${k.used_by_username ?? ''}${k.company_name ? `（${k.company_name}）` : ''}`;
    }
    // 后端存的是 UTC 时间
    if (new Date(k.expires_at.replace(' ', 'T') + 'Z') < new Date()) return '已过期';
    return `未使用 · ${k.expires_at.slice(0, 10)} 到期`;
  };

  return (
    <>
      <section className="um-card">
        <h4>🔑 生成公司注册密钥</h4>
        <p className="um-hint">
          把密钥发给公司老板，老板在登录页点「注册」，填写密钥和公司名称即可注册公司账号。一个密钥只能用一次。
        </p>
        <div className="um-row">
          <label className="um-inline">
            有效期
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={1}>1 天</option>
              <option value={7}>7 天</option>
              <option value={30}>30 天</option>
            </select>
          </label>
          <button className="um-btn primary" onClick={generate} disabled={busy}>
            {busy ? '生成中...' : '生成密钥'}
          </button>
        </div>
        {newKey && (
          <div className="um-newkey">
            <code>{newKey}</code>
            <button className="um-btn" onClick={() => copy(newKey)}>复制</button>
          </div>
        )}
      </section>

      <section className="um-card">
        <h4>密钥列表（{keys.length}）</h4>
        {keys.length === 0 ? (
          <div className="um-empty">还没有生成过密钥</div>
        ) : (
          <ul className="um-list">
            {keys.map((k) => (
              <li key={k.id} className="um-item">
                <div className="um-item-main">
                  <code className="um-code">{k.key_code}</code>
                  <span className={`um-sub ${k.used ? 'used' : ''}`}>{keyStatus(k)}</span>
                </div>
                {!k.used && (
                  <div className="um-actions">
                    <button className="um-btn small" onClick={() => copy(k.key_code)}>复制</button>
                    <button className="um-btn small danger" onClick={() => revoke(k)}>作废</button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="um-card">
        <h4>🏢 已注册公司（{companies.length}）</h4>
        <p className="um-hint">平台老板只能看到公司名称和人数，看不到公司文档。</p>
        {companies.length === 0 ? (
          <div className="um-empty">暂无公司</div>
        ) : (
          <ul className="um-list">
            {companies.map((c) => (
              <li key={c.id} className="um-item">
                <div className="um-item-main">
                  <span className="um-name">{c.name}</span>
                  <span className="um-sub">
                    老板：{c.owner_username ?? '-'} · {c.member_count} 人
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
};

/* ==================== 公司老板 / 高级用户：下级用户 ==================== */

const CompanyPanel: React.FC<{ me: MyInfo; request: RequestFn; notify: NotifyFn }> = ({
  me,
  request,
  notify,
}) => {
  const levels = me.permissions.creatable_levels;
  const [users, setUsers] = useState<CompanyUser[]>([]);
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    user_level: levels[levels.length - 1],
  });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await request('/company/users');
      setUsers(data.users);
    } catch (e: any) {
      notify('err', e.message);
    }
  }, [request, notify]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const data = await request('/company/users', { method: 'POST', body: JSON.stringify(form) });
      notify('ok', data.message);
      setForm({ ...form, username: '', email: '', password: '' });
      load();
    } catch (e: any) {
      notify('err', e.message);
    } finally {
      setBusy(false);
    }
  };

  const changeLevel = async (u: CompanyUser, level: number) => {
    if (!confirm(`将 ${u.username} 调整为${LEVEL_NAMES[level]}？`)) return;
    try {
      const data = await request(`/company/users/${u.id}/level`, {
        method: 'PUT',
        body: JSON.stringify({ user_level: level }),
      });
      notify('ok', data.message);
      load();
    } catch (e: any) {
      notify('err', e.message);
    }
  };

  const remove = async (u: CompanyUser) => {
    if (!confirm(`确定删除用户 ${u.username}？删除后该账号无法登录。`)) return;
    try {
      const data = await request(`/company/users/${u.id}`, { method: 'DELETE' });
      notify('ok', data.message);
      load();
    } catch (e: any) {
      notify('err', e.message);
    }
  };

  const canEdit = me.permissions.change_level || me.permissions.delete_user;

  return (
    <>
      <section className="um-card">
        <h4>➕ 创建下级用户</h4>
        <form className="um-form" onSubmit={create}>
          <input
            placeholder="用户名（至少2个字符）"
            value={form.username}
            minLength={2}
            required
            onChange={(e) => setForm({ ...form, username: e.target.value })}
          />
          <input
            placeholder="邮箱"
            type="email"
            value={form.email}
            required
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
          <input
            placeholder="初始密码（至少6位）"
            type="text"
            value={form.password}
            minLength={6}
            required
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
          <select
            value={form.user_level}
            onChange={(e) => setForm({ ...form, user_level: Number(e.target.value) })}
          >
            {levels.map((l) => (
              <option key={l} value={l}>
                {LEVEL_NAMES[l]}
              </option>
            ))}
          </select>
          <button className="um-btn primary" type="submit" disabled={busy}>
            {busy ? '创建中...' : '创建用户'}
          </button>
        </form>
        <p className="um-hint">创建后把用户名和初始密码告诉对方，对方直接登录即可。</p>
      </section>

      <section className="um-card">
        <h4>
          👥 {me.user_level === 2 ? '公司成员' : '我和我的下级'}（{users.length}）
        </h4>
        {users.length === 0 ? (
          <div className="um-empty">暂无用户</div>
        ) : (
          <ul className="um-list">
            {users.map((u) => (
              <li key={u.id} className="um-item">
                <div className="um-item-main">
                  <span className="um-name">
                    {u.username}
                    {u.is_self && <span className="um-self">（我）</span>}
                  </span>
                  <span className="um-sub">{u.email}</span>
                </div>
                <span className={`um-badge level-${u.user_level}`}>{u.level_name}</span>
                {!u.is_self && canEdit && (
                  <div className="um-actions">
                    {me.permissions.change_level && u.user_level === 4 && (
                      <button className="um-btn small" onClick={() => changeLevel(u, 3)}>升级</button>
                    )}
                    {me.permissions.change_level && u.user_level === 3 && (
                      <button className="um-btn small" onClick={() => changeLevel(u, 4)}>降级</button>
                    )}
                    {me.permissions.delete_user && (
                      <button className="um-btn small danger" onClick={() => remove(u)}>删除</button>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
};

export default UserManagement;
