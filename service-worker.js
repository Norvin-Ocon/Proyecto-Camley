const CACHE_NAME = 'camley-transporte-v2.1';
const urlsToCache = [
'/',
'/login',
'/static/css/style.css',
'/static/js/admin.js',
'/static/js/app.js',
'/manifest.json'
];

// ==================== INSTALACIÓN ====================
self.addEventListener('install', event => {
console.log('🟢 Service Worker instalando...');

event.waitUntil(
    caches.open(CACHE_NAME)
    .then(cache => {
        console.log('📦 Cacheando archivos esenciales');
        return cache.addAll(urlsToCache);
    })
    .then(() => {
        console.log('✅ Todos los recursos cacheados');
        return self.skipWaiting();
    })
    .catch(error => {
        console.error('❌ Error cacheando:', error);
    })
);
});

// ==================== ACTIVACIÓN ====================
self.addEventListener('activate', event => {
console.log('🟡 Service Worker activado');

event.waitUntil(
    caches.keys().then(cacheNames => {
    return Promise.all(
        cacheNames.map(cacheName => {
        if (cacheName !== CACHE_NAME) {
            console.log(`🗑️ Eliminando cache viejo: ${cacheName}`);
            return caches.delete(cacheName);
        }
        })
    );
    }).then(() => {
    console.log('✅ Cache limpio, tomando control');
    return self.clients.claim();
    })
);
});

// ==================== INTERCEPTAR PETICIONES ====================
self.addEventListener('fetch', event => {
const url = new URL(event.request.url);

  // NO cachear API requests ni páginas dinámicas
if (url.pathname.includes('/api/') || 
    url.pathname.includes('/admin/') ||
    url.pathname.includes('/conductor/') ||
    url.pathname.includes('/padre/') ||
    event.request.method !== 'GET') {
    // Pasar directamente al servidor
    event.respondWith(fetch(event.request));
    return;
}

  // Para recursos estáticos y página principal, usar cache primero
event.respondWith(
    caches.match(event.request)
    .then(response => {
        // Si existe en cache, devolverlo
        if (response) {
        console.log(`📁 Sirviendo desde cache: ${url.pathname}`);
        return response;
        }
        
        // Si no está en cache, obtener del servidor
        console.log(`🌐 Obteniendo del servidor: ${url.pathname}`);
        return fetch(event.request).then(networkResponse => {
          // Verificar respuesta válida
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
            return networkResponse;
        }
        
          // Clonar respuesta para cache
        const responseToCache = networkResponse.clone();
        
          // Guardar en cache para futuras peticiones
        caches.open(CACHE_NAME)
            .then(cache => {
            cache.put(event.request, responseToCache);
            console.log(`💾 Guardado en cache: ${url.pathname}`);
            });
        
        return networkResponse;
        });
    })
    .catch(error => {
        console.error('❌ Error en fetch:', error);
        
        // Fallback para página principal
        if (event.request.mode === 'navigate') {
        return caches.match('/');
        }
        
        // Fallback para CSS/JS
        if (event.request.url.includes('.css')) {
          return new Response('/* Fallback CSS */', {
            headers: { 'Content-Type': 'text/css' }
        });
        }
        
        if (event.request.url.includes('.js')) {
        return new Response('// Fallback JS', {
            headers: { 'Content-Type': 'application/javascript' }
        });
        }
        
        return new Response('Página no disponible sin conexión', {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 'Content-Type': 'text/html' }
        });
        })
    );
});

// ==================== NOTIFICACIONES PUSH ====================
self.addEventListener('push', event => {
console.log('🔔 Notificación push recibida');

let data = {
    title: 'Camley Transporte',
    body: 'Tienes una nueva notificación',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge.png'
};

if (event.data) {
    try {
    data = JSON.parse(event.data.text());
    } catch (e) {
    data.body = event.data.text();
    }
}

const options = {
    body: data.body,
    icon: data.icon || '/static/icons/icon-192x192.png',
    badge: data.badge || '/static/icons/badge.png',
    vibrate: [100, 50, 100],
    data: {
    dateOfArrival: Date.now(),
    primaryKey: '1',
    url: data.url || '/'
    },
    actions: [
    {
        action: 'open',
        title: 'Abrir'
    },
    {
        action: 'close',
        title: 'Cerrar'
        }
    ]
};

event.waitUntil(
    self.registration.showNotification(data.title, options)
);
});

// ==================== CLICK EN NOTIFICACIÓN ====================
self.addEventListener('notificationclick', event => {
console.log('🔔 Notificación clickeada:', event.notification.tag);

event.notification.close();

const urlToOpen = event.notification.data.url || '/';

event.waitUntil(
    clients.matchAll({
    type: 'window',
    includeUncontrolled: true
    }).then(windowClients => {
      // Buscar si ya hay una pestaña abierta
    for (const client of windowClients) {
        if (client.url === urlToOpen && 'focus' in client) {
        return client.focus();
        }
    }
    
      // Si no hay pestaña, abrir una nueva
    if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
    }
    })
);
});

// ==================== SINCRONIZACIÓN EN SEGUNDO PLANO ====================
self.addEventListener('sync', event => {
console.log('🔄 Sincronización en segundo plano:', event.tag);

if (event.tag === 'sync-data') {
    event.waitUntil(syncData());
}
});

async function syncData() {
console.log('📡 Sincronizando datos...');
  // Aquí puedes agregar lógica para sincronizar datos offline
}

// ==================== MENSAJES ====================
self.addEventListener('message', event => {
console.log('📨 Mensaje recibido en Service Worker:', event.data);

if (event.data.type === 'CACHE_ASSETS') {
    // Cachear recursos adicionales
    caches.open(CACHE_NAME)
    .then(cache => cache.addAll(event.data.urls))
    .then(() => {
        event.ports[0].postMessage({ success: true });
    });
}
});
