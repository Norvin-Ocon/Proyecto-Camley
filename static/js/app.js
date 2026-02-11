// ==================== FUNCIONALIDADES GLOBALES ====================

// Notificaciones en tiempo real
function checkNotifications() {
    if (!window.currentUserId) return;
    
    fetch(`/api/notificaciones/${window.currentUserId}`)
        .then(response => response.json())
        .then(notifications => {
            const unread = notifications.filter(n => !n.leida);
            
            // Actualizar contador
            const badge = document.getElementById('notificationBadge');
            if (badge) {
                if (unread.length > 0) {
                    badge.textContent = unread.length;
                    badge.classList.remove('d-none');
                } else {
                    badge.classList.add('d-none');
                }
            }
            
            // Sonido para nuevas notificaciones
            if (unread.length > window.lastNotificationCount) {
                playNotificationSound();
            }
            
            window.lastNotificationCount = unread.length;
        })
        .catch(error => console.error('Error checking notifications:', error));
}

// Sonido de notificación
function playNotificationSound() {
    const audio = new Audio('/static/sounds/notification.mp3');
    audio.play().catch(e => console.log('Audio error:', e));
}

// Geolocalización para conductores
function getLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject('Geolocalización no soportada');
        } else {
            navigator.geolocation.getCurrentPosition(
                position => resolve({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy
                }),
                error => reject(error.message)
            );
        }
    });
}

// Formatear fecha
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-ES', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Formatear moneda
function formatCurrency(amount) {
    return new Intl.NumberFormat('es-NI', {
        style: 'currency',
        currency: 'NIO'
    }).format(amount);
}

// Validar email
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Validar teléfono
function isValidPhone(phone) {
    const re = /^[\+]?[1-9][\d]{0,15}$/;
    return re.test(phone.replace(/\s/g, ''));
}

// Debounce para búsquedas
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ==================== PWA FUNCTIONS ====================

// Verificar si es PWA
function isRunningAsPWA() {
    return window.matchMedia('(display-mode: standalone)').matches || 
            window.navigator.standalone === true;
}

// Instalar PWA
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallButton();
});

function showInstallButton() {
    const installBtn = document.getElementById('installPWA');
    if (installBtn) {
        installBtn.classList.remove('d-none');
        installBtn.addEventListener('click', installPWA);
    }
}

function installPWA() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                console.log('✅ PWA instalado');
            }
            deferredPrompt = null;
        });
    }
}

// ==================== INIT ====================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 App Camley iniciada');
    
    // Configurar PWA (sin Service Worker en localhost para evitar cache viejo en desarrollo)
    if ('serviceWorker' in navigator) {
        const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname);
        if (isLocalhost) {
            navigator.serviceWorker.register('/sw-kill.js')
                .then(() => navigator.serviceWorker.getRegistrations())
                .then(regs => Promise.all(regs.map(r => r.unregister())))
                .then(() => console.log('ℹ️ Service Worker limpiado en localhost'))
                .catch(err => console.log('⚠️ Error limpiando Service Worker local:', err));
        } else {
            navigator.serviceWorker.register('/service-worker.js')
                .then(reg => console.log('✅ Service Worker registrado:', reg.scope))
                .catch(err => console.log('❌ Service Worker error:', err));
        }
    }
    
    // Verificar notificaciones cada 30 segundos
    if (window.currentUserId) {
        setInterval(checkNotifications, 30000);
        checkNotifications(); // Primera verificación
    }
    
    // Configurar auto-logout después de 30 minutos de inactividad
    let inactivityTimer;
    function resetTimer() {
        clearTimeout(inactivityTimer);
        inactivityTimer = setTimeout(logoutWarning, 25 * 60 * 1000); // 25 minutos
    }
    
    function logoutWarning() {
        if (confirm('Tu sesión está por expirar por inactividad. ¿Quieres continuar?')) {
            resetTimer();
        } else {
            window.location.href = '/logout';
        }
    }
    
    // Eventos para resetear timer
    ['click', 'mousemove', 'keypress', 'scroll'].forEach(event => {
        document.addEventListener(event, resetTimer);
    });
    
    resetTimer(); // Iniciar timer
    
    // Configurar offline/online detection
    window.addEventListener('online', () => {
        showNotification('✅ Conexión restablecida', 'success');
    });
    
    window.addEventListener('offline', () => {
        showNotification('⚠️ Estás sin conexión a internet', 'warning');
    });

    // Mostrar/ocultar contraseñas con mantener presionado
    const toggles = document.querySelectorAll('.password-toggle');
    toggles.forEach(btn => {
        const targetId = btn.getAttribute('data-target');
        const input = document.getElementById(targetId);
        const icon = btn.querySelector('i');
        if (!input) return;

        const show = () => {
            input.type = 'text';
            if (icon) {
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
            }
        };

        const hide = () => {
            input.type = 'password';
            if (icon) {
                icon.classList.add('bi-eye-slash');
                icon.classList.remove('bi-eye');
            }
        };

        btn.addEventListener('mousedown', show);
        btn.addEventListener('touchstart', show);
        btn.addEventListener('mouseup', hide);
        btn.addEventListener('mouseleave', hide);
        btn.addEventListener('touchend', hide);
        btn.addEventListener('touchcancel', hide);
    });
});

// ==================== EXPORT FUNCTIONS ====================
// Para uso en otros archivos
window.AppUtils = {
    formatDate,
    formatCurrency,
    isValidEmail,
    isValidPhone,
    getLocation,
    debounce,
    isRunningAsPWA
};
