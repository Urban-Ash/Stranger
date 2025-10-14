// 统一的请求封装：返回 JSON，失败抛出包含 status 的 Error

export async function requestJson(url, { method = 'GET', headers = {}, body } = {}) {
  const opts = { method, headers, body };
  if (body && typeof body === 'object' && !(body instanceof FormData)) {
    opts.headers = { 'Content-Type': 'application/json', ...headers };
    opts.body = typeof body === 'string' ? body : JSON.stringify(body);
  }
  let resp;
  try {
    resp = await fetch(url, opts);
  } catch (err) {
    const e = new Error(err && err.message ? err.message : 'Network error');
    e.name = err && err.name ? err.name : 'TypeError';
    e.status = 0; // 网络错误统一使用 0
    throw e;
  }
  let data = null;
  const ct = (resp.headers && resp.headers.get && resp.headers.get('content-type')) || '';
  if (ct.includes('application/json')) {
    try { data = await resp.json(); } catch { data = null; }
  }
  if (!resp.ok) {
    const msg = (data && (data.message || data.error)) || `HTTP ${resp.status}`;
    const e = new Error(msg);
    e.status = resp.status;
    throw e;
  }
  return data;
}