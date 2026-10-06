// Minimal Service Worker for Taiwan Stock PWA installability
const CACHE_NAME = 'twstock-pwa-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Pass-through to network
  event.respondWith(fetch(event.request));
});
