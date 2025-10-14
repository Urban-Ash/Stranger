// 简单前端 i18n 模块：管理语言、字典与翻译应用
const I18N_STORAGE_KEY = 'lang';
// 动态语言列表与原生标签映射（后端 /i18n/list 自动生成）
let supportedLangs = ['zh','zh-TW','en','ja','ko'];
let nativeLabelMap = { zh: '简体中文', 'zh-TW': '繁體中文', en: 'English', ja: '日本語', ko: '한국어' };
// 外部 JSON 语言包缓存：{ lang: { meta, strings } }
const externalDictionaries = {};

function detectLang() {
  const raw = (navigator.languages && navigator.languages[0]) || navigator.language || '';
  const lng = String(raw || '').toLowerCase();
  if (lng.startsWith('zh')) {
    if (lng.includes('hant') || lng.includes('tw') || lng.includes('hk')) return 'zh-TW';
    return 'zh';
  }
  if (lng.startsWith('ja')) return 'ja';
  if (lng.startsWith('ko')) return 'ko';
  if (lng.startsWith('en')) return 'en';
  return 'zh';
}

let currentLang = localStorage.getItem(I18N_STORAGE_KEY) || detectLang();

export function getLang() { return currentLang; }

// 加载指定语言的外部 JSON（仅使用外部字典）
async function loadLangJSON(lang) {
  try {
    const res = await fetch(`/i18n/${lang}.json?t=${Date.now()}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data && typeof data === 'object') {
      externalDictionaries[lang] = data;
      // 同步语言标签映射（如有提供）
      const lbl = (data.meta && data.meta.native_label) || null;
      if (lbl) nativeLabelMap[lang] = lbl;
    }
  } catch (e) {
    // 静默失败：不使用任何内置后备，不修改当前视图
  }
}

// 获取有效字典：仅使用外部 JSON（完全外部化）
function getEffectiveDict(lang) {
  const ext = (externalDictionaries[lang] && externalDictionaries[lang].strings) || null;
  return ext || null;
}

export function setLang(lang) {
  const allowed = getSupportedLangs();
  currentLang = (allowed && allowed.includes(lang)) ? lang : currentLang;
  localStorage.setItem(I18N_STORAGE_KEY, currentLang);
  // 仅在加载外部 JSON 后应用翻译
  loadLangJSON(currentLang).then(() => {
    applyTranslations();
    // 通知订阅者语言已更新（菜单与PWA可重刷）
    try { window.dispatchEvent(new CustomEvent('i18n:updated', { detail: { lang: currentLang } })); } catch {}
  });
}
export function t(key, vars) {
  const dict = getEffectiveDict(currentLang);
  let str = dict && dict[key];
  if (!str) { str = key; }
  if (vars && typeof vars === 'object') {
    Object.keys(vars).forEach(k => {
      str = String(str).replace(`{${k}}`, vars[k]);
    });
  }
  return str;
}

export function applyTranslations() {
  // 若外部字典尚未加载，避免覆盖模板默认文案
  const dict = getEffectiveDict(currentLang);
  if (!dict) return;
  // 文档标题
  try {
    document.title = `${t('app_title')} - ${t('subtitle')}`;
  } catch {}
  // 标题与副标题
  const title = document.getElementById('strangerTitle');
  if (title) title.textContent = t('app_title');
  const subtitle = document.querySelector('.subtitle');
  if (subtitle) subtitle.textContent = t('subtitle');
  // 主题按钮标签
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.title = t('theme_toggle_title');
    themeToggle.setAttribute('aria-label', t('theme_toggle_aria'));
  }
  // 返回按钮 ARIA
  const backToHome = document.getElementById('backToHome');
  if (backToHome) {
    backToHome.title = t('back_to_home');
    backToHome.setAttribute('aria-label', t('back_to_home'));
  }
  // 语言菜单 ARIA
  const langMenu = document.getElementById('langMenu');
  if (langMenu) {
    langMenu.setAttribute('aria-label', t('lang_menu_aria'));
  }
  // 搜索框占位
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.placeholder = t('search_placeholder');
  // 结果 loading 文案
  const loadingText = document.querySelector('#loadingIndicator p');
  if (loadingText) loadingText.textContent = t('searching');
  // 添加/编辑模态文案
  const addTitle = document.querySelector('#addModal .modal-header h2');
  if (addTitle) addTitle.textContent = t('add_title');
  const editTitle = document.querySelector('#editModal .modal-header h2');
  if (editTitle) editTitle.textContent = t('edit_title');
  function setLabel(sel, key) {
    const el = document.querySelector(sel);
    if (el) el.textContent = t(key);
  }
  setLabel("label[for='addName']", 'add_name');
  setLabel("label[for='addIdCard']", 'add_id_card');
  setLabel("label[for='addPhones']", 'add_phones');
  setLabel("label[for='addQqs']", 'add_qqs');
  setLabel("label[for='addWeiboUid']", 'add_weibo_uid');
  setLabel("label[for='addEmail']", 'add_email');
  setLabel("label[for='addGender']", 'add_gender');
  // 性别选项
  const genderSel = document.getElementById('addGender');
  if (genderSel && genderSel.options && genderSel.options.length >= 3) {
    genderSel.options[0].textContent = t('add_gender');
    genderSel.options[1].textContent = t('add_gender_male');
    genderSel.options[2].textContent = t('add_gender_female');
  }
  setLabel("label[for='addBirthDate']", 'add_birth_date');
  setLabel("label[for='addLocation']", 'add_location');
  setLabel("label[for='addCompany']", 'add_company');
  setLabel("label[for='addPosition']", 'add_position');
  setLabel("label[for='addIndustry']", 'add_industry');
  // 按钮文案
  const cancelAdd = document.getElementById('cancelAdd');
  if (cancelAdd) cancelAdd.textContent = t('add_cancel');
  const submitAdd = document.querySelector('#addDataForm .submit-btn');
  if (submitAdd) submitAdd.textContent = t('add_submit');

  // 编辑模态标签
  setLabel("label[for='editName']", 'add_name');
  setLabel("label[for='editIdCard']", 'add_id_card');
  setLabel("label[for='editPhones']", 'add_phones');
  setLabel("label[for='editQqs']", 'add_qqs');
  setLabel("label[for='editWeiboUid']", 'add_weibo_uid');
  setLabel("label[for='editEmail']", 'add_email');
  setLabel("label[for='editGender']", 'add_gender');
  const editGenderSel = document.getElementById('editGender');
  if (editGenderSel && editGenderSel.options && editGenderSel.options.length >= 3) {
    editGenderSel.options[0].textContent = t('add_gender');
    editGenderSel.options[1].textContent = t('add_gender_male');
    editGenderSel.options[2].textContent = t('add_gender_female');
  }
  setLabel("label[for='editBirthDate']", 'add_birth_date');
  setLabel("label[for='editLocation']", 'add_location');
  setLabel("label[for='editCompany']", 'add_company');
  setLabel("label[for='editPosition']", 'add_position');
  setLabel("label[for='editIndustry']", 'add_industry');
  setLabel("label[for='editCustomInfo']", 'field_custom_info');
  setLabel("label[for='editDataSources']", 'field_data_sources');
  // 编辑按钮与提示
  const deleteRecordBtn = document.getElementById('deleteRecord');
  if (deleteRecordBtn) deleteRecordBtn.textContent = t('delete_record');
  const cancelEditBtn = document.getElementById('cancelEdit');
  if (cancelEditBtn) cancelEditBtn.textContent = t('add_cancel');
  const submitEditBtn = document.querySelector('#editDataForm .submit-btn');
  if (submitEditBtn) submitEditBtn.textContent = t('edit_submit');
  const editHints = document.querySelectorAll('#editDataForm .form-hint');
  if (editHints && editHints.length >= 1) editHints[0].textContent = t('edit_custom_hint');
  if (editHints && editHints.length >= 2) editHints[1].textContent = t('edit_data_sources_hint');
  const existingSourcesLabel = document.querySelector('#existingSources label');
  if (existingSourcesLabel) existingSourcesLabel.textContent = t('existing_sources_label');
  // 来源详情弹窗标题
  const sourceModalTitle = document.getElementById('sourceModalTitle');
  if (sourceModalTitle) sourceModalTitle.textContent = t('source_detail_title');
  // 登录页文案
  const loginTitle = document.getElementById('login-title');
  if (loginTitle) loginTitle.textContent = t('login_title');
  // 输入框与标签
  const loginUser = document.getElementById('username');
  if (loginUser) loginUser.placeholder = t('login_username');
  const loginPass = document.getElementById('password');
  if (loginPass) loginPass.placeholder = t('login_password');
  const labelUsername = document.getElementById('labelUsername');
  if (labelUsername) labelUsername.textContent = t('login_username');
  const labelPassword = document.getElementById('labelPassword');
  if (labelPassword) labelPassword.textContent = t('login_password');
  const loginSubmit = document.getElementById('loginSubmit');
  if (loginSubmit) loginSubmit.textContent = t('login_submit');
  const loginError = document.getElementById('loginError');
  if (loginError && loginError.dataset && loginError.dataset.errorKey) {
    loginError.textContent = t(loginError.dataset.errorKey);
  }
}

// 刷新可用语言列表（后端自动发现 static/i18n/*.json）
export async function refreshLangs() {
  try {
    const res = await fetch(`/i18n/list?t=${Date.now()}`);
    if (!res.ok) return;
    const list = await res.json();
    if (Array.isArray(list) && list.length) {
      supportedLangs = list.map(it => it.code);
      // 重建原生标签映射
      const map = {};
      list.forEach(it => { map[it.code] = it.native_label || it.code; });
      nativeLabelMap = map;
      try { window.dispatchEvent(new CustomEvent('i18n:langs', { detail: { langs: list } })); } catch {}
    }
  } catch (e) {
    // 静默忽略错误（保留当前语言列表与标签映射）
  }
}

export function initI18n() {
  // 刷新语言列表并加载当前语言的外部 JSON，随后应用翻译
  refreshLangs();
  loadLangJSON(currentLang).then(() => {
    applyTranslations();
    try { window.dispatchEvent(new CustomEvent('i18n:updated', { detail: { lang: currentLang } })); } catch {}
  });
}

export function getSupportedLangs() {
  return supportedLangs;
}

export function getLangNativeLabel(lang) {
  return (nativeLabelMap && nativeLabelMap[lang]) ? nativeLabelMap[lang] : (lang || '');
}

// 新增PWA国际化支持函数
export function getPWAManifest() {
  const lang = getLang();
  return {
    name: t('pwa_app_name'),
    short_name: t('pwa_app_short_name'),
    id: 'stranger.app',
    lang: lang === 'zh' ? 'zh-CN' : lang === 'zh-TW' ? 'zh-TW' : lang === 'ja' ? 'ja' : lang === 'ko' ? 'ko' : 'en',
    dir: 'ltr',
    start_url: '/',
    scope: '/',
    display: 'standalone',
    orientation: 'portrait',
    background_color: '#0b0c10',
    theme_color: '#4FC3F7',
    description: t('pwa_description'),
    icons: [
      {
        src: '/static/icons/icon.svg',
        sizes: 'any',
        type: 'image/svg+xml',
        purpose: 'any maskable'
      }
    ],
    shortcuts: [
      {
        name: t('pwa_shortcut_search_name'),
        short_name: t('pwa_shortcut_search_short'),
        description: t('pwa_shortcut_search_desc'),
        url: '/?action=search'
      },
      {
        name: t('pwa_shortcut_add_name'),
        short_name: t('pwa_shortcut_add_short'),
        description: t('pwa_shortcut_add_desc'),
        url: '/?action=add'
      }
    ],
    categories: ['productivity', 'utilities'],
    prefer_related_applications: false
  };
}

// 更新PWA manifest
export function updatePWAManifest() {
  const manifestLink = document.querySelector('link[rel="manifest"]');
  if (manifestLink) {
    // 生成动态manifest URL，包含当前语言参数
    const currentLang = getLang();
    manifestLink.href = `/manifest.json?lang=${currentLang}&t=${Date.now()}`;
  }
}