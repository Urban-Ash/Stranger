// 添加数据模块：负责添加弹窗的展示与提交逻辑
import { showToast } from './utils.js';
import { t } from './i18n.js?v=2';
import { renderStatusPanel, bindRetry } from './status_panel.js';
import { requestJson } from './api.js';
import { splitCommaList } from './utils.js';

export function setupAddModal() {
  const titleEl = document.getElementById('strangerTitle');
  const addModal = document.getElementById('addModal');
  const closeModal = document.getElementById('closeModal');
  const cancelAdd = document.getElementById('cancelAdd');
  const addForm = document.getElementById('addDataForm');

  if (!titleEl || !addModal || !addForm) return;

  // 点击标题打开添加弹窗（沿用原有交互）
  titleEl.addEventListener('click', () => {
    addForm.reset();
    addModal.style.display = 'block';
  });

  function closeAdd() {
    addModal.style.display = 'none';
  }

  if (closeModal) closeModal.addEventListener('click', closeAdd);
  if (cancelAdd) cancelAdd.addEventListener('click', closeAdd);
  addModal.addEventListener('click', (e) => { if (e.target === addModal) closeAdd(); });

  // 提交新增
  addForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById('addStatus');
    if (statusEl) renderStatusPanel(statusEl, { type: 'loading', title: t('loading') });

    // 收集表单并规范化为后端 profile 结构
    const fd = new FormData(addForm);
    const get = (k) => (fd.get(k) || '').toString().trim();

    const phones = splitCommaList(get('phones'));
    const qqs = splitCommaList(get('qqs'));
    const weibo = get('weibo_uid') ? [get('weibo_uid')] : [];
    const emails = get('email') ? [get('email')] : [];

    const payload = {
      name: get('name') || null,
      id_card: get('id_card') || null,
      gender: get('gender') || null,
      birth_date: get('birth_date') || null,
      phones,
      qqs,
      weibo_uids: weibo,
      emails,
      company: get('company') || null,
      position: get('position') || null
      // 其余自定义字段后端会忽略或作为兼容占位，不强制传递
    };

    try {
      const data = await requestJson('/api/customer', { method: 'POST', body: payload });
      if (!data || !data.success) {
        const msg = (data && (data.message || data.error)) || t('unknown');
        const status = (data && data.status) || 500;
        if (status === 503) {
          if (statusEl) {
            renderStatusPanel(statusEl, { type: 'service_unavailable', retry: true, retryId: 'retryAddBtn' });
            bindRetry(statusEl, () => addForm.dispatchEvent(new Event('submit')), 'retryAddBtn');
          } else {
            showToast(`${t('service_unavailable_title')}: ${t('service_unavailable_desc')}`);
          }
          return;
        }
        if (statusEl) {
          renderStatusPanel(statusEl, { type: 'error', retry: true, retryId: 'retryAddBtn', desc: msg });
          bindRetry(statusEl, () => addForm.dispatchEvent(new Event('submit')), 'retryAddBtn');
        }
        throw new Error(msg);
      }
      if (statusEl) {
        renderStatusPanel(statusEl, { type: 'success_add' });
      }
      setTimeout(() => {
        if (statusEl) statusEl.innerHTML = '';
        closeAdd();
      }, 800);
      // 可选：将新增结果加入当前搜索结果集
      const inserted = data.data || payload;
      if (Array.isArray(window.searchResults)) {
        window.searchResults.unshift(inserted);
        // 触发重渲染（延迟到下一个 tick，避免阻塞）
        setTimeout(() => {
          const { displayResults } = requireRender();
          displayResults(window.searchResults);
        }, 0);
      }
    } catch (err) {
      const statusEl = document.getElementById('addStatus');
      if (statusEl) {
        if (err && err.status === 503) {
          renderStatusPanel(statusEl, { type: 'service_unavailable', retry: true, retryId: 'retryAddBtn' });
        } else if (err && err.name === 'TypeError') {
          renderStatusPanel(statusEl, { type: 'network_error', retry: true, retryId: 'retryAddBtn' });
        } else {
          renderStatusPanel(statusEl, { type: 'error', retry: true, retryId: 'retryAddBtn', desc: err.message });
        }
        bindRetry(statusEl, () => addForm.dispatchEvent(new Event('submit')), 'retryAddBtn');
      } else {
        showToast(t('add_failed_prefix') + err.message);
      }
    }
  });
}

function requireRender() {
  // 动态导入以避免循环依赖
  // eslint-disable-next-line no-undef
  return window.__renderModule || import('./search.js?v=5').then(mod => (window.__renderModule = mod));
}