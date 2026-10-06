// Retire the previous vanilla frontend service worker and its caches.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil((async () => {
  for (const key of await caches.keys()) {
    if (key.startsWith('reportlint-shell-')) await caches.delete(key);
  }
  await self.registration.unregister();
})()));
