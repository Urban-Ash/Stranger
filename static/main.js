// 入口模块：装配搜索、编辑、添加逻辑（保留样式与 DOM 结构）
import { setupSearch, displayResults } from './modules/search.js?v=5';
import { initI18n, setLang, getLang, t, getSupportedLangs, getLangNativeLabel } from './modules/i18n.js?v=2';
import { openEditModal, bindEditModalEvents } from './modules/edit.js?v=3';
import { setupAddModal } from './modules/add.js?v=3';

function initApp() {
  // 初始化 i18n
  initI18n();
  // 主题切换初始化
  const root = document.documentElement;
  const savedTheme = localStorage.getItem('theme');
  if (savedTheme === 'light' || savedTheme === 'dark') {
    root.setAttribute('data-theme', savedTheme);
  }
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = root.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });
  }

  // 语言切换按钮
  const langToggle = document.getElementById('langToggle');
  const langToggleText = document.getElementById('langToggleText');
  const langMenu = document.getElementById('langMenu');
  const langDropdown = document.getElementById('langDropdown');

  const updateLangButtonText = () => {
    if (langToggleText && langToggle) {
      const lang = getLang();
      langToggleText.textContent = getLangNativeLabel(lang);
      langToggle.title = t('lang_toggle_title');
      langToggle.setAttribute('aria-label', t('lang_toggle_title'));
    }
  };

  const renderLangMenu = () => {
    if (!langMenu) return;
    const langs = getSupportedLangs();
    langMenu.innerHTML = '';
    const current = getLang();
    langs.forEach(l => {
      const li = document.createElement('li');
      li.textContent = getLangNativeLabel(l);
      if (l === current) li.classList.add('active');
      li.dataset.lang = l;
      langMenu.appendChild(li);
    });
  };

  // 初始渲染按钮与菜单
  updateLangButtonText();
  renderLangMenu();

  // 点击菜单项切换语言
  if (langMenu) {
    langMenu.addEventListener('click', (e) => {
      const item = e.target.closest('li');
      if (!item || !item.dataset.lang) return;
      const selected = item.dataset.lang;
      setLang(selected);
      updateLangButtonText();
      renderLangMenu();
      if (window.searchResults) {
        displayResults(window.searchResults);
      }
    });
  }

  // 点击展开/收起菜单（移除悬停交互，避免误触导致立即关闭）
  if (langDropdown && langToggle && langMenu) {
    langToggle.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      langDropdown.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!langDropdown.contains(e.target)) {
        langDropdown.classList.remove('open');
      }
    });
  }

  // 搜索初始化
  setupSearch({
    onResults: (results) => {
      window.searchResults = results || [];
      displayResults(window.searchResults);
    }
  });

  // 编辑模态绑定
  bindEditModalEvents();

  // 添加数据模态绑定
  setupAddModal();

  // 暴露编辑入口以兼容现有按钮标记
  window.editResult = function(index) {
    if (!window.searchResults || !window.searchResults[index]) return;
    openEditModal(window.searchResults[index], index);
  };

  // 注册 Service Worker 与安装入口
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(console.error);
  }

  const installBtn = document.getElementById('installBtn');
  let deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (installBtn) installBtn.style.display = 'inline-flex';
  });

  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      deferredPrompt = null;
      installBtn.style.display = 'none';
      console.log('Install prompt outcome:', outcome);
    });
  }
}

// 根据文档就绪状态执行初始化，避免错过 DOMContentLoaded 已触发的情况
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}

// 提供渲染函数的全局兼容回退，供动态导入或旧代码复用
// 避免多实例情况下找不到同名导出导致的调用异常
// eslint-disable-next-line no-undef
window.__renderModule = window.__renderModule || { displayResults };