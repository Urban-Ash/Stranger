/* Service Worker for Stranger: cache shell; do NOT cache API responses */
const CACHE_NAME = 'stranger-cache-v3';
const CORE_ASSETS = [
  '/',
  '/static/style.css',
  '/static/main.js',
  '/static/icons/icon.svg'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((k) => k !== CACHE_NAME && caches.delete(k)))).then(() => self.clients.claim())
  );
});

// Helper: classify requests
function isAPIRequest(url) {
  try {
    const u = new URL(url);
    return u.pathname.startsWith('/api/');
  } catch (_) { return false; }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = request.url;
  const dest = request.destination;

  // 仅缓存/匹配 GET 请求；POST/PUT/PATCH/DELETE 直接走网络，避免 Cache.put 报错
  if (request.method !== 'GET') {
    event.respondWith(fetch(request));
    return;
  }

  // 页面导航请求：离线时回退到缓存的首页
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => caches.match('/'))
    );
    return;
  }

  if (isAPIRequest(url)) {
    // Network-only for API; fallback to cache only if explicitly present
    event.respondWith(
      fetch(request).catch(() => caches.match(request))
    );
    return;
  }

  // 对脚本与样式采用网络优先以确保及时更新
  if (dest === 'script' || dest === 'style') {
    event.respondWith(
      fetch(request).then((resp) => {
        const clone = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        return resp;
      }).catch(() => caches.match(request))
    );
    return;
  }

  // 其他静态资源：stale-while-revalidate
  event.respondWith(
    caches.match(request).then((cached) => {
      const fetchPromise = fetch(request).then((networkResp) => {
        if (networkResp && networkResp.status === 200) {
          const clone = networkResp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
        }
        return networkResp;
      }).catch(() => cached);
      return cached || fetchPromise;
    })
  );
});