// Service Worker for PWA + Archive + Offline-friendly caching
// NOTE: This SW is designed to work under GitHub Pages subpaths (e.g. /morningnews/)

const CORE_CACHE = 'morning-news-core-v2';
const PAGES_CACHE = 'morning-news-pages-v2';

const CORE_ASSETS = [
    './',
    'index.html',
    'archive.html',
    'manifest.json',
    'logo.png',
    'sw.js'
];

// Install event (precache core)
self.addEventListener('install', (event) => {
    console.log('Service Worker installing...');
    self.skipWaiting();
    event.waitUntil(
        caches.open(CORE_CACHE).then((cache) => cache.addAll(CORE_ASSETS)).catch((err) => {
            console.warn('Core precache failed:', err);
        })
    );
});

// Activate event (cleanup old caches)
self.addEventListener('activate', (event) => {
    console.log('Service Worker activating...');
    event.waitUntil(
        (async () => {
            const keys = await caches.keys();
            await Promise.all(
                keys
                    .filter((k) => k.startsWith('morning-news-') && ![CORE_CACHE, PAGES_CACHE].includes(k))
                    .map((k) => caches.delete(k))
            );
            await self.clients.claim();
        })()
    );
});

function isHtmlRequest(request) {
    if (request.mode === 'navigate') return true;
    const accept = request.headers.get('accept') || '';
    return accept.includes('text/html');
}

async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    const fetchPromise = fetch(request)
        .then((response) => {
            if (response && response.ok) {
                cache.put(request, response.clone());
            }
            return response;
        })
        .catch(() => null);

    return cached || (await fetchPromise);
}

async function cacheFirst(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
}

// Fetch event
self.addEventListener('fetch', (event) => {
    const { request } = event;

    // Only cache GET / same-origin
    if (request.method !== 'GET') return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;

    // HTML pages (index, archive, output/*.html)
    if (isHtmlRequest(request)) {
        event.respondWith(
            (async () => {
                const response = await staleWhileRevalidate(request, PAGES_CACHE);
                if (response) return response;

                // Offline fallback: try cached index.html
                const cache = await caches.open(CORE_CACHE);
                return (await cache.match('index.html')) || Response.error();
            })()
        );
        return;
    }

    // Static assets: cache-first
    const isStatic =
        url.pathname.endsWith('.png') ||
        url.pathname.endsWith('.json') ||
        url.pathname.endsWith('.js') ||
        url.pathname.endsWith('.css') ||
        url.pathname.endsWith('.woff2');

    if (isStatic) {
        event.respondWith(cacheFirst(request, CORE_CACHE));
    }
});

// NOTE:
// 기존 Push Notification 기능은 사용률/운영 복잡도를 고려해 제거했습니다.
// Service Worker는 PWA 캐싱/오프라인 대응에만 사용됩니다.
