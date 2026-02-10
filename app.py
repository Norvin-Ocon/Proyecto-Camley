from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session, send_from_directory
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from database import app, db, Usuario, Estudiante, Ruta, Pago, Gasto, Ingreso, Vehiculo, Notificacion, Asistencia, UbicacionVehiculo, UbicacionHistorial, PushSubscription, AsistenciaManual, TicketSoporte, crear_usuarios_ejemplo
from datetime import datetime, timedelta
import json
import os
from io import BytesIO
from pywebpush import webpush, WebPushException
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import calendar

# ==================== INICIALIZAR DB EN PRODUCCIÓN ====================
def init_db():
    try:
        with app.app_context():
            db.create_all()
            crear_usuarios_ejemplo()
    except Exception as e:
        print(f"DB init error: {e}")

init_db()

# ==================== CONFIGURACIÓN FLASK-LOGIN ====================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ==================== FUNCIONES AUXILIARES ====================
def crear_notificacion(usuario_id, tipo, mensaje, link=None):
    """Crear una notificación para un usuario"""
    notif = Notificacion(
        usuario_id=usuario_id,
        tipo=tipo,
        mensaje=mensaje,
        link=link,
        fecha=datetime.utcnow()
    )
    db.session.add(notif)
    db.session.commit()
    enviar_push_usuario(usuario_id, 'Camley Transporte', mensaje, link)
    return notif

def enviar_push_usuario(usuario_id, titulo, mensaje, url=None):
    """Enviar notificación push a un usuario"""
    vapid_public = os.getenv('VAPID_PUBLIC_KEY')
    vapid_private = os.getenv('VAPID_PRIVATE_KEY')
    vapid_email = os.getenv('VAPID_EMAIL', 'mailto:admin@camley.com')
    if not vapid_public or not vapid_private:
        return

    subs = PushSubscription.query.filter_by(usuario_id=usuario_id).all()
    payload = json.dumps({
        'title': titulo,
        'body': mensaje,
        'url': url or '/'
    })
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_email}
            )
        except WebPushException:
            # Si falla la suscripción, se ignora para no romper el flujo
            continue

def calcular_vencimiento(semanas=1):
    """Calcular fecha de vencimiento basada en semanas"""
    return datetime.utcnow() + timedelta(days=7 * semanas)

def obtener_semana_actual():
    """Obtener fecha de inicio y fin de la semana actual"""
    hoy = datetime.utcnow()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    fin_semana = inicio_semana + timedelta(days=6)
    return inicio_semana.date(), fin_semana.date()

def obtener_mes_actual():
    """Obtener fecha de inicio y fin del mes actual"""
    hoy = datetime.utcnow()
    inicio_mes = hoy.replace(day=1)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fin_mes = hoy.replace(day=ultimo_dia)
    return inicio_mes.date(), fin_mes.date()

def es_ajax():
    """Detectar si la solicitud es AJAX"""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
        request.accept_mimetypes['application/json'] > request.accept_mimetypes['text/html']

@app.context_processor
def inject_now():
    """Inyectar fecha actual en todas las plantillas"""
    return {'now': datetime.utcnow()}

# ==================== RUTAS PRINCIPALES ====================
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory(app.root_path, 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory(app.root_path, 'service-worker.js')

@app.route('/health')
def health():
    return 'ok', 200

@app.route('/api/push/public_key')
def push_public_key():
    return jsonify({'publicKey': os.getenv('VAPID_PUBLIC_KEY', '')})

@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint')
    keys = data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    if not endpoint or not p256dh or not auth:
        return jsonify({'success': False, 'error': 'Datos de suscripción inválidos'}), 400

    existente = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existente:
        existente.usuario_id = current_user.id
        existente.p256dh = p256dh
        existente.auth = auth
    else:
        sub = PushSubscription(
            usuario_id=current_user.id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth
        )
        db.session.add(sub)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint')
    if not endpoint:
        return jsonify({'success': False, 'error': 'Endpoint requerido'}), 400
    sub = PushSubscription.query.filter_by(endpoint=endpoint, usuario_id=current_user.id).first()
    if sub:
        db.session.delete(sub)
        db.session.commit()
    return jsonify({'success': True})

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login general"""
    if current_user.is_authenticated and request.method == 'GET':
        if current_user.rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.rol == 'padre':
            return redirect(url_for('padre_dashboard'))
        elif current_user.rol == 'conductor':
            return redirect(url_for('conductor_dashboard'))
    
    if current_user.is_authenticated and request.method == 'POST':
        logout_user()

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = Usuario.query.filter_by(email=email).first()
        
        if user and user.password == password:
            if user.activo:
                login_user(user, remember=True)
                flash(f'✅ Bienvenido {user.nombre}!', 'success')
                
                if user.rol == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.rol == 'padre':
                    return redirect(url_for('padre_dashboard'))
                elif user.rol == 'conductor':
                    return redirect(url_for('conductor_dashboard'))
            else:
                flash('❌ Tu cuenta está inactiva. Contacta al administrador.', 'error')
        else:
            flash('❌ Email o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    """Registro de nuevos usuarios"""
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        genero = request.form.get('genero')
        rol = request.form.get('rol', 'padre')
        
        # Solo el admin puede crear conductores. Nadie puede crear admins.
        if rol == 'admin':
            flash('❌ No se permite crear cuentas de administrador', 'error')
            return redirect(url_for('registro'))
        
        if rol == 'conductor' and (not current_user.is_authenticated or current_user.rol != 'admin'):
            flash('❌ No autorizado para crear conductores', 'error')
            return redirect(url_for('login'))
        
        # Si no es admin quien registra, forzar rol padre
        if not current_user.is_authenticated or current_user.rol != 'admin':
            rol = 'padre'
        
        if Usuario.query.filter_by(email=email).first():
            flash('❌ Este email ya está registrado', 'error')
            return redirect(url_for('registro'))
        
        activo = False
        if rol == 'conductor':
            activo = request.form.get('activo', 'false').lower() == 'true'
        elif rol == 'padre':
            activo = False  # padres requieren aprobación
        
        if not genero:
            flash('❌ Debes seleccionar el género', 'error')
            return redirect(url_for('registro'))

        nuevo_usuario = Usuario(
            nombre=nombre,
            email=email,
            password=password,
            telefono=telefono,
            direccion=direccion,
            genero=genero,
            rol=rol,
            activo=activo
        )
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        admin = Usuario.query.filter_by(rol='admin').first()
        if rol == 'conductor':
            if admin:
                crear_notificacion(
                    admin.id,
                    'sistema',
                    f'🚍 Nuevo conductor creado: {nombre}',
                    url_for('admin_conductores')
                )
            flash('✅ Conductor creado correctamente', 'success')
            return redirect(url_for('admin_conductores'))
        
        if rol == 'padre':
            if admin:
                crear_notificacion(
                    admin.id,
                    'sistema',
                    f'👨‍👩‍👧 Nuevo padre registrado: {nombre}. Requiere aprobación.',
                    url_for('admin_padres')
                )
            flash('✅ Registro exitoso. Tu cuenta será activada por el administrador.', 'success')
            return redirect(url_for('login'))
        
        flash('✅ Registro exitoso.', 'success')
        return redirect(url_for('login'))
    
    return render_template('registro.html')

@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('✅ Sesión cerrada correctamente', 'info')
    return redirect(url_for('index'))

# ==================== PANEL ADMINISTRADOR ====================
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Dashboard del administrador"""
    if current_user.rol != 'admin':
        flash('⚠️ No tienes permisos de administrador', 'error')
        return redirect(url_for('index'))
    
    total_estudiantes = Estudiante.query.count()
    total_rutas = Ruta.query.filter_by(activa=True).count()
    total_conductores = Usuario.query.filter_by(rol='conductor', activo=True).count()
    
    pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
    pagos_vencidos = Pago.query.filter(
        Pago.estado == 'pendiente',
        Pago.fecha_vencimiento < datetime.utcnow()
    ).count()
    
    inicio_semana, fin_semana = obtener_semana_actual()
    ingresos_semana = db.session.query(db.func.sum(Ingreso.monto)).filter(
        Ingreso.fecha >= inicio_semana
    ).scalar() or 0
    gastos_semana = db.session.query(db.func.sum(Gasto.monto)).filter(
        Gasto.fecha >= inicio_semana
    ).scalar() or 0
    
    conductores_pendientes = Usuario.query.filter_by(rol='conductor', activo=False).count()
    
    notificaciones = Notificacion.query.order_by(Notificacion.fecha.desc()).limit(5).all()
    ultimos_pagos = Pago.query.order_by(Pago.fecha_creacion.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                        estudiantes=total_estudiantes,
                        rutas=total_rutas,
                        conductores=total_conductores,
                        pagos_pendientes=pagos_pendientes,
                        pagos_vencidos=pagos_vencidos,
                        ingresos_semana=ingresos_semana,
                        gastos_semana=gastos_semana,
                        conductores_pendientes=conductores_pendientes,
                        notificaciones=notificaciones,
                        ultimos_pagos=ultimos_pagos,
                        inicio_semana=inicio_semana,
                        fin_semana=fin_semana)

# ==================== GESTIÓN DE ESTUDIANTES ====================
@app.route('/admin/estudiantes')
@login_required
def admin_estudiantes():
    """Lista de estudiantes"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    estudiantes = Estudiante.query.all()
    padres = Usuario.query.filter_by(rol='padre', activo=True).all()
    rutas = Ruta.query.filter_by(activa=True).all()
    
    return render_template('admin/estudiantes.html',
                        estudiantes=estudiantes,
                        padres=padres,
                        rutas=rutas)

@app.route('/admin/estudiantes/agregar', methods=['POST'])
@login_required
def agregar_estudiante():
    """Agregar nuevo estudiante"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        nombre = request.form['nombre']
        edad = int(request.form['edad'])
        grado = request.form['grado']
        genero = request.form.get('genero')
        escuela = request.form.get('escuela', '')
        condicion = request.form.get('condicion', '') or request.form.get('observaciones', '')
        padre_id = request.form.get('padre_id')
        ruta_id = request.form.get('ruta_id')
        
        if not genero:
            return jsonify({'success': False, 'error': 'Género requerido'}), 400

        existente = Estudiante.query.filter_by(
            nombre=nombre,
            grado=grado,
            escuela=escuela,
            padre_id=int(padre_id) if padre_id else None
        ).first()
        if existente:
            return jsonify({'success': False, 'error': 'Estudiante ya existe con los mismos datos'}), 400

        nuevo_estudiante = Estudiante(
            nombre=nombre,
            edad=edad,
            genero=genero,
            grado=grado,
            escuela=escuela,
            condicion=condicion,
            padre_id=int(padre_id) if padre_id else None,
            ruta_id=int(ruta_id) if ruta_id else None,
            fecha_inscripcion=datetime.utcnow()
        )
        
        db.session.add(nuevo_estudiante)
        db.session.commit()
        
        vencimiento = calcular_vencimiento(1)
        nuevo_pago = Pago(
            estudiante_id=nuevo_estudiante.id,
            monto=50.00,
            fecha_vencimiento=vencimiento,
            estado='pendiente',
            meses_cubiertos=1,
            fecha_creacion=datetime.utcnow()
        )
        
        db.session.add(nuevo_pago)
        
        if padre_id:
            padre = Usuario.query.get(padre_id)
            if padre:
                crear_notificacion(
                    padre.id,
                    'estudiante',
                    f'📚 {nombre} ha sido inscrito(a). Primer pago vence {vencimiento.strftime("%d/%m/%Y")}',
                    url_for('padre_dashboard')
                )
        
        db.session.commit()
        
        if es_ajax():
            return jsonify({
                'success': True,
                'message': '✅ Estudiante agregado exitosamente',
                'estudiante_id': nuevo_estudiante.id
            })
        
        flash('✅ Estudiante agregado exitosamente', 'success')
        return redirect(url_for('admin_estudiantes'))
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/estudiantes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_estudiante(id):
    """Editar estudiante existente"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    estudiante = Estudiante.query.get_or_404(id)
    
    if request.method == 'POST':
        estudiante.nombre = request.form['nombre']
        estudiante.edad = int(request.form['edad'])
        estudiante.grado = request.form['grado']
        estudiante.genero = request.form.get('genero', estudiante.genero)
        estudiante.escuela = request.form.get('escuela', '')
        estudiante.condicion = request.form.get('condicion', '') or request.form.get('observaciones', '')
        estudiante.padre_id = int(request.form['padre_id']) if request.form['padre_id'] else None
        estudiante.ruta_id = int(request.form['ruta_id']) if request.form['ruta_id'] else None
        
        db.session.commit()
        flash('✅ Estudiante actualizado exitosamente', 'success')
        return redirect(url_for('admin_estudiantes'))
    
    padres = Usuario.query.filter_by(rol='padre', activo=True).all()
    rutas = Ruta.query.filter_by(activa=True).all()
    
    return render_template('admin/editar_estudiante.html',
                        estudiante=estudiante,
                        padres=padres,
                        rutas=rutas)

@app.route('/admin/estudiantes/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_estudiante(id):
    """Eliminar estudiante"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    estudiante = Estudiante.query.get_or_404(id)
    
    try:
        Pago.query.filter_by(estudiante_id=id).delete()
        Asistencia.query.filter_by(estudiante_id=id).delete()
        
        if estudiante.padre_id:
            crear_notificacion(
                estudiante.padre_id,
                'estudiante',
                f'❌ {estudiante.nombre} ha sido dado de baja del sistema',
                url_for('padre_dashboard')
            )
        
        db.session.delete(estudiante)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Estudiante {estudiante.nombre} eliminado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== GESTIÓN DE PAGOS (COMPLETO) ====================
@app.route('/admin/pagos')
@login_required
def admin_pagos():
    """Lista de pagos - VERSIÓN CORREGIDA"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    estado = request.args.get('estado', 'todos')
    estudiante_id = request.args.get('estudiante_id')
    
    # Consulta con JOIN para obtener estudiante
    query = Pago.query.join(Estudiante, Pago.estudiante_id == Estudiante.id)
    
    if estado != 'todos':
        if estado == 'vencido':
            query = query.filter(
                Pago.estado == 'pendiente',
                Pago.fecha_vencimiento < datetime.utcnow()
            )
        else:
            query = query.filter(Pago.estado == estado)
    
    if estudiante_id and estudiante_id.isdigit():
        query = query.filter(Pago.estudiante_id == int(estudiante_id))
    
    pagos = query.order_by(
        Pago.estado,
        Pago.fecha_vencimiento.asc()
    ).all()
    
    estudiantes = Estudiante.query.order_by(Estudiante.nombre.asc()).all()
    
    return render_template('admin/pagos.html',
                        pagos=pagos,
                        estudiantes=estudiantes,
                        estado_actual=estado,
                        now=datetime.utcnow())

@app.route('/admin/pagos/registrar', methods=['POST'])
@login_required
def registrar_pago_admin():
    """Registrar un nuevo pago desde el panel admin"""
    if current_user.rol != 'admin':
        flash('No autorizado', 'error')
        return redirect(url_for('admin_pagos'))
    
    try:
        estudiante_id = request.form.get('estudiante_id')
        monto = float(request.form.get('monto', 0))
        metodo_pago = request.form.get('metodo_pago')
        estado = request.form.get('estado', 'pendiente')
        referencia = request.form.get('referencia', '')
        fecha_vencimiento_str = request.form.get('fecha_vencimiento')
        
        if not estudiante_id:
            flash('Debe seleccionar un estudiante', 'error')
            return redirect(url_for('admin_pagos'))
        
        estudiante = Estudiante.query.get(estudiante_id)
        if not estudiante:
            flash('Estudiante no encontrado', 'error')
            return redirect(url_for('admin_pagos'))
        
        fecha_vencimiento = None
        if fecha_vencimiento_str:
            fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, '%Y-%m-%d')
        else:
            fecha_vencimiento = datetime.utcnow() + timedelta(days=7)
        
        pago = Pago(
            estudiante_id=estudiante_id,
            monto=monto,
            estado=estado,
            metodo_pago=metodo_pago,
            referencia=referencia,
            fecha_vencimiento=fecha_vencimiento,
            fecha_creacion=datetime.utcnow()
        )
        if estado == 'pagado':
            pago.fecha_pago = datetime.utcnow()
        
        db.session.add(pago)
        db.session.flush()

        if estado == 'pagado':
            descripcion_ingreso = f'Pago de {estudiante.nombre}'
            existe_ingreso = Ingreso.query.filter_by(
                descripcion=descripcion_ingreso,
                monto=monto,
                fuente='pago_estudiante'
            ).order_by(Ingreso.fecha.desc()).first()
            if not existe_ingreso or (datetime.utcnow() - existe_ingreso.fecha).total_seconds() > 300:
                nuevo_ingreso = Ingreso(
                    descripcion=descripcion_ingreso,
                    monto=monto,
                    fuente='pago_estudiante',
                    fecha=datetime.utcnow()
                )
                db.session.add(nuevo_ingreso)
        
        if estudiante.padre_id:
            crear_notificacion(
                estudiante.padre_id,
                'pago',
                f'💰 Nuevo pago pendiente: C$ {monto} por {estudiante.nombre}. Vence: {fecha_vencimiento.strftime("%d/%m/%Y")}',
                url_for('padre_dashboard')
            )
        
        db.session.commit()
        flash(f'✅ Pago de C$ {monto} registrado para {estudiante.nombre}', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'error')
    
    return redirect(url_for('admin_pagos'))

@app.route('/admin/pagos/marcar_pagado/<int:pago_id>', methods=['POST'])
@login_required
def marcar_pago_pagado(pago_id):
    """Marcar pago como pagado"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    pago = Pago.query.get_or_404(pago_id)
    
    try:
        data = request.get_json(silent=True) or request.form
        pago.estado = 'pagado'
        pago.fecha_pago = datetime.utcnow()
        pago.metodo_pago = data.get('metodo_pago', 'efectivo')
        
        descripcion_ingreso = f'Pago de {pago.estudiante.nombre}'
        existe_ingreso = Ingreso.query.filter_by(
            descripcion=descripcion_ingreso,
            monto=pago.monto,
            fuente='pago_estudiante'
        ).order_by(Ingreso.fecha.desc()).first()
        if not existe_ingreso or (datetime.utcnow() - existe_ingreso.fecha).total_seconds() > 300:
            nuevo_ingreso = Ingreso(
                descripcion=descripcion_ingreso,
                monto=pago.monto,
                fuente='pago_estudiante',
                fecha=datetime.utcnow()
            )
            db.session.add(nuevo_ingreso)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Pago marcado como pagado. Ingreso registrado: C$ {pago.monto}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/pagos/<int:pago_id>/pagar', methods=['POST'])
@login_required
def marcar_como_pagado(pago_id):
    """Marcar pago como pagado (ruta alternativa)"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    return marcar_pago_pagado(pago_id)

@app.route('/admin/pagos/<int:pago_id>/eliminar', methods=['POST'])
@login_required
def eliminar_pago(pago_id):
    """Eliminar pago"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    pago = Pago.query.get_or_404(pago_id)
    
    try:
        estudiante_nombre = pago.estudiante.nombre
        db.session.delete(pago)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Pago de {estudiante_nombre} eliminado'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/pagos/limpiar-vencidos', methods=['POST'])
@login_required
def limpiar_pagos_vencidos():
    """Eliminar pagos vencidos"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        eliminados = Pago.query.filter(
            Pago.estado == 'pendiente',
            Pago.fecha_vencimiento < datetime.utcnow()
        ).delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Pagos vencidos eliminados',
            'eliminados': eliminados
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/pagos/<int:pago_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_pago(pago_id):
    """Editar pago"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    pago = Pago.query.get_or_404(pago_id)
    
    if request.method == 'GET':
        return render_template('admin/partials/editar_pago_modal.html', 
                            pago=pago, 
                            estudiantes=Estudiante.query.all())
    
    try:
        data = request.form or (request.get_json(silent=True) or {})
        monto_raw = data.get('monto')
        if monto_raw:
            pago.monto = float(monto_raw.replace(',', '.'))
        pago.estado = data.get('estado', pago.estado)
        pago.metodo_pago = data.get('metodo_pago', pago.metodo_pago)
        pago.referencia = data.get('referencia', pago.referencia)
        
        fecha_vencimiento = data.get('fecha_vencimiento')
        if fecha_vencimiento:
            pago.fecha_vencimiento = datetime.strptime(fecha_vencimiento, '%Y-%m-%d')
        
        if pago.estado == 'pagado' and not pago.fecha_pago:
            pago.fecha_pago = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Pago actualizado exitosamente'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== FINANZAS ====================
@app.route('/admin/finanzas')
@login_required
def admin_finanzas():
    """Panel de finanzas"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    total_ingresos = db.session.query(db.func.sum(Ingreso.monto)).scalar() or 0
    total_gastos = db.session.query(db.func.sum(Gasto.monto)).scalar() or 0
    balance = total_ingresos - total_gastos
    
    ingresos = Ingreso.query.order_by(Ingreso.fecha.desc()).limit(10).all()
    gastos = Gasto.query.order_by(Gasto.fecha.desc()).limit(10).all()
    
    hoy = datetime.utcnow()
    inicio_mes = hoy.replace(day=1)
    ingresos_mes = db.session.query(db.func.sum(Ingreso.monto)).filter(
        Ingreso.fecha >= inicio_mes
    ).scalar() or 0
    gastos_mes = db.session.query(db.func.sum(Gasto.monto)).filter(
        Gasto.fecha >= inicio_mes
    ).scalar() or 0
    
    return render_template('admin/finanzas.html',
                        total_ingresos=total_ingresos,
                        total_gastos=total_gastos,
                        balance=balance,
                        ingresos=ingresos,
                        gastos=gastos,
                        ingresos_mes=ingresos_mes,
                        gastos_mes=gastos_mes)

@app.route('/admin/finanzas/agregar_ingreso', methods=['POST'])
@login_required
def agregar_ingreso():
    """Agregar ingreso manual"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        descripcion = request.form['descripcion']
        monto = float(request.form['monto'])
        fuente = request.form.get('fuente', 'otros')
        
        nuevo_ingreso = Ingreso(
            descripcion=descripcion,
            monto=monto,
            fuente=fuente,
            fecha=datetime.utcnow()
        )
        
        db.session.add(nuevo_ingreso)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '✅ Ingreso registrado',
            'ingreso_id': nuevo_ingreso.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/finanzas/agregar_gasto', methods=['POST'])
@login_required
def agregar_gasto():
    """Agregar gasto manual"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        descripcion = request.form['descripcion']
        monto = float(request.form['monto'])
        categoria = request.form['categoria']
        
        nuevo_gasto = Gasto(
            descripcion=descripcion,
            monto=monto,
            categoria=categoria,
            fecha=datetime.utcnow()
        )
        
        db.session.add(nuevo_gasto)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '✅ Gasto registrado',
            'gasto_id': nuevo_gasto.id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reporte_finanzas')
@login_required
def generar_reporte_finanzas():
    """Generar reporte PDF de finanzas"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elementos = []
    estilos = getSampleStyleSheet()
    
    titulo = Paragraph("Reporte de Finanzas - Sistema de Transporte", estilos['Title'])
    elementos.append(titulo)
    
    fecha = Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilos['Normal'])
    elementos.append(fecha)
    elementos.append(Paragraph("<br/><br/>", estilos['Normal']))
    
    total_ingresos = db.session.query(db.func.sum(Ingreso.monto)).scalar() or 0
    total_gastos = db.session.query(db.func.sum(Gasto.monto)).scalar() or 0
    balance = total_ingresos - total_gastos
    
    datos_totales = [
        ['Concepto', 'Monto'],
        ['Total Ingresos', f'C$ {total_ingresos:.2f}'],
        ['Total Gastos', f'C$ {total_gastos:.2f}'],
        ['Balance General', f'C$ {balance:.2f}']
    ]
    
    tabla_totales = Table(datos_totales)
    tabla_totales.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elementos.append(tabla_totales)
    
    elementos.append(Paragraph("<br/><br/><b>Últimos Ingresos:</b>", estilos['Normal']))
    ingresos = Ingreso.query.order_by(Ingreso.fecha.desc()).limit(10).all()
    
    if ingresos:
        datos_ingresos = [['Descripción', 'Monto', 'Fecha', 'Fuente']]
        for ingreso in ingresos:
            datos_ingresos.append([
                ingreso.descripcion,
                f'C$ {ingreso.monto:.2f}',
                ingreso.fecha.strftime('%d/%m/%Y'),
                ingreso.fuente
            ])
        
        tabla_ingresos = Table(datos_ingresos)
        tabla_ingresos.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elementos.append(tabla_ingresos)
    
    doc.build(elementos)
    buffer.seek(0)
    
    return send_file(buffer,
                    as_attachment=True,
                    download_name=f'reporte_finanzas_{datetime.now().strftime("%Y%m%d")}.pdf',
                    mimetype='application/pdf')

# ==================== CONDUCTORES ====================
@app.route('/admin/conductores')
@login_required
def admin_conductores():
    """Panel de conductores"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    estado = request.args.get('estado', 'todos')
    query = Usuario.query.filter_by(rol='conductor')
    if estado == 'activos':
        query = query.filter_by(activo=True)
    elif estado == 'pendientes':
        query = query.filter_by(activo=False)
    
    conductores = query.order_by(Usuario.fecha_registro.desc()).all()
    rutas = Ruta.query.all()
    
    rutas_por_conductor = {r.conductor_id: r for r in rutas if r.conductor_id}
    vehiculos_por_conductor = {
        r.conductor_id: r.vehiculo for r in rutas if r.conductor_id and r.vehiculo
    }
    
    vehiculos_disponibles = Vehiculo.query.filter_by(activo=True).all()
    conductores_pendientes = Usuario.query.filter_by(rol='conductor', activo=False).count()
    conductores_con_rutas = len(rutas_por_conductor)
    
    return render_template('admin/conductores.html',
                        conductores=conductores,
                        rutas=rutas,
                        rutas_por_conductor=rutas_por_conductor,
                        vehiculos_por_conductor=vehiculos_por_conductor,
                        vehiculos_disponibles=vehiculos_disponibles,
                        conductores_pendientes=conductores_pendientes,
                        conductores_con_rutas=conductores_con_rutas,
                        estado_actual=estado)

@app.route('/admin/conductores/activar/<int:id>', methods=['POST'])
@login_required
def activar_conductor(id):
    """Activar/desactivar conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    
    try:
        conductor.activo = not conductor.activo
        estado = "activado" if conductor.activo else "desactivado"
        
        crear_notificacion(
            conductor.id,
            'sistema',
            f'🚍 Tu cuenta ha sido {estado} por el administrador',
            url_for('conductor_dashboard') if conductor.activo else None
        )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Conductor {estado}',
            'activo': conductor.activo
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/conductores/<int:id>/aprobar', methods=['POST'])
@login_required
def aprobar_conductor(id):
    """Aprobar conductor (activar)"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    try:
        conductor.activo = True
        crear_notificacion(
            conductor.id,
            'sistema',
            '✅ Tu cuenta de conductor ha sido aprobada',
            url_for('conductor_dashboard')
        )
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Conductor aprobado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/conductores/<int:id>/desactivar', methods=['POST'])
@login_required
def desactivar_conductor(id):
    """Desactivar conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    try:
        conductor.activo = False
        crear_notificacion(
            conductor.id,
            'sistema',
            '⚠️ Tu cuenta ha sido desactivada por el administrador'
        )
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Conductor desactivado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/conductores/<int:id>/asignar-vehiculo', methods=['POST'])
@login_required
def asignar_vehiculo_conductor(id):
    """Asignar vehículo al conductor (en su ruta actual)"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    data = request.get_json(silent=True) or request.form
    vehiculo_id = data.get('vehiculo_id')
    if not vehiculo_id:
        return jsonify({'success': False, 'error': 'Vehículo requerido'}), 400
    
    try:
        vehiculo = Vehiculo.query.get_or_404(int(vehiculo_id))
        vehiculo.conductor_id = conductor.id
        ruta = Ruta.query.filter_by(conductor_id=conductor.id).first()
        if ruta:
            ruta.vehiculo_id = int(vehiculo_id)
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Vehículo asignado al conductor'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/conductor/<int:id>/info')
@login_required
def api_conductor_info(id):
    """Información básica de conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    return jsonify({
        'success': True,
        'conductor': {
            'id': conductor.id,
            'nombre': conductor.nombre,
            'email': conductor.email,
            'telefono': conductor.telefono,
            'activo': conductor.activo
        }
    })

@app.route('/admin/conductores/<int:id>/editar', methods=['POST'])
@login_required
def editar_conductor_admin(id):
    """Editar información del conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    try:
        conductor.nombre = request.form.get('nombre', conductor.nombre)
        conductor.email = request.form.get('email', conductor.email)
        conductor.telefono = request.form.get('telefono', conductor.telefono)
        activo = request.form.get('activo')
        if activo is not None:
            conductor.activo = (activo == 'true')
        
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Conductor actualizado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/conductor/ubicacion/actualizar', methods=['POST'])
@login_required
def actualizar_ubicacion_conductor():
    """Actualizar ubicación del conductor"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    data = request.get_json(silent=True) or request.form
    lat = data.get('lat')
    lng = data.get('lng')
    if lat is None or lng is None:
        return jsonify({'success': False, 'error': 'Lat/Lng requeridos'}), 400
    
    try:
        registro = UbicacionVehiculo.query.filter_by(conductor_id=current_user.id).first()
        if registro:
            registro.lat = float(lat)
            registro.lng = float(lng)
            registro.ultima_actualizacion = datetime.utcnow()
        else:
            registro = UbicacionVehiculo(
                conductor_id=current_user.id,
                lat=float(lat),
                lng=float(lng),
                ultima_actualizacion=datetime.utcnow()
            )
            db.session.add(registro)
        
        historial = UbicacionHistorial(
            conductor_id=current_user.id,
            lat=float(lat),
            lng=float(lng),
            fecha=datetime.utcnow()
        )
        db.session.add(historial)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Ubicación actualizada'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/conductor/<int:id>/ubicacion')
@login_required
def api_conductor_ubicacion(id):
    """Obtener última ubicación de un conductor"""
    if current_user.rol == 'padre':
        hijos = Estudiante.query.filter_by(padre_id=current_user.id).all()
        conductor_ids = {hijo.ruta.conductor_id for hijo in hijos if hijo.ruta}
        if id not in conductor_ids:
            return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    ubicacion = UbicacionVehiculo.query.filter_by(conductor_id=id).first()
    if not ubicacion:
        return jsonify({'success': False, 'error': 'Sin ubicación'}), 404
    
    return jsonify({
        'success': True,
        'lat': ubicacion.lat,
        'lng': ubicacion.lng,
        'ultima_actualizacion': ubicacion.ultima_actualizacion.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/conductores/<int:id>/historial')
@login_required
def api_conductor_historial(id):
    """Historial reciente de ubicaciones de un conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    limit = int(request.args.get('limit', 200))
    puntos = UbicacionHistorial.query.filter_by(conductor_id=id).order_by(UbicacionHistorial.fecha.desc()).limit(limit).all()
    data = [{
        'lat': p.lat,
        'lng': p.lng,
        'fecha': p.fecha.strftime('%Y-%m-%d %H:%M:%S')
    } for p in reversed(puntos)]
    return jsonify({'success': True, 'puntos': data})

@app.route('/admin/conductores/asignar_ruta/<int:id>', methods=['POST'])
@login_required
def asignar_ruta_conductor(id):
    """Asignar ruta a conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    
    try:
        data = request.get_json(silent=True) or request.form
        ruta_id = int(data['ruta_id'])
        ruta = Ruta.query.get_or_404(ruta_id)
        
        if ruta.conductor_id:
            conductor_anterior = Usuario.query.get(ruta.conductor_id)
            if conductor_anterior:
                crear_notificacion(
                    conductor_anterior.id,
                    'sistema',
                    f'🚍 Has sido desasignado de la ruta: {ruta.nombre}',
                    url_for('conductor_dashboard')
                )
        
        ruta.conductor_id = conductor.id
        db.session.commit()
        
        crear_notificacion(
            conductor.id,
            'sistema',
            f'🚍 Has sido asignado a la ruta: {ruta.nombre}',
            url_for('conductor_dashboard')
        )
        
        return jsonify({
            'success': True,
            'message': f'✅ Ruta {ruta.nombre} asignada a {conductor.nombre}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PADRES ====================
@app.route('/admin/padres')
@login_required
def admin_padres():
    """Panel de padres con sus hijos"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    estado = request.args.get('estado', 'todos')
    query = Usuario.query.filter_by(rol='padre')
    if estado == 'activos':
        query = query.filter_by(activo=True)
    elif estado == 'pendientes':
        query = query.filter_by(activo=False)
    
    padres = query.all()
    padres_activos = [p for p in padres if p.activo]
    padres_pendientes = Usuario.query.filter_by(rol='padre', activo=False).all()
    
    datos_padres = []
    for padre in padres_activos:
        hijos = Estudiante.query.filter_by(padre_id=padre.id).all()
        
        hijos_info = []
        for hijo in hijos:
            vehiculo_info = "No asignado"
            if hijo.ruta and hijo.ruta.vehiculo:
                vehiculo_info = f"{hijo.ruta.vehiculo.modelo} - Placa: {hijo.ruta.vehiculo.placa}"
            
            ultimo_pago = Pago.query.filter_by(
                estudiante_id=hijo.id
            ).order_by(Pago.fecha_vencimiento.desc()).first()
            
            dias_restantes = 0
            if ultimo_pago and ultimo_pago.fecha_vencimiento:
                dias_restantes = (ultimo_pago.fecha_vencimiento.date() - datetime.utcnow().date()).days
            
            hijos_info.append({
                'nombre': hijo.nombre,
                'grado': hijo.grado,
                'vehiculo': vehiculo_info,
                'dias_restantes': max(0, dias_restantes),
                'estado_pago': ultimo_pago.estado if ultimo_pago else 'sin_pago'
            })
        
        datos_padres.append({
            'padre': padre,
            'hijos': hijos_info,
            'total_hijos': len(hijos)
        })
    
    return render_template('admin/padres.html',
                        datos_padres=datos_padres,
                        padres_pendientes=padres_pendientes,
                        estado_actual=estado)

# ==================== PANEL PADRE ====================
@app.route('/padre/dashboard')
@login_required
def padre_dashboard():
    """Dashboard del padre"""
    if current_user.rol != 'padre':
        flash('⚠️ No tienes permisos de padre', 'error')
        return redirect(url_for('index'))
    
    hijos = Estudiante.query.filter_by(padre_id=current_user.id).all()
    
    pagos_pendientes = []
    for hijo in hijos:
        pagos_hijo = Pago.query.filter_by(
            estudiante_id=hijo.id,
            estado='pendiente'
        ).order_by(Pago.fecha_vencimiento.asc()).all()
        
        for pago in pagos_hijo:
            pagos_pendientes.append({
                'pago': pago,
                'estudiante': hijo
            })
    
    asistencias_recientes = []
    for hijo in hijos:
        asistencia = Asistencia.query.filter_by(
            estudiante_id=hijo.id
        ).order_by(Asistencia.fecha.desc()).first()
        
        if asistencia:
            asistencias_recientes.append({
                'estudiante': hijo,
                'asistencia': asistencia
            })
    
    notificaciones = Notificacion.query.filter_by(
        usuario_id=current_user.id
    ).order_by(Notificacion.fecha.desc()).limit(10).all()
    
    return render_template('padres/dashboard.html',
                        hijos=hijos,
                        pagos=pagos_pendientes,
                        asistencias=asistencias_recientes,
                        notificaciones=notificaciones)

@app.route('/padre/ruta/<int:estudiante_id>')
@login_required
def padre_ruta(estudiante_id):
    """Vista de ruta en tiempo real para padres"""
    if current_user.rol != 'padre':
        return redirect(url_for('index'))
    
    estudiante = Estudiante.query.get_or_404(estudiante_id)
    if estudiante.padre_id != current_user.id:
        flash('⚠️ No tienes permisos para ver esta ruta', 'error')
        return redirect(url_for('padre_dashboard'))
    
    ruta = estudiante.ruta
    conductor = ruta.conductor_rel if ruta else None
    
    ubicacion_vehiculo = None
    if conductor:
        ubicacion_vehiculo = UbicacionVehiculo.query.filter_by(conductor_id=conductor.id).first()
    
    asistencias_recientes = Asistencia.query.filter_by(estudiante_id=estudiante.id).order_by(Asistencia.fecha.desc()).limit(5).all()
    
    return render_template('padres/ruta.html',
                        estudiante=estudiante,
                        ruta=ruta,
                        conductor=conductor,
                        ubicacion_vehiculo=ubicacion_vehiculo,
                        asistencias_recientes=asistencias_recientes,
                        paradas=[])

@app.route('/admin/padres/<int:id>/activar', methods=['POST'])
@login_required
def activar_padre(id):
    """Activar cuenta de padre"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    padre = Usuario.query.get_or_404(id)
    try:
        padre.activo = True
        crear_notificacion(
            padre.id,
            'sistema',
            '✅ Tu cuenta de padre ha sido aprobada',
            url_for('padre_dashboard')
        )
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Padre activado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PANEL CONDUCTOR ====================
@app.route('/conductor/dashboard')
@login_required
def conductor_dashboard():
    """Dashboard del conductor"""
    if current_user.rol != 'conductor':
        flash('⚠️ No tienes permisos de conductor', 'error')
        return redirect(url_for('index'))
    
    ruta = Ruta.query.filter_by(conductor_id=current_user.id).first()
    
    if not ruta:
        flash('⚠️ No tienes una ruta asignada', 'warning')
        return render_template('conductor/dashboard.html',
                            ruta=None,
                            estudiantes=[],
                            asistencia_map={},
                            hoy=datetime.utcnow().date())
    
    estudiantes = Estudiante.query.filter_by(ruta_id=ruta.id).all()
    
    hoy = datetime.utcnow().date()
    asistencias_hoy = Asistencia.query.filter(
        Asistencia.fecha == hoy,
        Asistencia.estudiante_id.in_([e.id for e in estudiantes])
    ).all()
    
    asistencia_map = {a.estudiante_id: a for a in asistencias_hoy}
    
    asistencia_manual = AsistenciaManual.query.filter_by(
        conductor_id=current_user.id,
        fecha=hoy
    ).first()
    
    return render_template('conductor/dashboard.html',
                        ruta=ruta,
                        estudiantes=estudiantes,
                        asistencia_map=asistencia_map,
                        hoy=hoy,
                        asistencia_manual=asistencia_manual)

@app.route('/conductor/registrar_asistencia', methods=['POST'])
@login_required
def registrar_asistencia():
    """Registrar asistencia desde el conductor"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        data = request.get_json(silent=True) or request.form
        estudiante_id = int(data['estudiante_id'])
        estado = data.get('estado', 'presente')
        observaciones = data.get('observaciones', '')
        
        conductor_ruta = Ruta.query.filter_by(conductor_id=current_user.id).first()
        estudiante = Estudiante.query.get(estudiante_id)
        
        if not conductor_ruta or not estudiante or estudiante.ruta_id != conductor_ruta.id:
            return jsonify({'success': False, 'error': 'Estudiante no en tu ruta'})
        
        hoy = datetime.utcnow().date()
        asistencia_existente = Asistencia.query.filter_by(
            estudiante_id=estudiante_id,
            fecha=hoy
        ).first()
        
        if asistencia_existente:
            return jsonify({'success': False, 'error': 'Asistencia ya registrada hoy'}), 400
        else:
            nueva_asistencia = Asistencia(
                estudiante_id=estudiante_id,
                fecha=hoy,
                hora=datetime.utcnow().time(),
                estado=estado,
                observaciones=observaciones,
                conductor_id=current_user.id
            )
            db.session.add(nueva_asistencia)
        
        if estudiante.padre_id:
            estado_texto = {
                'presente': '✅ presente',
                'ausente': '❌ ausente',
                'tardanza': '⚠️ con tardanza'
            }.get(estado, estado)
            
            crear_notificacion(
                estudiante.padre_id,
                'asistencia',
                f'📝 {estudiante.nombre} marcado como {estado_texto} hoy',
                url_for('padre_dashboard')
            )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Asistencia registrada: {estudiante.nombre} - {estado}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/conductor/asistencia/registrar', methods=['POST'])
@login_required
def registrar_asistencia_alias():
    """Alias para compatibilidad con frontend"""
    return registrar_asistencia()

@app.route('/conductor/asistencia_manual', methods=['POST'])
@login_required
def guardar_asistencia_manual():
    """Guardar resumen manual de asistencia del conductor"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    data = request.get_json(silent=True) or request.form
    presentes = int(data.get('presentes', 0))
    ausentes = int(data.get('ausentes', 0))
    hoy = datetime.utcnow().date()
    
    registro = AsistenciaManual.query.filter_by(
        conductor_id=current_user.id,
        fecha=hoy
    ).first()
    
    if registro:
        registro.presentes = presentes
        registro.ausentes = ausentes
    else:
        registro = AsistenciaManual(
            conductor_id=current_user.id,
            fecha=hoy,
            presentes=presentes,
            ausentes=ausentes
        )
        db.session.add(registro)
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/conductor/notificar_retraso', methods=['POST'])
@login_required
def notificar_retraso():
    """Notificar retraso a padres"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        motivo = request.form['motivo']
        tiempo_estimado = request.form.get('tiempo_estimado', '15-20 minutos')
        
        ruta = Ruta.query.filter_by(conductor_id=current_user.id).first()
        if not ruta:
            return jsonify({'success': False, 'error': 'No tienes ruta asignada'})
        
        estudiantes = Estudiante.query.filter_by(ruta_id=ruta.id).all()
        
        notificaciones_enviadas = 0
        for estudiante in estudiantes:
            if estudiante.padre_id:
                crear_notificacion(
                    estudiante.padre_id,
                    'retraso',
                    f'⏰ Retraso en la ruta: {motivo}. Tiempo estimado: {tiempo_estimado}',
                    url_for('padre_dashboard')
                )
                notificaciones_enviadas += 1
        
        admin = Usuario.query.filter_by(rol='admin').first()
        if admin:
            crear_notificacion(
                admin.id,
                'retraso',
                f'🚍 Conductor {current_user.nombre} reporta retraso: {motivo}',
                url_for('admin_dashboard')
            )
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ Retraso notificado a {notificaciones_enviadas} padres'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/conductor/reportar', methods=['POST'])
@login_required
def conductor_reportar():
    """Enviar reportes desde conductor a padres/admin"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    tipo = request.form.get('tipo', 'problema')
    mensaje = request.form.get('mensaje', '').strip()
    
    ruta = Ruta.query.filter_by(conductor_id=current_user.id).first()
    if not ruta:
        return jsonify({'success': False, 'error': 'No tienes ruta asignada'}), 400
    
    estudiantes = Estudiante.query.filter_by(ruta_id=ruta.id).all()
    padres_ids = {e.padre_id for e in estudiantes if e.padre_id}
    
    try:
        mensajes_defecto = {
            'retraso': 'Lamentamos informarles estimados padres de que la unidad tendrá un pequeño retraso en llegar.',
            'llegada': 'Estimado padre, la unidad ha llegado a su destino y su hijo se encuentra ya en su centro de estudio.',
            'problema': 'Reporte de problema por parte del conductor.'
        }
        mensaje_final = mensaje or mensajes_defecto.get(tipo, 'Notificación del conductor.')
        
        if tipo == 'problema':
            admin = Usuario.query.filter_by(rol='admin').first()
            if admin:
                crear_notificacion(
                    admin.id,
                    'problema',
                    f'🚍 {current_user.nombre}: {mensaje_final}',
                    url_for('admin_dashboard')
                )
        else:
            for padre_id in padres_ids:
                crear_notificacion(
                    padre_id,
                    tipo,
                    f'🚍 {mensaje_final}',
                    url_for('padre_dashboard')
                )
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Reporte enviado correctamente'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RUTAS Y VEHÍCULOS ====================
@app.route('/admin/rutas')
@login_required
def admin_rutas():
    """Gestión de rutas"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    rutas = Ruta.query.all()
    conductores = Usuario.query.filter_by(rol='conductor', activo=True).all()
    vehiculos = Vehiculo.query.filter_by(activo=True).all()
    
    return render_template('admin/rutas.html',
                        rutas=rutas,
                        conductores=conductores,
                        vehiculos=vehiculos)

@app.route('/admin/rutas/agregar', methods=['POST'])
@login_required
def agregar_ruta():
    """Agregar nueva ruta"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        nombre = request.form['nombre']
        descripcion = request.form.get('descripcion', '')
        hora_inicio = request.form['hora_inicio']
        hora_fin = request.form['hora_fin']
        vehiculo_id = int(request.form['vehiculo_id']) if request.form['vehiculo_id'] else None
        conductor_id = int(request.form['conductor_id']) if request.form.get('conductor_id') else None
        
        existente = Ruta.query.filter_by(
            nombre=nombre,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin
        ).first()
        if existente:
            return jsonify({'success': False, 'error': 'Ruta ya existe con el mismo nombre y horario'}), 400

        nueva_ruta = Ruta(
            nombre=nombre,
            descripcion=descripcion,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin,
            vehiculo_id=vehiculo_id,
            conductor_id=conductor_id,
            activa=True
        )
        
        db.session.add(nueva_ruta)
        db.session.commit()
        
        if conductor_id:
            crear_notificacion(
                conductor_id,
                'sistema',
                f'🚍 Has sido asignado a la ruta: {nombre}',
                url_for('conductor_dashboard')
            )
        
        return jsonify({
            'success': True,
            'message': '✅ Ruta agregada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/rutas/<int:ruta_id>/detalle')
@login_required
def detalle_ruta(ruta_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ruta = Ruta.query.get_or_404(ruta_id)
    return jsonify({
        'success': True,
        'ruta': {
            'id': ruta.id,
            'nombre': ruta.nombre,
            'descripcion': ruta.descripcion or '',
            'hora_inicio': ruta.hora_inicio,
            'hora_fin': ruta.hora_fin,
            'activa': ruta.activa,
            'conductor_id': ruta.conductor_id,
            'vehiculo_id': ruta.vehiculo_id
        }
    })

@app.route('/admin/rutas/<int:ruta_id>/estudiantes')
@login_required
def estudiantes_ruta(ruta_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    estudiantes = Estudiante.query.filter_by(ruta_id=ruta_id).all()
    data = [{'nombre': e.nombre, 'grado': e.grado, 'escuela': e.escuela or ''} for e in estudiantes]
    return jsonify({'success': True, 'estudiantes': data})

@app.route('/admin/rutas/<int:ruta_id>/toggle', methods=['POST'])
@login_required
def toggle_ruta(ruta_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ruta = Ruta.query.get_or_404(ruta_id)
    ruta.activa = not ruta.activa
    db.session.commit()
    return jsonify({'success': True, 'activa': ruta.activa})

@app.route('/admin/rutas/<int:ruta_id>/editar', methods=['POST'])
@login_required
def editar_ruta(ruta_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ruta = Ruta.query.get_or_404(ruta_id)
    try:
        ruta.nombre = request.form.get('nombre', ruta.nombre)
        ruta.descripcion = request.form.get('descripcion', ruta.descripcion)
        ruta.hora_inicio = request.form.get('hora_inicio', ruta.hora_inicio)
        ruta.hora_fin = request.form.get('hora_fin', ruta.hora_fin)
        conductor_id = request.form.get('conductor_id') or None
        vehiculo_id = request.form.get('vehiculo_id') or None
        ruta.conductor_id = int(conductor_id) if conductor_id else None
        ruta.vehiculo_id = int(vehiculo_id) if vehiculo_id else None
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/conductor/ruta/estado', methods=['POST'])
@login_required
def actualizar_estado_ruta():
    """Actualizar estado de la ruta del conductor"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    data = request.get_json(silent=True) or request.form
    estado = data.get('estado')
    if estado not in ['iniciada', 'pausada', 'finalizada']:
        return jsonify({'success': False, 'error': 'Estado inválido'}), 400
    ruta = Ruta.query.filter_by(conductor_id=current_user.id).first()
    if not ruta:
        return jsonify({'success': False, 'error': 'No tienes ruta asignada'}), 400

    hoy = datetime.utcnow().date()

    if estado == 'iniciada':
        Asistencia.query.filter(
            Asistencia.fecha == hoy,
            Asistencia.conductor_id == current_user.id
        ).delete(synchronize_session=False)
        db.session.commit()

    if estado == 'finalizada':
        admin = Usuario.query.filter_by(rol='admin').first()
        if admin:
            link = url_for('admin_reporte_asistencia', conductor_id=current_user.id, fecha=hoy.strftime('%Y-%m-%d'))
            crear_notificacion(
                admin.id,
                'asistencia',
                f'🚌 Ruta finalizada por {current_user.nombre}. Reporte disponible para descargar.',
                link
            )
        db.session.commit()

    session['estado_ruta'] = estado
    return jsonify({'success': True})

# ==================== VEHÍCULOS ====================
@app.route('/admin/vehiculos')
@login_required
def admin_vehiculos():
    """Panel de vehículos"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    vehiculos = Vehiculo.query.all()
    conductores = Usuario.query.filter_by(rol='conductor', activo=True).all()
    return render_template('admin/vehiculos.html', vehiculos=vehiculos, conductores=conductores)

@app.route('/admin/vehiculos/agregar', methods=['POST'])
@login_required
def agregar_vehiculo():
    """Agregar vehículo"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        placa = request.form['placa'].upper()
        marca = request.form['marca']
        modelo = request.form['modelo']
        año = int(request.form['año'])
        capacidad = int(request.form['capacidad'])
        estado = request.form.get('estado', 'activo')
        conductor_id = request.form.get('conductor_id') or None
        kilometraje = request.form.get('kilometraje') or None
        observaciones = request.form.get('observaciones', '')
        
        vehiculo = Vehiculo(
            placa=placa,
            marca=marca,
            modelo=modelo,
            año=año,
            capacidad=capacidad,
            estado=estado,
            activo=(estado != 'inactivo'),
            conductor_id=int(conductor_id) if conductor_id else None,
            kilometraje=int(kilometraje) if kilometraje else None,
            observaciones=observaciones
        )
        
        db.session.add(vehiculo)
        db.session.commit()
        flash('✅ Vehículo agregado correctamente', 'success')
        return redirect(url_for('admin_vehiculos'))
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin_vehiculos'))

@app.route('/admin/vehiculos/<int:vehiculo_id>/asignar-conductor', methods=['POST'])
@login_required
def asignar_conductor_vehiculo(vehiculo_id):
    """Asignar conductor a vehículo"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    data = request.get_json(silent=True) or request.form
    conductor_id = data.get('conductor_id')
    if not conductor_id:
        return jsonify({'success': False, 'error': 'Conductor requerido'}), 400
    
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    try:
        vehiculo.conductor_id = int(conductor_id)
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Conductor asignado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/vehiculos/<int:vehiculo_id>/cambiar-estado', methods=['POST'])
@login_required
def cambiar_estado_vehiculo(vehiculo_id):
    """Cambiar estado de vehículo"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    data = request.get_json(silent=True) or request.form
    estado = data.get('estado')
    if estado not in ['activo', 'mantenimiento', 'inactivo']:
        return jsonify({'success': False, 'error': 'Estado inválido'}), 400
    
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    try:
        vehiculo.estado = estado
        vehiculo.activo = (estado != 'inactivo')
        if estado == 'mantenimiento':
            vehiculo.ultimo_mantenimiento = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'message': '✅ Estado actualizado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/vehiculos/<int:vehiculo_id>/detalle')
@login_required
def detalle_vehiculo(vehiculo_id):
    """Detalle básico de vehículo"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    return jsonify({
        'success': True,
        'vehiculo': {
            'placa': vehiculo.placa,
            'marca': vehiculo.marca,
            'modelo': vehiculo.modelo,
            'año': vehiculo.año,
            'capacidad': vehiculo.capacidad,
            'estado': vehiculo.estado,
            'kilometraje': vehiculo.kilometraje or 0
        }
    })

@app.route('/api/conductores/ubicaciones')
@login_required
def api_conductores_ubicaciones():
    """Ubicación en tiempo real de conductores (admin)"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    ubicaciones = UbicacionVehiculo.query.join(Usuario, UbicacionVehiculo.conductor_id == Usuario.id).all()
    rutas = Ruta.query.all()
    rutas_por_conductor = {r.conductor_id: r for r in rutas if r.conductor_id}
    data = []
    for u in ubicaciones:
        data.append({
            'conductor_id': u.conductor_id,
            'nombre': u.conductor.nombre if u.conductor else 'Conductor',
            'activo': bool(u.conductor.activo) if u.conductor else False,
            'ruta': rutas_por_conductor.get(u.conductor_id).nombre if rutas_por_conductor.get(u.conductor_id) else '',
            'lat': u.lat,
            'lng': u.lng,
            'ultima_actualizacion': u.ultima_actualizacion.strftime('%d/%m/%Y %H:%M:%S')
        })
    return jsonify({'success': True, 'ubicaciones': data})

@app.route('/admin/vehiculos/<int:vehiculo_id>/editar', methods=['POST'])
@login_required
def editar_vehiculo(vehiculo_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    try:
        vehiculo.placa = request.form.get('placa', vehiculo.placa).upper()
        vehiculo.marca = request.form.get('marca', vehiculo.marca)
        vehiculo.modelo = request.form.get('modelo', vehiculo.modelo)
        vehiculo.año = int(request.form.get('año', vehiculo.año))
        vehiculo.capacidad = int(request.form.get('capacidad', vehiculo.capacidad))
        vehiculo.estado = request.form.get('estado', vehiculo.estado)
        vehiculo.kilometraje = int(request.form.get('kilometraje')) if request.form.get('kilometraje') else vehiculo.kilometraje
        vehiculo.activo = (vehiculo.estado != 'inactivo')
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/vehiculos/<int:vehiculo_id>/eliminar', methods=['POST'])
@login_required
def eliminar_vehiculo(vehiculo_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    try:
        Ruta.query.filter_by(vehiculo_id=vehiculo.id).update({'vehiculo_id': None})
        db.session.delete(vehiculo)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/rutas/<int:ruta_id>/eliminar', methods=['POST'])
@login_required
def eliminar_ruta(ruta_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ruta = Ruta.query.get_or_404(ruta_id)
    try:
        Estudiante.query.filter_by(ruta_id=ruta.id).update({'ruta_id': None})
        db.session.delete(ruta)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/finanzas/ingresos/<int:ingreso_id>/eliminar', methods=['POST'])
@login_required
def eliminar_ingreso(ingreso_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ingreso = Ingreso.query.get_or_404(ingreso_id)
    try:
        db.session.delete(ingreso)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/finanzas/gastos/<int:gasto_id>/eliminar', methods=['POST'])
@login_required
def eliminar_gasto(gasto_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    gasto = Gasto.query.get_or_404(gasto_id)
    try:
        db.session.delete(gasto)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== MODO OSCURO ====================
@app.route('/toggle_modo_oscuro', methods=['POST', 'GET'])
def toggle_modo_oscuro():
    """Alternar modo oscuro en sesión"""
    session['modo_oscuro'] = not session.get('modo_oscuro', False)
    if request.method == 'GET':
        next_url = request.args.get('next') or request.referrer or url_for('index')
        return redirect(next_url)
    return jsonify({'modo_oscuro': session['modo_oscuro']})

# ==================== NOTIFICACIONES ====================
@app.route('/api/notificaciones/<int:usuario_id>')
@login_required
def obtener_notificaciones(usuario_id):
    """Obtener notificaciones para un usuario"""
    if current_user.id != usuario_id and current_user.rol != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    notificaciones = Notificacion.query.filter_by(
        usuario_id=usuario_id
    ).order_by(Notificacion.fecha.desc()).limit(20).all()
    
    resultado = []
    for notif in notificaciones:
        resultado.append({
            'id': notif.id,
            'tipo': notif.tipo,
            'mensaje': notif.mensaje,
            'fecha': notif.fecha.strftime('%d/%m/%Y %H:%M'),
            'link': notif.link,
            'leida': notif.leida
        })
    
    return jsonify(resultado)

@app.route('/api/notificaciones/marcar_leida/<int:notif_id>', methods=['POST'])
@login_required
def marcar_notificacion_leida(notif_id):
    """Marcar notificación como leída"""
    notificacion = Notificacion.query.get_or_404(notif_id)
    
    if notificacion.usuario_id != current_user.id and current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    notificacion.leida = True
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/notificaciones/marcar_todas_leidas', methods=['POST'])
@login_required
def marcar_todas_leidas():
    """Marcar todas las notificaciones como leídas"""
    Notificacion.query.filter_by(usuario_id=current_user.id, leida=False).update({'leida': True})
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/notificaciones/count/<int:usuario_id>')
@login_required
def contar_notificaciones(usuario_id):
    """Contar notificaciones no leídas"""
    if current_user.id != usuario_id and current_user.rol != 'admin':
        return jsonify({'error': 'No autorizado'}), 403
    
    count = Notificacion.query.filter_by(usuario_id=usuario_id, leida=False).count()
    return jsonify({'count': count})

@app.route('/notificaciones')
@login_required
def notificaciones():
    """Buzón de notificaciones"""
    notificaciones = Notificacion.query.filter_by(usuario_id=current_user.id).order_by(Notificacion.fecha.desc()).all()
    return render_template('notificaciones.html', notificaciones=notificaciones)

@app.route('/api/pagos/<int:pago_id>/marcar_visto', methods=['POST'])
@login_required
def marcar_pago_visto(pago_id):
    """Marcar pago como visto por el padre"""
    pago = Pago.query.get_or_404(pago_id)
    if current_user.rol != 'padre':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    estudiante = Estudiante.query.get(pago.estudiante_id)
    if not estudiante or estudiante.padre_id != current_user.id:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    pago.visto_padre = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/contactar_admin', methods=['POST'])
@login_required
def contactar_admin():
    """Enviar mensaje al administrador (vía notificación interna)"""
    asunto = request.form.get('asunto', 'consulta')
    mensaje = request.form.get('mensaje', '')
    prioridad = request.form.get('prioridad', 'media')
    
    admin = Usuario.query.filter_by(rol='admin').first()
    if not admin:
        return jsonify({'success': False, 'error': 'Admin no encontrado'}), 404
    
    texto = f'📩 {current_user.nombre} ({current_user.email}) - {asunto} [{prioridad}]: {mensaje}'
    crear_notificacion(admin.id, 'sistema', texto, url_for('admin_dashboard'))
    
    ticket = TicketSoporte(
        remitente_id=current_user.id,
        remitente_rol=current_user.rol,
        mensaje=f'[{asunto} | {prioridad}] {mensaje}',
        estado='abierto'
    )
    db.session.add(ticket)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/soporte')
@login_required
def admin_soporte():
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    tickets = TicketSoporte.query.order_by(TicketSoporte.fecha.desc()).all()
    conductores = Usuario.query.filter_by(rol='conductor', activo=True).all()
    return render_template('admin/soporte.html', tickets=tickets, conductores=conductores)

@app.route('/admin/soporte/<int:ticket_id>/responder', methods=['POST'])
@login_required
def responder_ticket(ticket_id):
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ticket = TicketSoporte.query.get_or_404(ticket_id)
    respuesta = request.form.get('respuesta', '').strip()
    conductor_id = request.form.get('conductor_id') or None
    
    try:
        ticket.respuesta = respuesta
        ticket.respondido_por_id = current_user.id
        ticket.respondido_en = datetime.utcnow()
        ticket.estado = 'respondido'
        if conductor_id:
            ticket.conductor_id = int(conductor_id)
        
        # Notificar remitente
        crear_notificacion(
            ticket.remitente_id,
            'sistema',
            f'📩 Respuesta de soporte: {respuesta}',
            url_for('padre_dashboard')
        )
        
        # Notificar conductor si aplica
        if ticket.conductor_id:
            crear_notificacion(
                ticket.conductor_id,
                'sistema',
                f'📩 Soporte: {respuesta}',
                url_for('conductor_dashboard')
            )
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/conductor/soporte')
@login_required
def conductor_soporte():
    if current_user.rol != 'conductor':
        return redirect(url_for('index'))
    tickets = TicketSoporte.query.filter_by(conductor_id=current_user.id).order_by(TicketSoporte.fecha.desc()).all()
    return render_template('conductor/soporte.html', tickets=tickets)

@app.route('/conductor/soporte/<int:ticket_id>/responder', methods=['POST'])
@login_required
def conductor_responder_ticket(ticket_id):
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    ticket = TicketSoporte.query.get_or_404(ticket_id)
    if ticket.conductor_id != current_user.id:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    respuesta = request.form.get('respuesta', '').strip()
    try:
        ticket.respuesta = respuesta
        ticket.respondido_por_id = current_user.id
        ticket.respondido_en = datetime.utcnow()
        ticket.estado = 'respondido'
        
        # Notificar padre y admin
        crear_notificacion(
            ticket.remitente_id,
            'sistema',
            f'📩 Respuesta del conductor: {respuesta}',
            url_for('padre_dashboard')
        )
        admin = Usuario.query.filter_by(rol='admin').first()
        if admin:
            crear_notificacion(
                admin.id,
                'sistema',
                f'📩 Respuesta del conductor {current_user.nombre}: {respuesta}',
                url_for('admin_soporte')
            )
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== ASISTENCIAS ====================
@app.route('/admin/asistencias')
@login_required
def admin_asistencias():
    """Panel de asistencias"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    fecha_str = request.args.get('fecha', datetime.utcnow().strftime('%Y-%m-%d'))
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    
    asistencias = Asistencia.query.filter_by(fecha=fecha).all()
    asistencias_manuales = AsistenciaManual.query.filter_by(fecha=fecha).all()
    estudiantes = Estudiante.query.all()

    conductores_map = {}
    for a in asistencias:
        if not a.conductor:
            continue
        cid = a.conductor.id
        if cid not in conductores_map:
            conductores_map[cid] = {
                'id': cid,
                'nombre': a.conductor.nombre,
                'presentes': 0,
                'ausentes': 0,
                'tardanzas': 0
            }
        if a.estado == 'presente':
            conductores_map[cid]['presentes'] += 1
        elif a.estado == 'ausente':
            conductores_map[cid]['ausentes'] += 1
        elif a.estado == 'tardanza':
            conductores_map[cid]['tardanzas'] += 1
    
    return render_template('admin/asistencias.html',
                        asistencias=asistencias,
                        asistencias_manuales=asistencias_manuales,
                        estudiantes=estudiantes,
                        conductores_reportes=list(conductores_map.values()),
                        fecha=fecha)

@app.route('/admin/asistencias/reporte')
@login_required
def admin_reporte_asistencia():
    """Generar reporte PDF de asistencias por conductor y fecha"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    conductor_id = request.args.get('conductor_id')
    fecha_str = request.args.get('fecha', datetime.utcnow().strftime('%Y-%m-%d'))
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

    if not conductor_id or not conductor_id.isdigit():
        flash('Conductor inválido', 'error')
        return redirect(url_for('admin_asistencias'))

    conductor = Usuario.query.get(int(conductor_id))
    if not conductor:
        flash('Conductor no encontrado', 'error')
        return redirect(url_for('admin_asistencias'))

    asistencias = Asistencia.query.filter_by(
        fecha=fecha,
        conductor_id=conductor.id
    ).all()

    presentes = sum(1 for a in asistencias if a.estado == 'presente')
    ausentes = sum(1 for a in asistencias if a.estado == 'ausente')
    tardanzas = sum(1 for a in asistencias if a.estado == 'tardanza')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph(f'Reporte de Asistencia - {conductor.nombre}', styles['Title'])
    subtitle = Paragraph(f'Fecha: {fecha.strftime("%d/%m/%Y")}', styles['Normal'])
    resumen = Paragraph(
        f'Resumen: Presentes {presentes} | Ausentes {ausentes} | Tardanzas {tardanzas}',
        styles['Normal']
    )
    elements.extend([title, subtitle, resumen])

    data = [['Estudiante', 'Estado', 'Hora', 'Observaciones']]
    for a in asistencias:
        hora = a.hora.strftime('%H:%M') if a.hora else '-'
        data.append([
            a.estudiante.nombre,
            a.estado,
            hora,
            a.observaciones or ''
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (1,1), (-1,-1), 'LEFT')
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    filename = f'reporte_asistencia_{conductor.nombre}_{fecha.strftime("%Y%m%d")}.pdf'
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def error_servidor(e):
    return render_template('500.html'), 500

# ==================== INICIALIZACIÓN ====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not Usuario.query.filter_by(email='admin@camley.com').first():
            admin = Usuario(
                nombre='Administrador',
                email='admin@camley.com',
                password='admin123',
                rol='admin',
                activo=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Usuario admin creado: admin@camley.com / admin123")
        
        if not Usuario.query.filter_by(email='padre@camley.com').first():
            padre = Usuario(
                nombre='Padre de Prueba',
                email='padre@camley.com',
                password='padre123',
                rol='padre',
                activo=True
            )
            db.session.add(padre)
            db.session.commit()
            print("✅ Usuario padre creado: padre@camley.com / padre123")
        
        if not Usuario.query.filter_by(email='conductor@camley.com').first():
            conductor = Usuario(
                nombre='Conductor de Prueba',
                email='conductor@camley.com',
                password='conductor123',
                rol='conductor',
                activo=True
            )
            db.session.add(conductor)
            db.session.commit()
            print("✅ Usuario conductor creado: conductor@camley.com / conductor123")
    
    app.run(debug=True, port=5000)
