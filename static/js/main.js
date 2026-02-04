// JavaScript principal para Camley Transporte

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚌 Camley Transporte - Sistema cargado');
    
    // ============ FUNCIONES GENERALES ============
    
    // Auto-ocultar alerts
    const autoHideAlerts = () => {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            setTimeout(() => {
                if (alert.parentElement) {
                    const bsAlert = new bootstrap.Alert(alert);
                    bsAlert.close();
                }
            }, 5000);
        });
    };
    
    // Inicializar tooltips
    const initTooltips = () => {
        const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltips.forEach(tooltip => {
            new bootstrap.Tooltip(tooltip);
        });
    };
    
    // Confirmación antes de acciones importantes
    const setupConfirmations = () => {
        const confirmButtons = document.querySelectorAll('[data-confirm]');
        confirmButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                const message = this.getAttribute('data-confirm') || '¿Estás seguro de realizar esta acción?';
                if (!confirm(message)) {
                    e.preventDefault();
                    e.stopPropagation();
                    return false;
                }
            });
        });
    };
    
    // Formatear números como moneda
    window.formatCurrency = (amount) => {
        return new Intl.NumberFormat('es-NI', {
            style: 'currency',
            currency: 'NIO'
        }).format(amount);
    };
    
    // ============ FUNCIONALIDADES ESPECÍFICAS ============
    
    // Panel de administrador
    if (document.querySelector('.admin-dashboard')) {
        console.log('🔧 Panel de administrador detectado');
        
        // Actualizar estadísticas
        const updateStats = () => {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    // Actualizar contadores
                    document.querySelectorAll('[data-stat]').forEach(element => {
                        const stat = element.getAttribute('data-stat');
                        if (data[stat] !== undefined) {
                            element.textContent = data[stat];
                        }
                    });
                })
                .catch(error => console.error('Error actualizando stats:', error));
        };
        
        // Actualizar cada 30 segundos
        setInterval(updateStats, 30000);
    }
    
    // Panel de conductor - GPS
    if (document.querySelector('.conductor-dashboard')) {
        console.log('🚍 Panel de conductor detectado');
        
        const updateLocationBtn = document.getElementById('update-location');
        const locationStatus = document.getElementById('location-status');
        
        if (updateLocationBtn) {
            updateLocationBtn.addEventListener('click', function() {
                if (navigator.geolocation) {
                    locationStatus.innerHTML = '<span class="text-warning">📍 Obteniendo ubicación...</span>';
                    
                    navigator.geolocation.getCurrentPosition(
                        // Éxito
                        (position) => {
                            const lat = position.coords.latitude;
                            const lng = position.coords.longitude;
                            
                            // Enviar al servidor
                            fetch('/conductor/ubicacion/actualizar', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                },
                                body: JSON.stringify({
                                    lat: lat,
                                    lng: lng
                                })
                            })
                            .then(response => response.json())
                            .then(data => {
                                if (data.success) {
                                    locationStatus.innerHTML = 
                                        `<span class="text-success">✅ Ubicación actualizada</span>
                                        <br><small>Lat: ${lat.toFixed(4)}, Lng: ${lng.toFixed(4)}</small>`;
                                    
                                    // Notificar visualmente
                                    showNotification('Ubicación actualizada correctamente', 'success');
                                    
                                    // Actualizar mapa si existe
                                    if (window.updateMapLocation) {
                                        window.updateMapLocation(lat, lng);
                                    }
                                } else {
                                    locationStatus.innerHTML = 
                                        `<span class="text-danger">❌ Error: ${data.error}</span>`;
                                }
                            })
                            .catch(error => {
                                locationStatus.innerHTML = 
                                    `<span class="text-danger">❌ Error de conexión</span>`;
                                console.error('Error:', error);
                            });
                        },
                        // Error
                        (error) => {
                            let message = 'Error desconocido';
                            switch(error.code) {
                                case error.PERMISSION_DENIED:
                                    message = 'Permiso denegado';
                                    break;
                                case error.POSITION_UNAVAILABLE:
                                    message = 'Ubicación no disponible';
                                    break;
                                case error.TIMEOUT:
                                    message = 'Tiempo de espera agotado';
                                    break;
                            }
                            locationStatus.innerHTML = 
                                `<span class="text-danger">❌ ${message}</span>`;
                        }
                    );
                } else {
                    locationStatus.innerHTML = 
                        '<span class="text-danger">❌ Geolocalización no soportada</span>';
                }
            });
        }
    }
    
    // Panel de padres - Seguimiento
    if (document.querySelector('.padres-dashboard')) {
        console.log('👨‍👧 Panel de padres detectado');
        
        // Actualizar ubicación del vehículo
        const updateVehicleLocation = (estudianteId) => {
            if (!estudianteId) return;
            
            fetch(`/api/ubicacion/estudiante/${estudianteId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.ubicacion) {
                        // Actualizar en la interfaz
                        const locationElement = document.getElementById(`vehicle-location-${estudianteId}`);
                        if (locationElement) {
                            locationElement.innerHTML = 
                                `📍 Lat: ${data.ubicacion.lat.toFixed(4)}, Lng: ${data.ubicacion.lng.toFixed(4)}`;
                        }
                        
                        // Actualizar mapa
                        if (window.updateVehicleOnMap && data.ubicacion) {
                            window.updateVehicleOnMap(data.ubicacion.lat, data.ubicacion.lng);
                        }
                    }
                })
                .catch(error => console.error('Error actualizando ubicación:', error));
        };
        
        // Configurar actualizaciones periódicas
        document.querySelectorAll('[data-estudiante-id]').forEach(element => {
            const estudianteId = element.getAttribute('data-estudiante-id');
            // Actualizar cada 10 segundos
            setInterval(() => updateVehicleLocation(estudianteId), 10000);
        });
    }
    
    // ============ NOTIFICACIONES PUSH (SIMULACIÓN) ============
    
    // Solicitar permisos para notificaciones
    const requestNotificationPermission = () => {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    console.log('🔔 Permiso para notificaciones concedido');
                    showNotification('¡Notificaciones activadas!', 'info');
                }
            });
        }
    };
    
    // Mostrar notificación
    window.showNotification = (message, type = 'info') => {
        // Notificación del navegador
        if ('Notification' in window && Notification.permission === 'granted') {
            const icon = type === 'success' ? '✅' : 
                        type === 'warning' ? '⚠️' : 
                        type === 'error' ? '❌' : '📢';
            
            new Notification('Camley Transporte', {
                body: `${icon} ${message}`,
                icon: '/static/icon-192.png'
            });
        }
        
        // Notificación en la página
        const notificationContainer = document.getElementById('notification-container') || 
                                    createNotificationContainer();
        
        const notificationId = 'notif-' + Date.now();
        const notification = document.createElement('div');
        notification.id = notificationId;
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        notificationContainer.appendChild(notification);
        
        // Auto-eliminar después de 5 segundos
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(notification);
            bsAlert.close();
        }, 5000);
    };
    
    function createNotificationContainer() {
        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        container.style.maxWidth = '400px';
        document.body.appendChild(container);
        return container;
    }
    
    // ============ PWA ============
    
    // Detectar si se puede instalar como PWA
    let deferredPrompt;
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        
        // Mostrar botón de instalación
        const installBtn = document.createElement('div');
        installBtn.className = 'pwa-install-btn';
        installBtn.innerHTML = '📱';
        installBtn.title = 'Instalar como app';
        installBtn.addEventListener('click', installPWA);
        
        document.body.appendChild(installBtn);
    });
    
    function installPWA() {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            deferredPrompt.userChoice.then((choiceResult) => {
                if (choiceResult.outcome === 'accepted') {
                    console.log('✅ PWA instalado');
                    showNotification('¡App instalada correctamente!', 'success');
                }
                deferredPrompt = null;
            });
        }
    }
    
    // ============ INICIALIZACIÓN ============
    
    autoHideAlerts();
    initTooltips();
    setupConfirmations();
    requestNotificationPermission();
    
    // Manejar formularios con AJAX
    document.querySelectorAll('form[data-ajax]').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            
            // Mostrar loading
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Procesando...';
            submitBtn.disabled = true;
            
            fetch(this.action, {
                method: this.method,
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showNotification(data.message || '✅ Operación exitosa', 'success');
                    
                    // Redirigir si hay URL
                    if (data.redirect) {
                        setTimeout(() => {
                            window.location.href = data.redirect;
                        }, 1500);
                    }
                    
                    // Recargar si es necesario
                    if (data.reload) {
                        setTimeout(() => location.reload(), 1500);
                    }
                } else {
                    showNotification(data.error || '❌ Error en la operación', 'danger');
                }
            })
            .catch(error => {
                showNotification('❌ Error de conexión', 'danger');
                console.error('Error:', error);
            })
            .finally(() => {
                // Restaurar botón
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    });
    
    // Actualizar hora actual
    function updateCurrentTime() {
        const timeElements = document.querySelectorAll('.current-time');
        if (timeElements.length > 0) {
            const now = new Date();
            const timeString = now.toLocaleTimeString('es-NI');
            timeElements.forEach(el => {
                el.textContent = timeString;
            });
        }
    }
    
    setInterval(updateCurrentTime, 1000);
    updateCurrentTime();
    
    console.log('✅ JavaScript inicializado correctamente');
});