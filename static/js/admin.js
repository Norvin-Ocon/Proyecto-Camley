// ==================== FUNCIONES GENERALES ====================

// CSRF Token
function getCSRFToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : '';
}

// Mostrar loading
function showLoading(button) {
    const originalText = button.innerHTML;
    button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Procesando...';
    button.disabled = true;
    return originalText;
}

// Restaurar botón
function restoreButton(button, originalText) {
    button.innerHTML = originalText;
    button.disabled = false;
}

// Mostrar notificación
function showNotification(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container-fluid') || document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// ==================== FUNCIONES PARA ESTUDIANTES ====================

function verDetallesEstudiante(id) {
    window.location.href = `/admin/estudiantes/editar/${id}`;
}

function editarEstudiante(id) {
    window.location.href = `/admin/estudiantes/editar/${id}`;
}

function eliminarEstudiante(id, nombre) {
    if (confirm(`¿Estás seguro de eliminar a "${nombre}"? Esta acción no se puede deshacer.`)) {
        const button = (typeof event !== 'undefined' && event.target) ? event.target : document.activeElement;
        const originalText = showLoading(button);
        
        fetch(`/admin/estudiantes/eliminar/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('Error: ' + data.error, 'danger');
                restoreButton(button, originalText);
            }
        })
        .catch(error => {
            showNotification('Error de conexión: ' + error, 'danger');
            restoreButton(button, originalText);
        });
    }
}

// ==================== FUNCIONES PARA PAGOS ====================

function agregarPago() {
    const form = document.getElementById('formAgregarPago');
    const button = form.querySelector('button[type="submit"]');
    const originalText = showLoading(button);
    
    const formData = new FormData(form);
    
    fetch('/admin/pagos/registrar', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            const modalPago = document.getElementById('addPaymentModal') || document.getElementById('modalAgregarPago');
            if (modalPago) {
                const bsModal = bootstrap.Modal.getInstance(modalPago) || new bootstrap.Modal(modalPago);
                bsModal.hide();
            }
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Error: ' + data.error, 'danger');
            restoreButton(button, originalText);
        }
    })
    .catch(error => {
        showNotification('Error de conexión: ' + error, 'danger');
        restoreButton(button, originalText);
    });
}

function marcarComoPagado(pagoId, estudianteNombre) {
    if (confirm(`¿Marcar como pagado el pago de ${estudianteNombre}?`)) {
        fetch(`/admin/pagos/marcar_pagado/${pagoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('Error: ' + data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Error de conexión: ' + error, 'danger');
        });
    }
}

function eliminarPago(pagoId, estudianteNombre) {
    if (confirm(`¿Eliminar el registro de pago de ${estudianteNombre}?`)) {
        fetch(`/admin/pagos/eliminar/${pagoId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('Error: ' + data.error, 'danger');
            }
        })
        .catch(error => {
            showNotification('Error de conexión: ' + error, 'danger');
        });
    }
}

// ==================== FUNCIONES PARA CONDUCTORES ====================

function activarConductor(id, nombre, actualmenteActivo) {
    const accion = actualmenteActivo ? 'desactivar' : 'activar';
    
    if (confirm(`${accion.toUpperCase()} a "${nombre}"?`)) {
        const button = (typeof event !== 'undefined' && event.target) ? event.target : document.activeElement;
        const originalText = showLoading(button);
        
        fetch(`/admin/conductores/activar/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('Error: ' + data.error, 'danger');
                restoreButton(button, originalText);
            }
        })
        .catch(error => {
            showNotification('Error de conexión: ' + error, 'danger');
            restoreButton(button, originalText);
        });
    }
}

function asignarRutaConductor(conductorId, conductorNombre) {
    const rutaId = document.getElementById(`selectRuta${conductorId}`).value;
    
    if (!rutaId) {
        showNotification('Selecciona una ruta', 'warning');
        return;
    }
    
    if (confirm(`¿Asignar ruta a ${conductorNombre}?`)) {
        const button = (typeof event !== 'undefined' && event.target) ? event.target : document.activeElement;
        const originalText = showLoading(button);
        
        fetch(`/admin/conductores/asignar_ruta/${conductorId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify({ ruta_id: rutaId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification(data.message, 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                showNotification('Error: ' + data.error, 'danger');
                restoreButton(button, originalText);
            }
        })
        .catch(error => {
            showNotification('Error de conexión: ' + error, 'danger');
            restoreButton(button, originalText);
        });
    }
}

// ==================== FUNCIONES PARA FINANZAS ====================

function agregarIngreso() {
    const form = document.getElementById('formAgregarIngreso');
    const button = form.querySelector('button[type="submit"]');
    const originalText = showLoading(button);
    
    const formData = new FormData(form);
    
    fetch('/admin/finanzas/agregar_ingreso', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            const modalIngreso = document.getElementById('addIncomeModal') || document.getElementById('modalAgregarIngreso');
            if (modalIngreso) {
                const bsModal = bootstrap.Modal.getInstance(modalIngreso) || new bootstrap.Modal(modalIngreso);
                bsModal.hide();
            }
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Error: ' + data.error, 'danger');
            restoreButton(button, originalText);
        }
    })
    .catch(error => {
        showNotification('Error de conexión: ' + error, 'danger');
        restoreButton(button, originalText);
    });
}

function agregarGasto() {
    const form = document.getElementById('formAgregarGasto');
    const button = form.querySelector('button[type="submit"]');
    const originalText = showLoading(button);
    
    const formData = new FormData(form);
    
    fetch('/admin/finanzas/agregar_gasto', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification(data.message, 'success');
            const modalGasto = document.getElementById('addExpenseModal') || document.getElementById('modalAgregarGasto');
            if (modalGasto) {
                const bsModal = bootstrap.Modal.getInstance(modalGasto) || new bootstrap.Modal(modalGasto);
                bsModal.hide();
            }
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Error: ' + data.error, 'danger');
            restoreButton(button, originalText);
        }
    })
    .catch(error => {
        showNotification('Error de conexión: ' + error, 'danger');
        restoreButton(button, originalText);
    });
}

// ==================== INICIALIZACIÓN ====================

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Auto-ocultar alertas después de 5 segundos
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Validación de formularios
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Filtro de tablas
    const filterInputs = document.querySelectorAll('.table-filter');
    filterInputs.forEach(input => {
        input.addEventListener('keyup', function() {
            const filter = this.value.toLowerCase();
            const tableId = this.getAttribute('data-table');
            const table = document.getElementById(tableId);
            const rows = table.getElementsByTagName('tr');
            
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            }
        });
    });
});

