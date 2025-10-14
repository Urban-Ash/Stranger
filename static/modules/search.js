// 搜索模块：仅负责搜索流程与结果渲染入口
import { showToast, escapeHtml, formatValue } from './utils.js';
import { t, getLang } from './i18n.js?v=2';
import { renderStatusPanel, bindRetry } from './status_panel.js';

export function setupSearch({ onResults }) {
  const searchInput = document.getElementById('searchInput');
  const searchButton = document.getElementById('searchButton');
  const resultsContainer = document.getElementById('resultsContainer');
  const resultsContent = document.getElementById('resultsContent');
  const loadingIndicator = document.getElementById('loadingIndicator');
  // 已移除“精确/模糊”切换：统一后端仅精确匹配；保留自由文本模式按需触发

  let currentRequest; // AbortController

  if (!searchInput || !searchButton) return;

  searchInput.focus();

  // 输入为空时收起结果容器
  searchInput.addEventListener('input', () => {
    const query = searchInput.value.trim();
    if (!query) {
      resultsContainer.classList.remove('active');
    }
  });

  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      performSearch();
    }
  });
  searchButton.addEventListener('click', performSearch);

  function showLoading(show) {
    // 不再修改 #resultsContent 的 display，避免打断 flex 布局与 gap
    if (loadingIndicator) {
      loadingIndicator.style.display = 'none';
    }
    if (resultsContent && show) {
      renderStatusPanel(resultsContent, { type: 'loading', title: t('searching') });
  }
  }

  async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) {
      resultsContainer.classList.remove('active');
      return;
    }

    if (currentRequest) currentRequest.abort();
    const controller = new AbortController();
    currentRequest = controller;

    // 先清空，再渲染统一的加载面板，避免被后续清空覆盖
    if (resultsContent) resultsContent.innerHTML = '';
    showLoading(true);
    resultsContainer.classList.add('active');

    // 前端轻量识别查询类型：仅对自由文本附加 fuzzy
    function detectQueryKey(val) {
      const s = String(val || '').trim();
      // weibo uid url
      if (/https?:\/\/weibo\.com\/u\/\d{5,20}/.test(s)) return 'weibo_uid';
      // id card
      if (/^\d{17}[\dXx]$/.test(s)) return 'id_card';
      // digits normalize
      const digits = s.replace(/\D/g, '');
      let digitsNorm = digits;
      if (digitsNorm.length >= 12 && digitsNorm.startsWith('86')) {
        digitsNorm = digitsNorm.slice(-11);
      }
      // phone
      if (/^1\d{10}$/.test(digitsNorm || '')) return 'phone';
      // email
      if (/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(s)) return 'email';
      // qq
      if (/^\d{5,12}$/.test(digits || '')) return 'qq';
      return 'general';
    }

    try {
      const qk = detectQueryKey(query);
      const normalizeForKey = (val, key) => {
        const s = String(val || '').trim();
        const digits = s.replace(/\D/g, '');
        // 归一化手机号：去国码与非数字，仅保留最终11位
        if (key === 'phone') {
          let dn = digits;
          if (dn.length >= 12 && dn.startsWith('86')) dn = dn.slice(-11);
          if (dn.length > 11) dn = dn.slice(-11);
          return dn;
        }
        // QQ：保留纯数字
        if (key === 'qq') return digits;
        // 身份证：去空白并大写末位X
        if (key === 'id_card') return s.toUpperCase();
        // 微博UID：若是URL则提取数字，否则原样
        if (key === 'weibo_uid') {
          const m = s.match(/weibo\.com\/u\/(\d{5,20})/);
          return m ? m[1] : digits || s;
        }
        // 邮箱与通用：原样
        return s;
      };

      const params = new URLSearchParams();
      params.set('query', normalizeForKey(query, qk));
      params.set('max_results', '50');
      // 自由文本查询不再附加 match 参数，后端仅支持精确匹配或显式 general 模式
      const response = await fetch(`/api/search?${params.toString()}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });

      if (!response.ok) {
        let errorData = {};
        try { errorData = await response.json(); } catch (_) {}
        const status = response.status;
        const errMsg = errorData.error || errorData.message || `HTTP ${status}`;
        const e = new Error(errMsg);
        e.status = status;
        throw e;
      }

      const result = await response.json();
      showLoading(false);

      if (result.success && Array.isArray(result.results)) {
        onResults(result.results);
      } else {
        displayNoResults(resultsContent);
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      showLoading(false);
      // 针对503服务不可用的专属提示
      if (error && error.status === 503) {
        renderStatusPanel(resultsContent, {
          type: 'error',
          title: t('service_unavailable_title'),
          desc: t('service_unavailable_desc'),
          icon: '🚧',
          retry: true,
          retryId: 'retrySearchBtn'
        });
        bindRetry(resultsContent, () => {
          const input = document.getElementById('searchInput');
          if (input && input.value.trim()) {
            const searchButton = document.getElementById('searchButton');
            if (searchButton) searchButton.click();
          }
        }, 'retrySearchBtn');
      } else {
        // 网络错误可单独提示
        if (error && error.name === 'TypeError') {
          renderStatusPanel(resultsContent, { type: 'network_error', retry: true, retryId: 'retrySearchBtn' });
        } else {
          displayError(resultsContent, error.message);
        }
      }
    } finally {
      currentRequest = null;
    }
  }
}

export function displayResults(results) {
  const resultsContent = document.getElementById('resultsContent');
  if (!resultsContent) return;
  resultsContent.innerHTML = '';

  if (!Array.isArray(results) || results.length === 0) {
    displayNoResults(resultsContent);
    return;
  }

  // 统一以桌面列表渲染（去除不存在的移动模块依赖）

  results.forEach((result, index) => {
    // 统一ID字段
    if (result._id && !result.id) result.id = result._id;

    const resultItem = document.createElement('div');
    resultItem.className = 'result-item';
    resultItem.style.animationDelay = `${index * 0.1}s`;
    resultItem.dataset.index = index;

    // 右侧信息栏字段顺序（按需求）：性别、籍贯、出生日期、身份证号、手机、邮箱、QQ号、微博UID、公司、职位、配偶姓名、直系亲属姓名
    const fieldOrder = ['gender', 'native_place', 'birth_date', 'id_card', 'phones', 'phone', 'emails', 'email', 'qqs', 'qq', 'weibo_uids', 'weibo_uid', 'company', 'position', 'spouse_name', 'relative_name', 'relationship'];
    const allowedKeys = new Set(['gender', 'native_place', 'birth_date', 'id_card', 'phones', 'phone', 'emails', 'email', 'qqs', 'qq', 'weibo_uids', 'weibo_uid', 'company', 'position', 'spouse_name', 'relative_name', 'relationship']);

    // 是否存在复数字段：需判断长度，避免空数组误判导致单数字段被忽略
    const hasPhones = Array.isArray(result.phones) ? result.phones.length > 0 : !!result.phones;
    const hasQqs = Array.isArray(result.qqs) ? result.qqs.length > 0 : !!result.qqs;
    const hasEmails = Array.isArray(result.emails) ? result.emails.length > 0 : !!result.emails;
    let sortedEntries = Object.entries(result)
      .filter(([key]) => {
        const lower = String(key).toLowerCase();
        if (!allowedKeys.has(lower)) return false;
        if (lower === 'phone' && hasPhones) return false;
        if (lower === 'qq' && hasQqs) return false;
        if (lower === 'email' && hasEmails) return false;
        return true;
      })
      .sort(([keyA], [keyB]) => {
        const ia = fieldOrder.indexOf(keyA);
        const ib = fieldOrder.indexOf(keyB);
        return (ia === -1 ? 999 : ia) - (ib === -1 ? 999 : ib);
      });

    // 拼接关系：relative_name + （relationship）；若有则隐藏独立的 relationship 字段
    const relIdx = sortedEntries.findIndex(([k]) => k === 'relationship');
    const rnIdx = sortedEntries.findIndex(([k]) => k === 'relative_name');
    if (rnIdx >= 0) {
      const name = sortedEntries[rnIdx][1];
      const relVal = relIdx >= 0 ? sortedEntries[relIdx][1] : null;
    const display = name && relVal ? `${escapeHtml(String(name))}（${escapeHtml(String(relVal))}）` : escapeHtml(String(name || t('unknown')));
      sortedEntries[rnIdx][1] = display;
      if (relIdx >= 0) {
        sortedEntries.splice(relIdx, 1);
      }
    } else if (relIdx >= 0) {
      // 无亲属姓名时，不单独展示关系字段
      sortedEntries.splice(relIdx, 1);
    }

    const filteredEntries = sortedEntries.filter(([key, value]) => {
      if (value === null || value === undefined) return false;
      if (typeof value === 'string') {
        const s = value.trim();
      if (s === '' || s === t('unknown') || s.toLowerCase() === 'unknown' || s.toUpperCase() === 'N/A') return false;
      }
      if (Array.isArray(value)) return value.length > 0;
      if (typeof value === 'object') {
        const keys = Object.keys(value);
        if (keys.length === 0) return false;
        const any = keys.some(k => {
          const v = value[k];
          if (v === null || v === undefined) return false;
          if (typeof v === 'string') {
            const sv = v.trim();
    return sv !== '' && sv !== t('unknown') && sv.toLowerCase() !== 'unknown' && sv.toUpperCase() !== 'N/A';
          }
          if (Array.isArray(v)) return v.length > 0;
          return true;
        });
        if (!any) return false;
      }
      const formatted = formatValue(value, key);
      const f = typeof formatted === 'string' ? formatted.trim() : formatted;
    if (f === t('unknown') || f === '未识别' || (typeof f === 'string' && (f.toLowerCase() === 'unknown' || f.toUpperCase() === 'N/A'))) return false;
      return true;
    });

    // 删除重复的旧 infoItems 构建逻辑，统一在下方以两列栅格渲染

    // 上部信息：置信度与来源、时间信息重构为并排行
    let credibilityChip = '';
    if (result.credibility) {
      const levelClass = result.credibility.credibility_level === '高' ? 'high' : result.credibility.credibility_level === '中' ? 'medium' : 'low';
      credibilityChip = `
        <div class="meta-chip">
      <span class="chip-label">${t('field_ai_confidence') || '置信度'}</span>
          <span class="credibility-display ${levelClass}">
            <span class="credibility-level">${escapeHtml(String(result.credibility.credibility_level))}</span>
            <span class="credibility-percentage">(${escapeHtml(String(result.credibility.percentage || ''))})</span>
          </span>
        </div>`;
    }

    // 数据来源行
    let sourcesHtml = `<div class="source-row"><div class="source-label">${t('field_data_sources')}</div><div class="source-list">`;
    // 优先使用后端注入的 formatted_data_sources
    const fds = Array.isArray(result.formatted_data_sources) ? result.formatted_data_sources : null;
    if (fds && fds.length > 0) {
      // 本地日期格式化为 YYYY.MM.DD
      const formatDateDots = (s) => {
        if (!s) return '';
        const d = new Date(s);
        if (Number.isNaN(d.getTime())) return String(s);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${y}.${m}.${dd}`;
      };
      fds.forEach((src, sourceIndex) => {
        const table = src.table || src.source || '';
        const chinese = src.chinese || table;
        const dateStr = src.date ? formatDateDots(src.date) : '';
        const count = Number.isFinite(src.count) ? src.count : null;
        const prefix = count && count > 0 ? `${count}条` : '';
        const displayText = `${prefix ? prefix : ''}${chinese}${dateStr ? `（${dateStr}）` : ''}`;
        sourcesHtml += `
          <div class="data-source-item" data-result-index="${index}" data-source-index="${sourceIndex}" data-table="${escapeHtml(table)}" data-chinese="${escapeHtml(chinese)}" data-date="${escapeHtml(dateStr)}" data-count="${escapeHtml(prefix)}">
            <span class="source-text">${escapeHtml(displayText)}</span>
          </div>`;
      });
    } else {
      // 回退到旧 data_sources 字段
      let dataSources = result.data_sources;
      if (typeof dataSources === 'string') {
        dataSources = dataSources.split(',').map((s) => s.trim()).filter((s) => s);
      }
      if (Array.isArray(dataSources) && dataSources.length > 0) {
        const formatDateDots = (s) => {
          if (!s) return '';
          const d = new Date(s);
          if (Number.isNaN(d.getTime())) return String(s);
          const y = d.getFullYear();
          const m = String(d.getMonth() + 1).padStart(2, '0');
          const dd = String(d.getDate()).padStart(2, '0');
          return `${y}.${m}.${dd}`;
        };
        dataSources.forEach((source, sourceIndex) => {
          const sourceName = typeof source === 'object' ? (source.source || source.table || source.name || '') : source;
          const capturedAt = typeof source === 'object' && source.captured_at ? formatDateDots(source.captured_at) : '';
          const displayText = capturedAt ? `${sourceName}（${capturedAt}）` : sourceName;
          sourcesHtml += `
            <div class="data-source-item" data-result-index="${index}" data-source-index="${sourceIndex}" data-table="${escapeHtml(sourceName)}" data-chinese="${escapeHtml(sourceName)}" data-date="${escapeHtml(capturedAt)}">
              <span class="source-text">${escapeHtml(displayText)}</span>
            </div>`;
        });
      } else {
    sourcesHtml += `<div class="data-source-item no-interaction">${t('unknown')}</div>`;
      }
    }
    sourcesHtml += '</div></div>';

    // 时间信息chips
    let timeRow = '';
    if (result.metadata) {
      const metadata = result.metadata;
      const chips = [];
      if (metadata.created_at) {
        const createdStr = new Date(metadata.created_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).replace(/\//g, '/');
        chips.push(`<div class="meta-chip"><span class="chip-label">${escapeHtml(t('field_created_at'))}</span><span class="chip-value">${escapeHtml(createdStr)}</span></div>`);
      }
      if (metadata.updated_at) {
        const updatedStr = new Date(metadata.updated_at).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).replace(/\//g, '/');
        chips.push(`<div class="meta-chip"><span class="chip-label">${escapeHtml(t('field_updated_at'))}</span><span class="chip-value">${escapeHtml(updatedStr)}</span></div>`);
      }
      if (chips.length > 0) {
        timeRow = `<div class="meta-row">${chips.join('')}${credibilityChip}</div>`;
      } else if (credibilityChip) {
        timeRow = `<div class="meta-row">${credibilityChip}</div>`;
      }
    } else if (credibilityChip) {
      timeRow = `<div class="meta-row">${credibilityChip}</div>`;
    }

    // 置信度圆环（显示在标题右侧）；无数据显示空圆环
    const aiConf = normalizeConfidence(result.ai_confidence);
    const percent = aiConf ? parsePercentage(aiConf.percentage) : 0;
    const levelText = aiConf ? String(aiConf.level || '').trim() : '';
    const levelClass = aiConf ? (levelText === '高' ? 'high' : levelText === '中' ? 'medium' : levelText === '低' ? 'low' : 'empty') : 'empty';
    const reportTitle = aiConf ? t('ai_assessment_report_title_fmt', { level: levelText || '-', percent: percent }) : `${t('field_ai_confidence') || '置信度'}（${t('unknown')}）`;
    const confidenceCircleDesktop = `
      <div class="confidence-circle desktop-only ${levelClass}" data-index="${index}" title="${escapeHtml(reportTitle)}">
        <div class="confidence-ring" style="--percent:${percent}"></div>
        <div class="confidence-center">${percent}%</div>
      </div>
    `;
    const confidenceBlockDesktop = `
      <div class="confidence-block">
        ${confidenceCircleDesktop}
    <div class="confidence-caption">${t('field_ai_confidence') || '置信度'}</div>
      </div>
    `;
    const confidenceCircleMobile = `
      <div class="confidence-circle mobile-only ${levelClass}" data-index="${index}" title="${escapeHtml(reportTitle)}">
        <div class="confidence-ring" style="--percent:${percent}"></div>
        <div class="confidence-center">${percent}%</div>
      </div>
    `;
    const confidenceBlockMobile = `
      <div class="confidence-block">
        ${confidenceCircleMobile}
      </div>
    `;

    // 按两列栅格渲染，奇数时最后一项横跨两列
    let infoItemHtmls = filteredEntries.map(([key, value]) => {
      const val = typeof value === 'string' ? value : formatValue(value, key);
      if (String(key).toLowerCase() === 'spouse_name') {
        const backVal = result.spouse_phone ? String(result.spouse_phone).trim() : t('unknown');
        const frontVal = val || t('unknown');
        const frontLabel = t('field_spouse_name');
        const backLabel = t('field_spouse_phone');
        return `
          <div class="info-item toggle-item" data-type="spouse"
               data-front-label="${escapeHtml(frontLabel)}" data-back-label="${escapeHtml(backLabel)}"
               data-front-value="${escapeHtml(frontVal)}" data-back-value="${escapeHtml(backVal)}" data-state="front">
            <div class="info-label">${escapeHtml(frontLabel)}</div>
            <div class="info-value" title="${escapeHtml(frontVal)}">${escapeHtml(frontVal)}</div>
          </div>`;
      }
      if (String(key).toLowerCase() === 'relative_name') {
        const backVal = result.relative_phone ? String(result.relative_phone).trim() : t('unknown');
        const frontVal = val || t('unknown');
        const frontLabel = t('field_relative_name');
        const backLabel = t('field_relative_phone');
        return `
          <div class="info-item toggle-item" data-type="relative"
               data-front-label="${escapeHtml(frontLabel)}" data-back-label="${escapeHtml(backLabel)}"
               data-front-value="${escapeHtml(frontVal)}" data-back-value="${escapeHtml(backVal)}" data-state="front">
            <div class="info-label">${escapeHtml(frontLabel)}</div>
            <div class="info-value" title="${escapeHtml(frontVal)}">${escapeHtml(frontVal)}</div>
          </div>`;
      }
      const lowerKey = String(key).toLowerCase();
      // 手机/QQ/微博/邮箱/身份证点击查询：渲染为 chip（兼容对象数组）
      if (lowerKey === 'phone' || lowerKey === 'phones' || lowerKey === 'qq' || lowerKey === 'qqs' || lowerKey === 'weibo_uid' || lowerKey === 'weibo_uids' || lowerKey === 'email' || lowerKey === 'emails' || lowerKey === 'id_card') {
        let chips = '';
        if (Array.isArray(val)) {
          chips = val.map(item => {
            if (lowerKey === 'phone' || lowerKey === 'phones') {
              const num = typeof item === 'object' && item ? String(item.number ?? item).trim() : String(item).trim();
              const digits = num.replace(/\D/g, '');
              const display = digits || num;
        return `<span class="click-chip phone-chip" data-number="${escapeHtml(digits || display)}" title="${escapeHtml(t('title_query_carrier'))}">${escapeHtml(display)}</span>`;
            }
            if (lowerKey === 'qq' || lowerKey === 'qqs') {
              const numRaw = typeof item === 'object' && item ? String(item.qq ?? item.number ?? item).trim() : String(item).trim();
              const digits = numRaw.replace(/\D/g, '');
              const label = (typeof item === 'object' && item && item.name) ? `${item.name} (${digits || numRaw})` : (digits || numRaw);
        return `<span class="click-chip qq-chip" data-qq="${escapeHtml(digits || numRaw)}" title="${escapeHtml(t('title_query_qq'))}">${escapeHtml(label)}</span>`;
            }
            if (lowerKey === 'weibo_uid' || lowerKey === 'weibo_uids') {
              const uidRaw = typeof item === 'object' && item ? String(item.uid ?? item).trim() : String(item).trim();
              const digits = uidRaw.replace(/\D/g, '');
              const label = (typeof item === 'object' && item && item.name) ? `${item.name} (${digits || uidRaw})` : (digits || uidRaw);
        return `<span class="click-chip weibo-chip" data-uid="${escapeHtml(digits || uidRaw)}" title="${escapeHtml(t('title_query_weibo_uid'))}">${escapeHtml(label)}</span>`;
            }
            if (lowerKey === 'email' || lowerKey === 'emails') {
              const em = typeof item === 'object' && item ? String(item.email ?? item).trim() : String(item).trim();
        return `<span class="click-chip email-chip" data-email="${escapeHtml(em)}" title="${escapeHtml(t('title_recognize_email'))}">${escapeHtml(em)}</span>`;
            }
            // 身份证通常不为数组，做兼容
            const idv = typeof item === 'object' && item ? String(item.id_card ?? item).trim() : String(item).trim();
        return `<span class="click-chip id-chip" data-id="${escapeHtml(idv)}" title="${escapeHtml(t('title_validate_id_card'))}">${escapeHtml(idv)}</span>`;
          }).join(' ');
        } else if (val && typeof val === 'object') {
          // 单个对象值（例如 qqs 仅有一项且作为对象返回）
          if (lowerKey === 'phone' || lowerKey === 'phones') {
            const num = String(val.number ?? '').trim();
            const digits = num.replace(/\D/g, '');
            const display = digits || num || t('unknown');
      chips = `<span class="click-chip phone-chip" data-number="${escapeHtml(digits || display)}" title="${escapeHtml(t('title_query_carrier'))}">${escapeHtml(display)}</span>`;
          } else if (lowerKey === 'qq' || lowerKey === 'qqs') {
            const numRaw = String(val.qq ?? val.number ?? '').trim();
            const digits = numRaw.replace(/\D/g, '');
            const label = val.name ? `${val.name} (${digits || numRaw})` : (digits || numRaw || t('unknown'));
      chips = `<span class="click-chip qq-chip" data-qq="${escapeHtml(digits || numRaw)}" title="${escapeHtml(t('title_query_qq'))}">${escapeHtml(label)}</span>`;
          } else if (lowerKey === 'weibo_uid' || lowerKey === 'weibo_uids') {
            const uidRaw = String(val.uid ?? '').trim();
            const digits = uidRaw.replace(/\D/g, '');
            const label = val.name ? `${val.name} (${digits || uidRaw})` : (digits || uidRaw || t('unknown'));
      chips = `<span class="click-chip weibo-chip" data-uid="${escapeHtml(digits || uidRaw)}" title="${escapeHtml(t('title_query_weibo_uid'))}">${escapeHtml(label)}</span>`;
          } else if (lowerKey === 'email' || lowerKey === 'emails') {
            const em = String(val.email ?? '').trim();
      chips = `<span class="click-chip email-chip" data-email="${escapeHtml(em)}" title="${escapeHtml(t('title_recognize_email'))}">${escapeHtml(em || t('unknown'))}</span>`;
          } else {
            const idv = String(val.id_card ?? '').trim();
      chips = `<span class="click-chip id-chip" data-id="${escapeHtml(idv)}" title="${escapeHtml(t('title_validate_id_card'))}">${escapeHtml(idv || t('unknown'))}</span>`;
          }
        } else {
          const tokens = String(val)
            .split(/[,，\s]+/)
            .map(s => s.trim())
            .filter(s => s);
          chips = tokens.map(tok => {
              if (lowerKey === 'phone' || lowerKey === 'phones') {
        return `<span class="click-chip phone-chip" data-number="${escapeHtml(tok)}" title="${escapeHtml(t('title_query_carrier'))}">${escapeHtml(tok)}</span>`;
              } else {
                if (lowerKey === 'qq' || lowerKey === 'qqs') {
                  return `<span class="click-chip qq-chip" data-qq="${escapeHtml(tok)}" title="${escapeHtml(t('title_query_qq'))}">${escapeHtml(tok)}</span>`;
                } else if (lowerKey === 'weibo_uid' || lowerKey === 'weibo_uids') {
                  return `<span class="click-chip weibo-chip" data-uid="${escapeHtml(tok)}" title="${escapeHtml(t('title_query_weibo_uid'))}">${escapeHtml(tok)}</span>`;
                } else if (lowerKey === 'email' || lowerKey === 'emails') {
                  return `<span class="click-chip email-chip" data-email="${escapeHtml(tok)}" title="${escapeHtml(t('title_recognize_email'))}">${escapeHtml(tok)}</span>`;
                }
                // 身份证
                return `<span class="click-chip id-chip" data-id="${escapeHtml(tok)}" title="${escapeHtml(t('title_validate_id_card'))}">${escapeHtml(tok)}</span>`;
              }
          }).join(' ');
        }
        return `
          <div class="info-item" data-key="${escapeHtml(lowerKey)}">
            <div class="info-label">${translateKey(key)}</div>
            <div class="info-value">${chips || escapeHtml(val)}</div>
          </div>`;
      }
      return `
        <div class="info-item" data-key="${escapeHtml(lowerKey)}">
          <div class="info-label">${translateKey(key)}</div>
          <div class="info-value" title="${escapeHtml(val)}">${val}</div>
        </div>`;
    });

    // 取消项级折叠标记，改为网格级两行折叠

    // 置信度信息已在标题右侧圆环显示，不再在信息网格中重复
    if (infoItemHtmls.length % 2 === 1) {
      const last = infoItemHtmls.length - 1;
      const lastHtml = infoItemHtmls[last];
      if (lastHtml.includes('collapsible')) {
        infoItemHtmls[last] = lastHtml.replace('<div class="info-item collapsible"', '<div class="info-item collapsible span-two"');
      } else {
        infoItemHtmls[last] = lastHtml.replace('<div class="info-item"', '<div class="info-item span-two"');
      }
    }
    const infoItemsCombined = infoItemHtmls.join('');

    resultItem.innerHTML = `
      <div class="result-header result-top">
        <div class="result-top-left">
          <div class="name-id">
            <div class="result-title">${escapeHtml(result.name || '查询结果')}</div>
            <div class="result-id" data-id="${escapeHtml(result.id || '')}" title="记录ID">ID：${escapeHtml(result.id || '未知')}</div>
          </div>
          <div class="result-actions">
            <button class="edit-btn" onclick="editResult(${index})" title="修改信息">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                <path d="m18.5 2.5 a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
<button class="copy-btn" onclick="copyResult(${index})" title="${escapeHtml(t('copy'))}">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="m5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
            </button>
            <button class="ai-btn" onclick="analyzeWithAI(${index})" title="置信度测评">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
              </svg>
            </button>
            ${confidenceBlockMobile}
          </div>
          ${sourcesHtml}
          ${timeRow}
        </div>
        <div class="result-top-right">
          ${confidenceBlockDesktop}
        </div>
      </div>
      <div class="info-grid">${infoItemsCombined}
      </div>
    `;

    resultsContent.appendChild(resultItem);

    // 渲染后按行测量并折叠为两行，并调整圆环尺寸
    requestAnimationFrame(() => {
      setupGridCollapse(resultItem);
      adjustConfidenceCircleSize(resultItem);
    });
    // 绑定圆环点击显示评估报告
    // 桌面圆环点击显示评估报告
    const circle = resultItem.querySelector('.confidence-circle.desktop-only');
    if (circle) {
      circle.addEventListener('click', () => {
        const ri = parseInt(resultItem.dataset.index, 10);
        const res = (window.searchResults || [])[ri];
        const conf = normalizeConfidence(res && res.ai_confidence);
        if (!conf || !conf.report) {
          openSourceModal(t('ai_assessment_title'), `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('ai_no_data'))}</h3><p>${escapeHtml(t('ai_click_to_assess'))}</p></div>`);
          return;
        }
        const p = parsePercentage(conf.percentage);
        const levelText = String(conf.level || '').trim();
        const provider = conf.provider || '';
        const model = conf.model || '';
        const html = `
          <div class="analysis-content">
            <h3>置信度等级：${escapeHtml(levelText)}（${p}%）</h3>
            <div><strong>模型/提供方：</strong>${escapeHtml(provider)} ${model ? '(' + escapeHtml(model) + ')' : ''}</div>
            <h3>评估报告</h3>
            <div>${escapeHtml(conf.report)}</div>
          </div>
        `;
        openSourceModal(t('ai_assessment_report_title'), html);
      });
    }
  });

  window.searchResults = results;

  // 绑定点击事件（数据来源与翻转效果）—只绑定一次
  if (!resultsContent.dataset.sourceBound) {
    resultsContent.addEventListener('click', async (e) => {
      const item = e.target.closest('.data-source-item');
      if (!item) return;
      const ri = parseInt(item.dataset.resultIndex);
      const sourceTable = item.dataset.table;
      const res = (window.searchResults || [])[ri];
      if (!res || !sourceTable) return;

      // 打开加载中的模态框
      openSourceModal(`${t('source_detail_title')}：${item.dataset.chinese || sourceTable}`, `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('loading'))}</p></div>`);

      try {
        const params = new URLSearchParams();
        params.set('table', sourceTable);
        if (res.id_card) params.set('id_card', res.id_card);
        const phones = Array.isArray(res.phones) ? res.phones.join(',') : (res.phone || '');
        if (phones) params.set('phones', phones);
        const qqs = Array.isArray(res.qqs)
          ? res.qqs
              .map(v => {
                if (typeof v === 'string') return v;
                if (v && typeof v === 'object') return String(v.qq ?? v.number ?? '').trim();
                return '';
              })
              .map(s => String(s).trim())
              .filter(s => s)
              .join(',')
          : (res.qq || '');
        if (qqs) params.set('qqs', qqs);
        if (res.weibo_uid) {
          params.set('weibo_uid', res.weibo_uid);
        } else if (Array.isArray(res.weibo_uids) && res.weibo_uids.length > 0) {
          const first = res.weibo_uids[0];
          const uid = typeof first === 'object' && first ? String(first.uid ?? '').trim() : String(first || '').trim();
          if (uid) params.set('weibo_uid', uid.replace(/\D/g, ''));
        }
        if (res.email) params.set('email', res.email);
        if (res.name) params.set('name', res.name);

        const resp = await fetch(`/api/source_detail?${params.toString()}`);
        const data = await resp.json();
        if (!resp.ok || !data.success) {
          throw new Error(data.message || data.error || '查询失败');
        }

        const records = Array.isArray(data.records) ? data.records : [];
        const title = `${t('source_detail_title')}：${data.chinese || sourceTable}`;
        if (records.length === 0) {
          openSourceModal(title, `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('source_no_records_title'))}</h3><p>${escapeHtml(t('source_no_records_desc'))}</p></div>`);
          return;
        }

        // 简单表格渲染前50行
        const cols = Object.keys(records[0] || {});
        const header = `<tr>${cols.map(c => `<th>${escapeHtml(String(c))}</th>`).join('')}</tr>`;
        const rows = records.map(r => `<tr>${cols.map(c => `<td>${escapeHtml(String(r[c] ?? ''))}</td>`).join('')}</tr>`).join('');
        const html = `
          <div class="table-wrapper" style="overflow:auto; max-height:60vh;">
            <table class="source-table" style="width:100%; border-collapse:collapse;">
              <thead>${header}</thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        `;
        openSourceModal(title, html);
      } catch (err) {
        openSourceModal(t('source_detail_title'), `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>${escapeHtml(t('error_title'))}</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
      }
    });
    resultsContent.dataset.sourceBound = '1';
  }

  if (!resultsContent.dataset.toggleBound) {
    resultsContent.addEventListener('click', (e) => {
      const toggleItem = e.target.closest('.toggle-item');
      if (!toggleItem) return;
      const state = toggleItem.dataset.state || 'front';
      const next = state === 'front' ? 'back' : 'front';
      toggleItem.dataset.state = next;
      const labelEl = toggleItem.querySelector('.info-label');
      const valueEl = toggleItem.querySelector('.info-value');
      if (!labelEl || !valueEl) return;
      const label = toggleItem.dataset[`${next}Label`] || '';
      const val = toggleItem.dataset[`${next}Value`] || '';
      labelEl.textContent = label;
      valueEl.textContent = val;
      valueEl.setAttribute('title', val);
    });
    resultsContent.dataset.toggleBound = '1';
  }

  // 手机/QQ/身份证点击查询（只绑定一次）
  if (!resultsContent.dataset.validationBound) {
    resultsContent.addEventListener('click', async (e) => {
      const phoneChip = e.target.closest('.phone-chip');
      const qqChip = e.target.closest('.qq-chip');
      const weiboChip = e.target.closest('.weibo-chip');
      const emailChip = e.target.closest('.email-chip');
      const idChip = e.target.closest('.id-chip');
      const idHeader = e.target.closest('.result-id');
      // 标题中的 ID 不再触发身份证校验；仅 chip 点击触发
      if (!phoneChip && !qqChip && !weiboChip && !emailChip && !idChip) return;

      if (phoneChip) {
        const number = (phoneChip.dataset.number || '').trim();
        if (!number) return;
        openSourceModal(t('phone_carrier_query_title'), `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('querying'))}</p></div>`);
        try {
          const params = new URLSearchParams();
          params.set('number', number);
          // 传递写入标志与上下文身份证号
          params.set('write', '1');
          const item = phoneChip.closest('.result-item');
          const idx = item && item.dataset.index ? Number(item.dataset.index) : NaN;
          const resList = window.searchResults || [];
          const ctx = !isNaN(idx) ? (resList[idx] || {}) : {};
          const idCard = (ctx.id_card || '').trim();
          if (idCard) params.set('id_card', idCard);
          const resp = await fetch(`/api/validate/phone?${params.toString()}`);
          const data = await resp.json();
          if (!resp.ok || !data.success) throw new Error(data.message || data.error || '查询失败');
          const p = data.province || '';
          const c = data.city || '';
          const carrier = data.carrier || '';
          const area = data.area_code || '';
          const post = data.postcode || '';
          const excerpt = data.raw_excerpt || '';
          const updated = data.updated || null;
          let writeSummary = '';
          if (updated === null) {
            writeSummary = '<div><strong>写入状态：</strong>写入失败（记录不存在或服务错误）</div>';
          } else if (updated && updated.phones === true) {
            writeSummary = '<div><strong>写入状态：</strong>写入成功（更新1项）</div>';
          } else if (updated && updated.phones === false) {
            writeSummary = '<div><strong>写入状态：</strong>写入完成（无变化）</div>';
          }
          const rows = [
            `<div><strong>手机号：</strong>${escapeHtml(data.number || number)}</div>`,
            p || c ? `<div><strong>归属地：</strong>${escapeHtml([p, c].filter(Boolean).join(' '))}</div>` : '',
            carrier ? `<div><strong>运营商：</strong>${escapeHtml(carrier)}</div>` : '',
            area ? `<div><strong>区号：</strong>${escapeHtml(area)}</div>` : '',
            post ? `<div><strong>邮编：</strong>${escapeHtml(post)}</div>` : '',
            writeSummary,
            (!p && !c && excerpt) ? `<div><strong>原文片段：</strong>${escapeHtml(excerpt)}</div>` : ''
          ].filter(Boolean).join('');
          openSourceModal(t('phone_carrier_query_title'), rows || `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('phone_carrier_no_data_title'))}</h3></div>`);
        } catch (err) {
          openSourceModal(t('phone_carrier_query_title'), `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>${escapeHtml(t('query_failed_title'))}</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
        }
        return;
      }

      if (qqChip) {
        const qq = (qqChip.dataset.qq || '').trim();
        if (!qq) return;
        openSourceModal(t('qq_info_query_title'), `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('querying'))}</p></div>`);
        try {
          const params = new URLSearchParams();
          params.set('qq', qq);
          params.set('write', '1');
          const item = qqChip.closest('.result-item');
          const idx = item && item.dataset.index ? Number(item.dataset.index) : NaN;
          const resList = window.searchResults || [];
          const ctx = !isNaN(idx) ? (resList[idx] || {}) : {};
          const idCard = (ctx.id_card || '').trim();
          if (idCard) params.set('id_card', idCard);
          // 传递用于合并的上下文：已有主表id或同卡片中的手机号
          const primaryId = (ctx.id || '').trim();
          if (primaryId) params.set('id', primaryId);
          const phonesArr = Array.isArray(ctx.phones) ? ctx.phones : [];
          let mergePhone = '';
          if (phonesArr.length > 0) {
            const p0 = phonesArr[0];
            let raw = '';
            if (typeof p0 === 'string') raw = p0;
            else if (p0 && typeof p0 === 'object') raw = String(p0.number || '');
            raw = raw.trim();
            if (raw) {
              let digits = raw.replace(/\D/g, '');
              if (digits.length >= 12 && digits.startsWith('86')) digits = digits.slice(-11);
              if (/^1\d{10}$/.test(digits)) mergePhone = digits;
            }
          }
          if (mergePhone) params.set('merge_phone', mergePhone);
          const resp = await fetch(`/api/validate/qq?${params.toString()}`);
          const data = await resp.json();
          if (!resp.ok || !data.success) throw new Error(data.message || data.error || '查询失败');
          const info = data.data || {};
          const updated = data.updated || null;
          let writeSummary = '';
          if (updated === null) {
            writeSummary = '<div><strong>写入状态：</strong>写入失败（记录不存在或服务错误）</div>';
          } else if (updated && updated.qqs === true) {
            writeSummary = '<div><strong>写入状态：</strong>写入成功（新增1项或更新）</div>';
          } else if (updated && updated.qqs === false) {
            writeSummary = '<div><strong>写入状态：</strong>写入完成（无变化）</div>';
          }
          const rows = [
            `<div><strong>QQ：</strong>${escapeHtml(String(info.qq ?? qq))}</div>`,
            info.name ? `<div><strong>昵称：</strong>${escapeHtml(info.name)}</div>` : '',
            info.email ? `<div><strong>邮箱：</strong>${escapeHtml(info.email)}</div>` : '',
            writeSummary,
            info.logo ? `<div><strong>头像：</strong><img src="${escapeHtml(info.logo)}" alt="avatar" style="width:48px;height:48px;border-radius:50%"></div>` : ''
          ].filter(Boolean).join('');
          openSourceModal(t('qq_info_query_title'), rows || `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('qq_info_empty_title'))}</h3></div>`);
        } catch (err) {
          openSourceModal(t('qq_info_query_title'), `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>${escapeHtml(t('query_failed_title'))}</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
        }
        return;
      }

      if (weiboChip) {
        const uid = (weiboChip.dataset.uid || '').trim();
        if (!uid) return;
        openSourceModal(t('weibo_uid_query_title'), `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('querying'))}</p></div>`);
        try {
          const params = new URLSearchParams();
          params.set('uid', uid);
          params.set('write', '1');
          const item = weiboChip.closest('.result-item');
          const idx = item && item.dataset.index ? Number(item.dataset.index) : NaN;
          const resList = window.searchResults || [];
          const ctx = !isNaN(idx) ? (resList[idx] || {}) : {};
          const idCard = (ctx.id_card || '').trim();
          if (idCard) params.set('id_card', idCard);
          const resp = await fetch(`/api/validate/weibo?${params.toString()}`);
          const data = await resp.json();
          if (!resp.ok || !data.success) throw new Error(data.message || data.error || '查询失败');
          const updated = data.updated || null;
          let writeSummary = '';
          if (updated === null) {
            writeSummary = '<div><strong>写入状态：</strong>写入失败（记录不存在或服务错误）</div>';
          } else if (updated && updated.weibo_uids === true) {
            writeSummary = '<div><strong>写入状态：</strong>写入成功（新增或更新）</div>';
          } else if (updated && updated.weibo_uids === false) {
            writeSummary = '<div><strong>写入状态：</strong>写入完成（无变化）</div>';
          }
          const rows = [
            `<div><strong>UID：</strong>${escapeHtml(String(data.uid || uid))}</div>`,
            data.name ? `<div><strong>用户名：</strong>${escapeHtml(data.name)}</div>` : '',
            data.gender ? `<div><strong>性别：</strong>${escapeHtml(data.gender)}</div>` : '',
            (data.fans || data.fans === 0) ? `<div><strong>粉丝：</strong>${escapeHtml(String(data.fans))}</div>` : '',
            (data.follows || data.follows === 0) ? `<div><strong>关注：</strong>${escapeHtml(String(data.follows))}</div>` : '',
            (data.rpz || data.rpz === 0) ? `<div><strong>转评赞：</strong>${escapeHtml(String(data.rpz))}</div>` : '',
            (data.posts || data.posts === 0) ? `<div><strong>全部微博：</strong>${escapeHtml(String(data.posts))}</div>` : '',
            writeSummary,
            data.avatar ? `<div><strong>头像：</strong><img src="${escapeHtml(data.avatar)}" alt="avatar" style="width:48px;height:48px;border-radius:50%"></div>` : ''
          ].filter(Boolean).join('');
          openSourceModal(t('weibo_uid_query_title'), rows || `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('weibo_info_empty_title'))}</h3></div>`);
        } catch (err) {
          openSourceModal(t('weibo_uid_query_title'), `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>${escapeHtml(t('query_failed_title'))}</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
        }
        return;
      }

      if (emailChip) {
        const email = (emailChip.dataset.email || '').trim();
        if (!email) return;
        const atIdx = email.indexOf('@');
        const local = atIdx > 0 ? email.substring(0, atIdx) : email;
        const domain = atIdx > 0 ? email.substring(atIdx + 1).toLowerCase() : '';
        const digits = String(local).replace(/\D/g, '');
        const isPhone = (domain.includes('163.com') || /^1\d{10}$/.test(digits));
        const isQQ = (domain.includes('qq.com') || /^\d{5,12}$/.test(digits));
        const item = emailChip.closest('.result-item');
        const idx = item && item.dataset.index ? Number(item.dataset.index) : NaN;
        const resList = window.searchResults || [];
        const ctx = !isNaN(idx) ? (resList[idx] || {}) : {};
        const idCard = (ctx.id_card || '').trim();
        if (isPhone) {
          const number = digits.length >= 11 ? digits.slice(-11) : digits;
          openSourceModal(t('email_recognition_phone_title'), `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('querying'))}</p></div>`);
          try {
            const params = new URLSearchParams();
            params.set('number', number);
            params.set('write', '1');
            if (idCard) params.set('id_card', idCard);
            const resp = await fetch(`/api/validate/phone?${params.toString()}`);
            const data = await resp.json();
            if (!resp.ok || !data.success) throw new Error(data.message || data.error || '查询失败');
            const p = data.province || '';
            const c = data.city || '';
            const carrier = data.carrier || '';
            const area = data.area_code || '';
            const post = data.postcode || '';
            const updated = data.updated || null;
            let writeSummary = '';
            if (updated === null) {
              writeSummary = '<div><strong>写入状态：</strong>写入失败（记录不存在或服务错误）</div>';
            } else if (updated && updated.phones === true) {
              writeSummary = '<div><strong>写入状态：</strong>写入成功（新增或更新）</div>';
            } else if (updated && updated.phones === false) {
              writeSummary = '<div><strong>写入状态：</strong>写入完成（无变化）</div>';
            }
            const rows = [
              `<div><strong>识别手机号：</strong>${escapeHtml(data.number || number)}</div>`,
              p || c ? `<div><strong>归属地：</strong>${escapeHtml([p, c].filter(Boolean).join(' '))}</div>` : '',
              carrier ? `<div><strong>运营商：</strong>${escapeHtml(carrier)}</div>` : '',
              area ? `<div><strong>区号：</strong>${escapeHtml(area)}</div>` : '',
              post ? `<div><strong>邮编：</strong>${escapeHtml(post)}</div>` : '',
              writeSummary
            ].filter(Boolean).join('');
            openSourceModal('邮箱识别：手机号归属地', rows);
          } catch (err) {
          openSourceModal(t('email_recognition_phone_title'), `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>${escapeHtml(t('query_failed_title'))}</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
          }
          return;
        }
        if (isQQ) {
          const qq = digits;
          openSourceModal(t('email_recognition_qq_title'), `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('querying'))}</p></div>`);
          try {
            const params = new URLSearchParams();
            params.set('qq', qq);
            params.set('write', '1');
            if (idCard) params.set('id_card', idCard);
            const resp = await fetch(`/api/validate/qq?${params.toString()}`);
            const data = await resp.json();
            if (!resp.ok || !data.success) throw new Error(data.message || data.error || '查询失败');
            const info = data.data || {};
            const updated = data.updated || null;
            let writeSummary = '';
            if (updated === null) {
              writeSummary = '<div><strong>写入状态：</strong>写入失败（记录不存在或服务错误）</div>';
            } else if (updated && updated.qqs === true) {
              writeSummary = '<div><strong>写入状态：</strong>写入成功（新增1项或更新）</div>';
            } else if (updated && updated.qqs === false) {
              writeSummary = '<div><strong>写入状态：</strong>写入完成（无变化）</div>';
            }
            const rows = [
              `<div><strong>识别QQ号：</strong>${escapeHtml(qq)}</div>`,
              info.name ? `<div><strong>昵称：</strong>${escapeHtml(info.name)}</div>` : '',
              info.email ? `<div><strong>邮箱：</strong>${escapeHtml(info.email)}</div>` : '',
              writeSummary,
              info.logo ? `<div><strong>头像：</strong><img src="${escapeHtml(info.logo)}" alt="avatar" style="width:48px;height:48px;border-radius:50%"></div>` : ''
            ].filter(Boolean).join('');
            openSourceModal(t('email_recognition_qq_title'), rows);
          } catch (err) {
            openSourceModal(t('email_recognition_qq_title'), `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>${escapeHtml(t('query_failed_title'))}</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
          }
          return;
        }
        openSourceModal(t('email_recognition_title'), `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('email_recognition_no_hit'))}</h3></div>`);
        return;
      }

      if (idChip) {
        const code = ((idChip && idChip.dataset.id) || '').trim();
        if (!code) return;
        openSourceModal(t('id_card_validation_title'), `<div class="status-panel loading"><div class="loading-spinner"></div><p>${escapeHtml(t('validating'))}</p></div>`);
        try {
          const params = new URLSearchParams();
          params.set('id_card', code);
          params.set('write', '1');
          const resp = await fetch(`/api/validate/id_card?${params.toString()}`);
          const data = await resp.json();
          if (!resp.ok || !data.success) throw new Error(data.message || data.error || '校验失败');
          const addr = data.address_code || '';
          const nativePlace = data.native_place || '';
          const birth = (data.birth_date || data.birth || '').replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3');
          const gender = data.gender || '';
          const valid = data.valid === true;
          const errMsg = data.error || '';
          const consistency = data.consistency || {};
          const consGender = consistency.gender;
          const consNative = consistency.native_place;
          const consBirth = consistency.birth_date;
          const updated = data.updated || null;
          const updGender = updated && updated.gender;
          const updNative = updated && updated.native_place;
          const updBirth = updated && updated.birth_date;

          // 统一写入状态总结
          let writeSummary = '';
          if (valid) {
            if (updated === null) {
              writeSummary = '<div><strong>写入状态：</strong>写入失败（记录不存在或服务错误）</div>';
            } else {
              const changedCount = [updGender, updNative, updBirth].filter(v => v === true).length;
              const allKnown = [updGender, updNative, updBirth].every(v => v === false || v === true);
              if (changedCount > 0) {
                writeSummary = `<div><strong>写入状态：</strong>写入成功（更新${changedCount}项）</div>`;
              } else if (allKnown) {
                writeSummary = '<div><strong>写入状态：</strong>写入完成（无变化）</div>';
              }
            }
          }
          const rows = [
            `<div><strong>身份证号：</strong>${escapeHtml(String(data.id_card || code))}</div>`,
            addr ? `<div><strong>地址码：</strong>${escapeHtml(addr)}</div>` : '',
            nativePlace ? `<div><strong>籍贯：</strong>${escapeHtml(nativePlace)}</div>` : '',
            birth ? `<div><strong>出生日期：</strong>${escapeHtml(birth)}</div>` : '',
            gender ? `<div><strong>性别：</strong>${escapeHtml(gender)}</div>` : '',
            `<div><strong>校验结果：</strong>${valid ? '有效' : '无效'}</div>`,
            writeSummary,
            (consGender === true || consGender === false) ? `<div><strong>性别一致性：</strong>${consGender ? '一致' : '不一致'}</div>` : '',
            (consNative === true || consNative === false) ? `<div><strong>籍贯一致性：</strong>${consNative ? '一致' : '不一致'}</div>` : '',
            (consBirth === true || consBirth === false) ? `<div><strong>出生日期一致性：</strong>${consBirth ? '一致' : '不一致'}</div>` : '',
            (updated !== null && (updGender === true || updGender === false)) ? `<div><strong>写入性别：</strong>${updGender ? '已更新' : '无变化'}</div>` : '',
            (updated !== null && (updNative === true || updNative === false)) ? `<div><strong>写入籍贯：</strong>${updNative ? '已更新' : '无变化'}</div>` : '',
            (updated !== null && (updBirth === true || updBirth === false)) ? `<div><strong>写入出生日期：</strong>${updBirth ? '已更新' : '无变化'}</div>` : '',
            (!valid && errMsg) ? `<div><strong>原因：</strong>${escapeHtml(errMsg)}</div>` : ''
          ].filter(Boolean).join('');
        openSourceModal(t('id_card_validation_title'), rows || `<div class="status-panel empty"><div class="status-icon">📭</div><h3>${escapeHtml(t('validation_no_data_title'))}</h3></div>`);
        } catch (err) {
          openSourceModal('身份证校验', `<div class="status-panel error"><div class="status-icon">⚠️</div><h3>校验失败</h3><p>${escapeHtml(err.message || 'Unknown error')}</p></div>`);
        }
      }
    });
    resultsContent.dataset.validationBound = '1';
  }

  // 项级折叠已移除，折叠由卡片级按钮控制
}

// 渲染后设置圆环尺寸：
// 桌面：直径为上半部分高度的 3/4；
// 移动端：直径等于功能按钮高度（AI按钮为参考）。
function adjustConfidenceCircleSize(resultItem) {
  try {
    const topEl = resultItem.querySelector('.result-top');
    const desktopCircle = resultItem.querySelector('.confidence-circle.desktop-only .confidence-ring');
    const mobileCircle = resultItem.querySelector('.confidence-circle.mobile-only .confidence-ring');
    if (topEl && desktopCircle) {
      const topH = topEl.offsetHeight;
      const size = Math.max(40, Math.round(topH * 0.75));
      desktopCircle.style.setProperty('--size', `${size}px`);
      desktopCircle.style.setProperty('--thickness', `${Math.round(size * 0.12)}px`);
    }
    if (mobileCircle) {
      const actions = resultItem.querySelector('.result-actions');
      const refBtn = actions ? actions.querySelector('.ai-btn') || actions.querySelector('button') : null;
      const btnH = refBtn ? refBtn.offsetHeight : 40;
      const mSize = Math.max(32, btnH);
      mobileCircle.style.setProperty('--size', `${mSize}px`);
      mobileCircle.style.setProperty('--thickness', `${Math.round(mSize * 0.12)}px`);
      // 将移动圆环插入到功能按钮右侧
      if (actions && !actions.querySelector('.confidence-circle.mobile-only')) {
        actions.appendChild(actions.ownerDocument.createRange().createContextualFragment(`${confidenceBlockMobile}`));
      }
    }
  } catch (_) {}
}

export function displayNoResults(resultsContentEl = document.getElementById('resultsContent')) {
  if (!resultsContentEl) return;
  renderStatusPanel(resultsContentEl, { type: 'empty', title: t('no_results_title'), desc: t('no_results_desc'), icon: '🔍' });
  try {
    const panel = resultsContentEl.querySelector('.status-panel.empty') || resultsContentEl;
    const btn = document.createElement('button');
    btn.className = 'retry-btn';
    btn.id = 'suggestLeadsBtn';
    btn.textContent = t('suggest_leads');
    btn.setAttribute('aria-label', t('suggest_leads_open'));
    panel.appendChild(btn);
    btn.addEventListener('click', () => {
      const tips = `
        <div class="status-panel">
          <div class="status-icon">💡</div>
          <h3>${escapeHtml(t('suggest_leads'))}</h3>
          <div style="text-align:left;line-height:1.6">
            <p>${escapeHtml(t('suggest_leads_intro'))}</p>
            <ul style="padding-left:1.2rem">
              <li>${escapeHtml(t('suggest_leads_item_1'))}</li>
              <li>${escapeHtml(t('suggest_leads_item_2'))}</li>
              <li>${escapeHtml(t('suggest_leads_item_3'))}</li>
              <li>${escapeHtml(t('suggest_leads_item_4'))}</li>
            </ul>
          </div>
        </div>`;
      // 复用来源详情模态框作为线索入口
      openSourceModal(t('suggest_leads'), tips);
    }, { once: true });
  } catch (_) {}
}

// 网格两行折叠：根据每个 info-item 的 offsetTop 分行，超过两行时折叠
function setupGridCollapse(resultItem) {
  const grid = resultItem.querySelector('.info-grid');
  if (!grid) return;
  const items = Array.from(grid.querySelectorAll('.info-item'));
  if (items.length === 0) return;

  // 通过 offsetTop 聚合每一行
  const rowMap = new Map();
  items.forEach((el) => {
    const top = Math.round(el.offsetTop);
    const arr = rowMap.get(top) || [];
    arr.push(el);
    rowMap.set(top, arr);
  });
  const rowTops = Array.from(rowMap.keys()).sort((a, b) => a - b);
  if (rowTops.length <= 2) return; // 两行及以下不折叠

  // 第二行的底部高度
  const secondTop = rowTops[1];
  const secondRowItems = rowMap.get(secondTop) || [];
  const row2Bottom = Math.max(...secondRowItems.map(el => el.offsetTop + el.offsetHeight));
  const collapsedHeight = row2Bottom - grid.offsetTop; // grid 内部高度

  // 初始化为折叠状态
  grid.style.maxHeight = `${collapsedHeight}px`;
  grid.classList.add('collapsed');
  grid.style.overflowY = 'hidden';

  // 添加展开/收起按钮
  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'grid-toggle';
  toggleBtn.setAttribute('aria-label', t('show_all'));
  toggleBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M6 9l6 6 6-6" />
    </svg>`;

  // 箭头浮在卡片上：插入到 resultItem 并绝对居中定位
  resultItem.appendChild(toggleBtn);

  const expand = () => {
    grid.classList.add('expanded');
    grid.style.maxHeight = `${grid.scrollHeight}px`;
    grid.style.overflowY = 'auto';
    toggleBtn.classList.add('up');
    toggleBtn.setAttribute('aria-label', '收起');
  };
  const collapse = () => {
    grid.classList.remove('expanded');
    grid.style.maxHeight = `${collapsedHeight}px`;
    grid.style.overflowY = 'hidden';
    toggleBtn.classList.remove('up');
  toggleBtn.setAttribute('aria-label', t('show_all'));
  };

  toggleBtn.addEventListener('click', () => {
    if (grid.classList.contains('expanded')) {
      collapse();
    } else {
      expand();
    }
  });
}

export function displayError(resultsContentEl, message) {
  if (!resultsContentEl) return;
  renderStatusPanel(resultsContentEl, { type: 'error', retry: true, retryId: 'retrySearchBtn', desc: message });
  bindRetry(resultsContentEl, () => {
    const input = document.getElementById('searchInput');
    if (input && input.value.trim()) {
      const searchButton = document.getElementById('searchButton');
      if (searchButton) searchButton.click();
    }
  }, 'retrySearchBtn');
}

// 统一状态面板渲染函数
// renderStatusPanel 已抽取为共享模块

// 字段翻译
export function translateKey(key) {
  const k = String(key || '').trim();
  const upper = k.toUpperCase();
  const lower = k.toLowerCase();

  const mapUpper = {
    ID_CARD: t('field_id_card'),
    PHONES: t('field_phones'),
    PHONE: t('field_phone'),
    EMAILS: t('field_emails'),
    QQS: t('field_qqs'),
    QQ: t('field_qq'),
    WEIBO_UIDS: t('field_weibo_uids'),
    WEIBO_UID: t('field_weibo_uid'),
    EMAIL: t('field_email'),
    NAME: t('field_name'),
    GENDER: t('field_gender'),
    BIRTH_DATE: t('field_birth_date'),
    NATIVE_PLACE: t('field_native_place'),
    LOCATION: t('field_location'),
    ADDRESS: t('field_address'),
    COMPANY: t('field_company'),
    POSITION: t('field_position'),
    INDUSTRY: t('field_industry'),
    CUSTOM_INFO: t('field_custom_info'),
    METADATA: t('field_metadata'),
    CREATED_AT: t('field_created_at'),
    UPDATED_AT: t('field_updated_at'),
    DATA_SOURCES: t('field_data_sources'),
    FORMATTED_DATA_SOURCES: t('field_formatted_data_sources'),
    SOURCE: t('field_source'),
    CAPTURED_AT: t('field_captured_at'),
    RELATIVE_NAME: t('field_relative_name'),
    RELATIVE_PHONE: t('field_relative_phone'),
    SPOUSE_NAME: t('field_spouse_name'),
    SPOUSE_PHONE: t('field_spouse_phone'),
    RELATIONSHIP: t('field_relationship'),
    RELATED_TO: t('field_related_to')
  };
  if (mapUpper[upper]) return mapUpper[upper];

  // 规则匹配，避免大小写或命名差异导致未翻译
  if (upper.includes('RELATIVE') && upper.includes('PHONE')) return t('field_relative_phone');
  if (upper.includes('RELATIVE') && (upper.includes('NAME') || upper.includes('REALNAME'))) return t('field_relative_name');
  if (upper.includes('SPOUSE') && upper.includes('PHONE')) return t('field_spouse_phone');
  if (upper.includes('SPOUSE') && (upper.includes('NAME') || upper.includes('REALNAME'))) return t('field_spouse_name');

  const mapLower = {
    relationship: t('field_relationship'),
    related_to: t('field_related_to'),
    id_card: t('field_id_card'),
    phones: t('field_phones'),
    phone: t('field_phone'),
    emails: t('field_emails'),
    qqs: t('field_qqs'),
    qq: t('field_qq'),
    weibo_uids: t('field_weibo_uids'),
    weibo_uid: t('field_weibo_uid'),
    email: t('field_email'),
    name: t('field_name'),
    gender: t('field_gender'),
    birth_date: t('field_birth_date'),
    native_place: t('field_native_place'),
    location: t('field_location'),
    address: t('field_address'),
    company: t('field_company'),
    position: t('field_position'),
    industry: t('field_industry'),
    custom_info: t('field_custom_info'),
    metadata: t('field_metadata'),
    created_at: t('field_created_at'),
    updated_at: t('field_updated_at'),
    data_sources: t('field_data_sources'),
    formatted_data_sources: t('field_formatted_data_sources'),
    source: t('field_source'),
    captured_at: t('field_captured_at'),
    ai_confidence: t('field_ai_confidence') || '置信度'
  };
  return mapLower[lower] || k;
}

// 简易来源详情模态框
function openSourceModal(title, innerHtml) {
  const modal = document.getElementById('sourceModal');
  const titleEl = document.getElementById('sourceModalTitle');
  const bodyEl = document.getElementById('sourceDetailBody');
  if (!modal || !titleEl || !bodyEl) return;
  titleEl.textContent = title || t('field_source');
  bodyEl.innerHTML = innerHtml || '';
  modal.style.display = 'block';
  const closeBtn = document.getElementById('closeSourceModal');
  if (closeBtn) closeBtn.onclick = () => { modal.style.display = 'none'; };
  modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
}

// 统一处理 AI 按键点击：可点击但无实际效果
window.analyzeWithAI = async function(index) {
  let success = false;
  try {
    const results = window.searchResults || [];
    const res = results[index];
    if (!res) { showToast && showToast(t('invalid_result')); return; }
    const idCard = (res.id_card || '').trim();
    if (!idCard) { showToast && showToast(t('missing_id_card_assess_unavailable')); return; }

    const item = document.querySelector(`.result-item[data-index="${index}"]`);
    const deskCircle = item && item.querySelector('.confidence-circle.desktop-only');
    const mobCircle = item && item.querySelector('.confidence-circle.mobile-only');
    const aiBtn = item && item.querySelector('.ai-btn');
    if (deskCircle) deskCircle.classList.add('loading');
    if (mobCircle) mobCircle.classList.add('loading');
    aiBtn && (aiBtn.disabled = true);

    const resp = await fetch('/api/ai/assess_confidence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject: res, id_card: idCard })
    });
    const data = await resp.json();
    if (!resp.ok || !data.success) {
      const msg = data.message || data.error || '';
      showToast && showToast(`${t('ai_assess_error_prefix')}${escapeHtml(msg || '')}`);
      return;
    }

    const updated = data.data || {};
    results[index] = Object.assign({}, res, updated);
    window.searchResults = results;
    displayResults(results);
    showToast && showToast(t('ai_assess_done'));
    success = true;
  } catch (error) {
    console.error('AI按键点击错误:', error);
    showToast && showToast(`${t('ai_assess_error_prefix')}${escapeHtml(error.message || t('unknown'))}`);
  } finally {
    const item = document.querySelector(`.result-item[data-index="${index}"]`);
    const deskCircle = item && item.querySelector('.confidence-circle.desktop-only');
    const mobCircle = item && item.querySelector('.confidence-circle.mobile-only');
    const aiBtn = item && item.querySelector('.ai-btn');
    if (!success) {
      if (deskCircle) deskCircle.classList.remove('loading');
      if (mobCircle) mobCircle.classList.remove('loading');
    }
    aiBtn && (aiBtn.disabled = false);
  }
}

// 复制结果到剪贴板（全局），供按钮 onclick 调用
  window.copyResult = async function(index) {
  try {
    const results = window.searchResults || [];
    if (!Array.isArray(results) || !results[index]) {
      showToast && showToast(t('copy_failed_invalid'));
      return;
    }
    const res = results[index];

    // 新逻辑：复制该结果中的“全部字段”（含数组与对象），并优先输出常见主字段
    const primaryOrder = [
      'name', 'id', 'id_card', 'gender', 'native_place', 'birth_date',
      'phones', 'phone', 'emails', 'email', 'qqs', 'qq', 'weibo_uids', 'weibo_uid',
      'company', 'position', 'spouse_name', 'spouse_phone',
      'relatives_names', 'relatives_phones', 'relatives_relations',
      'location', 'address', 'data_sources', 'ai_confidence', 'metadata'
    ];

    function formatPlain(value, key) {
      const lowerKey = String(key || '').toLowerCase();
      if (Array.isArray(value)) {
        const items = value.map((v) => {
          // 手机数组
          if (lowerKey === 'phones' || lowerKey === 'phone') {
            if (typeof v === 'string') return v.trim();
            if (v && typeof v === 'object') return String(v.number ?? '').trim();
            return '';
          }
          // 邮箱数组
          if (lowerKey === 'emails' || lowerKey === 'email') {
            if (typeof v === 'string') return v.trim();
            if (v && typeof v === 'object') return String(v.email ?? '').trim();
            return '';
          }
          // QQ数组
          if (lowerKey === 'qqs' || lowerKey === 'qq') {
            if (typeof v === 'string') return v.trim();
            if (v && typeof v === 'object') {
              const num = String(v.qq ?? v.number ?? '').trim();
              const digits = num.replace(/\D/g, '');
              return v.name ? `${v.name} (${digits || num})` : (digits || num);
            }
            return '';
          }
          // 微博UID数组
          if (lowerKey === 'weibo_uids' || lowerKey === 'weibo_uid') {
            if (typeof v === 'string') return v.trim();
            if (v && typeof v === 'object') {
              const uid = String(v.uid ?? '').trim();
              const digits = uid.replace(/\D/g, '');
              return v.name ? `${v.name} (${digits || uid})` : (digits || uid);
            }
            return '';
          }
          // 其他数组项：转字符串
          if (typeof v === 'object' && v !== null) {
            try { return JSON.stringify(v); } catch { return String(v); }
          }
          return String(v ?? '').trim();
        }).map(s => String(s).trim()).filter(s => s);
        // 去重
        const uniq = Array.from(new Set(items));
        return uniq.join(', ');
      }
      if (value && typeof value === 'object') {
        // 针对单个对象的友好格式化
        if (lowerKey === 'phone' || lowerKey === 'phones') {
          const num = String(value.number ?? '').trim();
          return num || '';
        }
        if (lowerKey === 'email' || lowerKey === 'emails') {
          const em = String(value.email ?? '').trim();
          return em || '';
        }
        if (lowerKey === 'qq' || lowerKey === 'qqs') {
          const num = String(value.qq ?? value.number ?? '').trim();
          const digits = num.replace(/\D/g, '');
          const label = value.name ? `${value.name} (${digits || num})` : (digits || num);
          return label || '';
        }
        if (lowerKey === 'weibo_uid' || lowerKey === 'weibo_uids') {
          const uid = String(value.uid ?? '').trim();
          const digits = uid.replace(/\D/g, '');
          const label = value.name ? `${value.name} (${digits || uid})` : (digits || uid);
          return label || '';
        }
        try { return JSON.stringify(value, null, 2); } catch { return String(value); }
      }
      return value ?? '';
    }

    const lines = [];
    const title = res.name || res.id || res._id || '记录';
    lines.push(`【${String(title)}】`);

    const allKeys = Object.keys(res);
    // 先输出主序列中存在的键，再输出剩余的全部键（排序稳定）
    const hasPhones = Array.isArray(res.phones) ? res.phones.length > 0 : !!res.phones;
    const hasEmails = Array.isArray(res.emails) ? res.emails.length > 0 : !!res.emails;
    const hasQqs = Array.isArray(res.qqs) ? res.qqs.length > 0 : !!res.qqs;
    const hasWeibos = Array.isArray(res.weibo_uids) ? res.weibo_uids.length > 0 : !!res.weibo_uids;

    const orderedSet = new Set();
    for (const key of primaryOrder) {
      if (!(key in res)) continue;
      if (key === 'phone' && hasPhones) continue;
      if (key === 'email' && hasEmails) continue;
      if (key === 'qq' && hasQqs) continue;
      if (key === 'weibo_uid' && hasWeibos) continue;
      orderedSet.add(key);
    }
    const restKeys = allKeys.filter(k => !orderedSet.has(k)).sort((a,b)=>String(a).localeCompare(String(b)));
    const keysToCopy = [...orderedSet, ...restKeys];

    for (const key of keysToCopy) {
      const val = res[key];
      const hasArray = Array.isArray(val) ? val.length > 0 : false;
      if (val === undefined || (Array.isArray(val) && !hasArray)) continue;
      const formatted = formatPlain(val, key);
      // 跳过空/未知值
      if (typeof formatted === 'string') {
        const s = formatted.trim();
        if (!s || s === '无') continue;
      }
      const k = translateKey ? translateKey(key) : key;
      lines.push(`${k}: ${formatted}`);
    }

    const text = lines.join('\n');

    // Clipboard API 优先，降级使用 textarea + execCommand
    let copied = false;
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch (_) {}
    }
    if (!copied) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try { document.execCommand('copy'); copied = true; } catch (_) { copied = false; }
      document.body.removeChild(ta);
    }

    if (copied) {
      showToast ? showToast(t('copied_to_clipboard')) : alert(t('copied_to_clipboard'));
    } else {
      showToast ? showToast(t('copy_failed_try_manual')) : alert(t('copy_failed'));
    }
  } catch (err) {
    console.error('复制错误:', err);
    showToast ? showToast(`${t('copy_failed_prefix')}${escapeHtml(err.message || t('unknown'))}`) : alert(t('copy_failed'));
  }
}

// 将后端返回的 ai_confidence 归一化为统一字段名结构
function normalizeConfidence(conf) {
  if (!conf || typeof conf !== 'object') return null;
  const level = conf.level || conf.credibility_level || conf.confidence_level || conf.grade || conf.status;
  const percentage = conf.percentage || conf.percent || conf.ratio || conf.score;
  return {
    level: level != null ? String(level) : undefined,
    percentage: percentage != null ? String(percentage) : undefined,
    report: conf.report || conf.analysis || conf.detail || '',
    provider: conf.provider || conf.vendor || conf.source || '',
    model: conf.model || conf.engine || ''
  };
}

// 解析百分比字符串到 0-100 数值；支持 "85%"、"0.85"、85
function parsePercentage(p) {
  if (p == null) return 0;
  let s = typeof p === 'number' ? String(p) : String(p).trim();
  if (s.endsWith('%')) s = s.slice(0, -1);
  const num = parseFloat(s);
  if (!isFinite(num)) return 0;
  if (num <= 1) return Math.round(num * 100);
  return Math.max(0, Math.min(100, Math.round(num)));
}