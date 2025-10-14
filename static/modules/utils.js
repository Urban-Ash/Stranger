// 公共工具方法模块：UI提示、HTML转义、字段值格式化

// HTML转义函数
export function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 显示提示消息
export function showToast(message) {
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('show');
  }, 100);

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => {
      if (toast.parentNode) {
        document.body.removeChild(toast);
      }
    }, 300);
  }, 2000);
}

// 值格式化（用于结果渲染）
export function formatValue(value, key) {
  if (Array.isArray(value)) {
    if (key === 'data_sources') {
      // 特殊处理数据来源，显示来源和时间
      return value
        .map((source) => {
          if (typeof source === 'object' && source.source) {
            const sourceText = source.source;
            const timeText = source.captured_at
              ? new Date(source.captured_at).toLocaleString('zh-CN')
              : '';
            return timeText ? `${sourceText} (${timeText})` : sourceText;
          }
          return source;
        })
        .join(', ');
    }
    // QQ数组：兼容对象数组，显示为 “昵称 (号码)” 或仅号码
    if (key === 'qqs' || key === 'qq') {
      const items = value
        .map((v) => {
          if (typeof v === 'string') {
            const s = String(v).trim();
            return s;
          }
          if (v && typeof v === 'object') {
            const num = String(v.qq ?? v.number ?? '').trim();
            const digits = num.replace(/\D/g, '');
            const label = v.name ? `${v.name} (${digits || num})` : (digits || num);
            return label;
          }
          return '';
        })
        .map((s) => String(s).trim())
        .filter((s) => s);
      const uniq = Array.from(new Set(items));
      return uniq.length > 0 ? uniq.join(', ') : '无';
    }
    // 微博UID数组：兼容对象数组，显示为 “用户名 (UID)” 或仅UID
    if (key === 'weibo_uids' || key === 'weibo_uid') {
      const items = value
        .map((v) => {
          if (typeof v === 'string') return String(v).trim();
          if (v && typeof v === 'object') {
            const uid = String(v.uid ?? '').trim();
            const digits = uid.replace(/\D/g, '');
            const label = v.name ? `${v.name} (${digits || uid})` : (digits || uid);
            return label;
          }
          return '';
        })
        .map((s) => String(s).trim())
        .filter((s) => s);
      const uniq = Array.from(new Set(items));
      return uniq.length > 0 ? uniq.join(', ') : '无';
    }
    // 手机数组：兼容对象数组，提取 number 或中文“手机号”
    if (key === 'phones' || key === 'phone') {
      const numbers = value
        .map((v) => {
          if (typeof v === 'string') return v;
          if (v && typeof v === 'object') {
            return v.number || v['手机号'] || '';
          }
          return '';
        })
        .map((s) => String(s).trim())
        .filter((s) => s);
      const uniq = Array.from(new Set(numbers));
      return uniq.length > 0 ? uniq.join(', ') : '无';
    }
    // 邮箱数组：去重
    if (key === 'emails' || key === 'email') {
      const emails = value
        .map((v) => {
          if (typeof v === 'string') return v;
          if (v && typeof v === 'object') return v.email || '';
          return '';
        })
        .map((s) => String(s).trim())
        .filter((s) => s);
      const uniq = Array.from(new Set(emails));
      return uniq.length > 0 ? uniq.join(', ') : '无';
    }
    return value.length > 0 ? value.join(', ') : '无';
  }

  if (typeof value === 'object' && value !== null) {
    if (key === 'metadata') {
      // 特殊处理metadata对象 - 分两行显示
      const parts = [];
      if (value.created_at) {
        parts.push(`创建: ${new Date(value.created_at).toLocaleString('zh-CN')}`);
      }
      if (value.updated_at) {
        parts.push(`更新: ${new Date(value.updated_at).toLocaleString('zh-CN')}`);
      }
      return parts.length > 0 ? parts.join('<br>') : '无';
    }
    // 单个手机对象
    if (key === 'phone') {
      const num = value.number || value['手机号'];
      return num ? String(num) : '无';
    }
    // 单个QQ对象
    if (key === 'qq' || key === 'qqs') {
      const num = String(value.qq ?? value.number ?? '').trim();
      const digits = num.replace(/\D/g, '');
      const label = value.name ? `${value.name} (${digits || num})` : (digits || num);
      return label || '无';
    }
    // 单个微博对象
    if (key === 'weibo_uid' || key === 'weibo_uids') {
      const uid = String(value.uid ?? '').trim();
      const digits = uid.replace(/\D/g, '');
      const label = value.name ? `${value.name} (${digits || uid})` : (digits || uid);
      return label || '无';
    }
    // 其他对象类型，尝试JSON格式化
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  return value || '无';
}

// 解析以逗号分隔的输入为数组（去空格、去空项）
export function splitCommaList(text) {
  if (!text) return [];
  return String(text)
    .split(',')
    .map((v) => v.trim())
    .filter((v) => v);
}