const CACHE='reportlint-shell-v2';
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['/app/','/app/app.css','/app/app.js','/app/icon.svg','/app/complex.html','/app/complex.css','/app/complex.js']))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('reportlint-shell-')&&key!==CACHE).map(key=>caches.delete(key))))));
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);if(event.request.method!=='GET'||url.origin!==self.location.origin||!url.pathname.startsWith('/app/'))return;event.respondWith(fetch(event.request).catch(()=>caches.match(event.request).then(cached=>cached||Response.error())));});
