// 共享的状态面板组件：loading/empty/error 等统一渲染
import { escapeHtml } from './utils.js';
import { t } from './i18n.js?v=2';

// 类型与图标的配置映射，深度集成 i18n，可扩展更多状态
const PANEL_PRESETS = {
  loading: { icon: '', titleKey: 'loading', descKey: '' },
  error: { icon: '⚠️', titleKey: 'error_title', descKey: '' },
  service_unavailable: { icon: '🚧', titleKey: 'service_unavailable_title', descKey: 'service_unavailable_desc' },
  network_error: { icon: '📡', titleKey: 'network_error_title', descKey: 'network_error_desc' },
  success_add: { icon: '✅', titleKey: 'add_success', descKey: '' },
  success_edit: { icon: '✅', titleKey: 'edit_success', descKey: '' },
  success_delete: { icon: '✅', titleKey: 'delete_success', descKey: '' },
  empty: { icon: '📭', titleKey: 'no_results_title', descKey: 'no_results_desc' }
};

export function renderStatusPanel(container, { type = 'loading', title = '', desc = '', icon = '', retry = false, retryId = 'retryBtn' }) {
  if (!container) return;
  const preset = PANEL_PRESETS[type] || {};
  const resolvedTitle = title || (preset.titleKey ? t(preset.titleKey) : '');
  const resolvedDesc = desc || (preset.descKey ? t(preset.descKey) : '');
  const resolvedIcon = icon || preset.icon || '';
  const isLoading = type === 'loading';
  const spinner = isLoading ? '<div class="loading-spinner"></div>' : '';
  const iconHtml = resolvedIcon ? `<div class="status-icon">${escapeHtml(resolvedIcon)}</div>` : '';
  const retryBtn = retry ? `<button class="retry-btn" id="${escapeHtml(retryId)}">${escapeHtml(t('retry'))}</button>` : '';
  container.innerHTML = `
    <div class="status-panel ${escapeHtml(type)}">
      ${spinner}
      ${iconHtml}
      ${resolvedTitle ? `<h3>${escapeHtml(resolvedTitle)}</h3>` : ''}
      ${resolvedDesc ? `<p>${escapeHtml(resolvedDesc)}</p>` : ''}
      ${retryBtn}
    </div>
  `;
}

// 抽象重试绑定，减少重复代码
export function bindRetry(container, handler, retryId = 'retryBtn') {
  if (!container || typeof handler !== 'function') return;
  const btn = container.querySelector(`#${CSS.escape(retryId)}`) || document.getElementById(retryId);
  if (btn) btn.addEventListener('click', handler, { once: true });
}