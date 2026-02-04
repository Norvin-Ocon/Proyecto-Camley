from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from database import app, db, Usuario, Estudiante, Ruta, Pago, Gasto, Ingreso, Vehiculo, Notificacion, Asistencia
from datetime import datetime, timedelta
import json
import os

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
        fecha=datetime.utcnow()
    )
    if link:
        notif.link = link
    db.session.add(notif)
    db.session.commit()
    return notif

def calcular_vencimiento(meses=1):
    """Calcular fecha de vencimiento basada en meses"""
    return datetime.utcnow() + timedelta(days=30*meses)

# ==================== RUTAS PRINCIPALES ====================
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if current_user.is_authenticated:
        if current_user.rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.rol == 'padre':
            return redirect(url_for('padre_dashboard'))
        elif current_user.rol == 'conductor':
            return redirect(url_for('conductor_dashboard'))
    
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
        try:
            nombre = request.form['nombre']
            email = request.form['email']
            password = request.form['password']
            telefono = request.form.get('telefono', '')
            direccion = request.form.get('direccion', '')
            rol = request.form['rol']
            
            # Verificar si el email ya existe
            if Usuario.query.filter_by(email=email).first():
                flash('❌ Este email ya está registrado', 'error')
                return redirect(url_for('registro'))
            
            # Crear nuevo usuario
            nuevo_usuario = Usuario(
                nombre=nombre,
                email=email,
                password=password,
                telefono=telefono,
                direccion=direccion,
                rol=rol,
                activo=True if rol != 'conductor' else False
            )
            
            db.session.add(nuevo_usuario)
            db.session.commit()
            
            # Notificar al admin si es conductor
            if rol == 'conductor':
                admin = Usuario.query.filter_by(rol='admin').first()
                if admin:
                    crear_notificacion(
                        admin.id,
                        'sistema',
                        f'🚍 Nuevo conductor registrado: {nombre}'
                    )
                flash('✅ Registro exitoso. Espera aprobación del administrador.', 'success')
            else:
                flash('✅ Registro exitoso. Ya puedes iniciar sesión.', 'success')
            
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f'❌ Error en el registro: {str(e)}', 'error')
    
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
    
    # Estadísticas
    total_estudiantes = Estudiante.query.count()
    total_pagos_pendientes = Pago.query.filter_by(estado='pendiente').count()
    total_conductores = Usuario.query.filter_by(rol='conductor', activo=True).count()
    total_vehiculos = Vehiculo.query.count()
    total_padres = Usuario.query.filter_by(rol='padre', activo=True).count()
    
    # Últimos pagos
    ultimos_pagos = Pago.query.order_by(Pago.fecha_emision.desc()).limit(5).all()
    
    # Conductores pendientes
    conductores_pendientes = Usuario.query.filter_by(rol='conductor', activo=False).count()
    
    return render_template('admin/dashboard.html',
                        estudiantes=total_estudiantes,
                        pagos_pendientes=total_pagos_pendientes,
                        conductores=total_conductores,
                        vehiculos=total_vehiculos,
                        padres=total_padres,
                        ultimos_pagos=ultimos_pagos,
                        conductores_pendientes=conductores_pendientes,
                        now=datetime.utcnow())

@app.route('/admin/estudiantes')
@login_required
def admin_estudiantes():
    """Gestión de estudiantes"""
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
        flash('⚠️ No tienes permisos', 'error')
        return redirect(url_for('index'))
    
    try:
        nombre = request.form['nombre']
        edad = int(request.form['edad'])
        grado = request.form['grado']
        escuela = request.form.get('escuela', '')
        padre_id = request.form.get('padre_id')
        ruta_id = request.form.get('ruta_id')
        
        nuevo_estudiante = Estudiante(
            nombre=nombre,
            edad=edad,
            grado=grado,
            escuela=escuela,
            padre_id=int(padre_id) if padre_id else None,
            ruta_id=int(ruta_id) if ruta_id else None,
            fecha_inscripcion=datetime.utcnow()
        )
        
        db.session.add(nuevo_estudiante)
        db.session.commit()
        
        # Crear primer pago
        vencimiento = calcular_vencimiento(1)
        nuevo_pago = Pago(
            estudiante_id=nuevo_estudiante.id,
            monto=50.00,
            fecha_vencimiento=vencimiento,
            estado='pendiente',
            meses_cubiertos=1
        )
        db.session.add(nuevo_pago)
        
        # Notificar al padre si tiene
        if padre_id:
            padre = Usuario.query.get(padre_id)
            if padre:
                crear_notificacion(
                    padre.id,
                    'estudiante',
                    f'📚 {nombre} ha sido inscrito(a). Primer pago vence {vencimiento.strftime("%d/%m/%Y")}'
                )
        
        db.session.commit()
        
        flash('✅ Estudiante agregado exitosamente', 'success')
        return redirect(url_for('admin_estudiantes'))
        
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin_estudiantes'))

@app.route('/admin/estudiantes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_estudiante(id):
    """Editar estudiante"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    estudiante = Estudiante.query.get_or_404(id)
    
    if request.method == 'POST':
        estudiante.nombre = request.form['nombre']
        estudiante.edad = int(request.form['edad'])
        estudiante.grado = request.form['grado']
        estudiante.escuela = request.form.get('escuela', '')
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
        # Eliminar pagos relacionados
        Pago.query.filter_by(estudiante_id=id).delete()
        
        # Eliminar estudiante
        db.session.delete(estudiante)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '✅ Estudiante eliminado exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/pagos')
@login_required
def admin_pagos():
    """Gestión de pagos"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    estado = request.args.get('estado', 'todos')
    
    query = Pago.query.join(Estudiante)
    
    if estado == 'pendiente':
        query = query.filter(Pago.estado == 'pendiente')
    elif estado == 'vencido':
        query = query.filter(Pago.estado == 'pendiente', Pago.fecha_vencimiento < datetime.utcnow())
    elif estado == 'pagado':
        query = query.filter(Pago.estado == 'pagado')
    
    pagos = query.order_by(Pago.fecha_vencimiento).all()
    estudiantes = Estudiante.query.all()
    
    return render_template('admin/pagos.html',
                        pagos=pagos,
                        estudiantes=estudiantes,
                        estado_actual=estado,
                        now=datetime.utcnow())

@app.route('/admin/pagos/registrar', methods=['POST'])
@login_required
def registrar_pago_admin():
    """Registrar pago desde administrador"""
    if current_user.rol != 'admin':
        flash('⚠️ No tienes permisos', 'error')
        return redirect(url_for('index'))
    
    try:
        pago_id = request.form.get('pago_id')
        metodo_pago = request.form['metodo_pago']
        referencia = request.form.get('referencia', '')
        
        if pago_id:
            # Registrar pago existente
            pago = Pago.query.get_or_404(pago_id)
        else:
            # Crear nuevo pago manual
            estudiante_id = int(request.form['estudiante_id'])
            monto = float(request.form['monto'])
            meses = int(request.form['meses'])
            
            pago = Pago(
                estudiante_id=estudiante_id,
                monto=monto,
                fecha_vencimiento=calcular_vencimiento(meses),
                estado='pendiente',
                meses_cubiertos=meses
            )
            db.session.add(pago)
        
        # Marcar como pagado
        pago.estado = 'pagado'
        pago.metodo_pago = metodo_pago
        pago.referencia = referencia
        pago.fecha_pago = datetime.utcnow()
        
        # Registrar como ingreso
        ingreso = Ingreso(
            tipo='pago_estudiante',
            descripcion=f'Pago registrado - Estudiante ID: {pago.estudiante_id}',
            monto=pago.monto,
            estudiante_id=pago.estudiante_id,
            referencia_pago=referencia
        )
        db.session.add(ingreso)
        
        # Crear siguiente pago
        nuevo_pago = Pago(
            estudiante_id=pago.estudiante_id,
            monto=pago.monto,
            fecha_vencimiento=calcular_vencimiento(pago.meses_cubiertos),
            estado='pendiente',
            meses_cubiertos=pago.meses_cubiertos
        )
        db.session.add(nuevo_pago)
        
        # Notificar al padre
        estudiante = Estudiante.query.get(pago.estudiante_id)
        if estudiante and estudiante.padre_id:
            crear_notificacion(
                estudiante.padre_id,
                'pago',
                f'💰 Pago registrado para {estudiante.nombre}. Próximo vence {nuevo_pago.fecha_vencimiento.strftime("%d/%m/%Y")}'
            )
        
        db.session.commit()
        
        flash('✅ Pago registrado exitosamente', 'success')
        return redirect(url_for('admin_pagos'))
        
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin_pagos'))

@app.route('/admin/pagos/<int:id>/detalles')
@login_required
def detalles_pago(id):
    """Ver detalles de pago"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    pago = Pago.query.get_or_404(id)
    return jsonify({
        'id': pago.id,
        'estudiante': pago.estudiante.nombre if pago.estudiante else 'N/A',
        'monto': pago.monto,
        'estado': pago.estado,
        'fecha_vencimiento': pago.fecha_vencimiento.strftime('%d/%m/%Y') if pago.fecha_vencimiento else '',
        'fecha_pago': pago.fecha_pago.strftime('%d/%m/%Y') if pago.fecha_pago else '',
        'metodo_pago': pago.metodo_pago or 'No especificado'
    })

@app.route('/admin/finanzas')
@login_required
def admin_finanzas():
    """Sistema de finanzas"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    ingresos = Ingreso.query.order_by(Ingreso.fecha.desc()).all()
    gastos = Gasto.query.order_by(Gasto.fecha.desc()).all()
    
    total_ingresos = sum(i.monto for i in ingresos)
    total_gastos = sum(g.monto for g in gastos)
    balance = total_ingresos - total_gastos
    
    return render_template('admin/finanzas.html',
                        ingresos=ingresos,
                        gastos=gastos,
                        total_ingresos=total_ingresos,
                        total_gastos=total_gastos,
                        balance=balance)

@app.route('/admin/finanzas/agregar-gasto', methods=['POST'])
@login_required
def agregar_gasto():
    """Agregar nuevo gasto"""
    if current_user.rol != 'admin':
        flash('⚠️ No tienes permisos', 'error')
        return redirect(url_for('index'))
    
    try:
        tipo = request.form['tipo']
        descripcion = request.form['descripcion']
        monto = float(request.form['monto'])
        
        gasto = Gasto(
            tipo=tipo,
            descripcion=descripcion,
            monto=monto,
            usuario_id=current_user.id
        )
        
        db.session.add(gasto)
        db.session.commit()
        
        flash('✅ Gasto registrado exitosamente', 'success')
        return redirect(url_for('admin_finanzas'))
        
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin_finanzas'))

@app.route('/admin/finanzas/agregar-ingreso', methods=['POST'])
@login_required
def agregar_ingreso_manual():
    """Agregar ingreso manual"""
    if current_user.rol != 'admin':
        flash('⚠️ No tienes permisos', 'error')
        return redirect(url_for('index'))
    
    try:
        tipo = request.form['tipo']
        descripcion = request.form['descripcion']
        monto = float(request.form['monto'])
        
        ingreso = Ingreso(
            tipo=tipo,
            descripcion=descripcion,
            monto=monto
        )
        
        db.session.add(ingreso)
        db.session.commit()
        
        flash('✅ Ingreso registrado exitosamente', 'success')
        return redirect(url_for('admin_finanzas'))
        
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin_finanzas'))

@app.route('/admin/conductores')
@login_required
def admin_conductores():
    """Gestión de conductores"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    estado = request.args.get('estado', 'todos')
    
    query = Usuario.query.filter_by(rol='conductor')
    
    if estado == 'activos':
        query = query.filter_by(activo=True)
    elif estado == 'pendientes':
        query = query.filter_by(activo=False)
    
    conductores = query.order_by(Usuario.fecha_registro.desc()).all()
    
    # Obtener rutas por conductor
    rutas = Ruta.query.all()
    rutas_por_conductor = {ruta.conductor_id: ruta for ruta in rutas}
    
    # Obtener vehículos por conductor
    vehiculos = Vehiculo.query.all()
    vehiculos_por_conductor = {vehiculo.conductor_id: vehiculo for vehiculo in vehiculos if vehiculo.conductor_id}
    
    # Contar conductores con rutas
    conductores_con_rutas = len([c for c in conductores if c.id in rutas_por_conductor])
    
    # Vehículos disponibles para asignar
    vehiculos_disponibles = Vehiculo.query.filter_by(conductor_id=None).all()
    
    return render_template('admin/conductores.html',
                        conductores=conductores,
                        estado_actual=estado,
                        rutas_por_conductor=rutas_por_conductor,
                        vehiculos_por_conductor=vehiculos_por_conductor,
                        vehiculos_disponibles=vehiculos_disponibles,
                        conductores_con_rutas=conductores_con_rutas,
                        conductores_pendientes=len([c for c in conductores if not c.activo]))

@app.route('/admin/conductores/<int:id>/aprobar', methods=['POST'])
@login_required
def aprobar_conductor(id):
    """Aprobar conductor pendiente"""
    if current_user.rol != 'admin':
        flash('⚠️ No tienes permisos', 'error')
        return redirect(url_for('index'))
    
    conductor = Usuario.query.get_or_404(id)
    
    if conductor.rol != 'conductor':
        flash('❌ Usuario no es conductor', 'error')
        return redirect(url_for('admin_conductores'))
    
    conductor.activo = True
    db.session.commit()
    
    flash(f'✅ Conductor {conductor.nombre} aprobado exitosamente', 'success')
    return redirect(url_for('admin_conductores'))

@app.route('/admin/conductores/<int:id>/asignar-vehiculo', methods=['POST'])
@login_required
def asignar_vehiculo_conductor(id):
    """Asignar vehículo a conductor"""
    if current_user.rol != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    conductor = Usuario.query.get_or_404(id)
    vehiculo_id = request.json.get('vehiculo_id')
    
    if not vehiculo_id:
        return jsonify({'success': False, 'error': 'ID de vehículo requerido'}), 400
    
    vehiculo = Vehiculo.query.get_or_404(vehiculo_id)
    
    # Liberar vehículo actual del conductor si tiene
    vehiculo_actual = Vehiculo.query.filter_by(conductor_id=conductor.id).first()
    if vehiculo_actual:
        vehiculo_actual.conductor_id = None
    
    # Asignar nuevo vehículo
    vehiculo.conductor_id = conductor.id
    db.session.commit()
    
    flash(f'✅ Vehículo {vehiculo.placa} asignado a {conductor.nombre}', 'success')
    return redirect(url_for('admin_conductores'))

@app.route('/admin/vehiculos')
@login_required
def admin_vehiculos():
    """Gestión de vehículos"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    vehiculos = Vehiculo.query.all()
    conductores = Usuario.query.filter_by(rol='conductor', activo=True).all()
    
    return render_template('admin/vehiculos.html',
                        vehiculos=vehiculos,
                        conductores=conductores)

@app.route('/admin/vehiculos/agregar', methods=['POST'])
@login_required
def agregar_vehiculo():
    """Agregar nuevo vehículo"""
    if current_user.rol != 'admin':
        flash('⚠️ No tienes permisos', 'error')
        return redirect(url_for('index'))
    
    try:
        placa = request.form['placa']
        marca = request.form['marca']
        modelo = request.form['modelo']
        año = int(request.form['año'])
        capacidad = int(request.form['capacidad'])
        conductor_id = request.form.get('conductor_id')
        
        nuevo_vehiculo = Vehiculo(
            placa=placa,
            marca=marca,
            modelo=modelo,
            año=año,
            capacidad=capacidad,
            conductor_id=int(conductor_id) if conductor_id else None,
            estado='activo'
        )
        
        db.session.add(nuevo_vehiculo)
        db.session.commit()
        
        flash('✅ Vehículo agregado exitosamente', 'success')
        return redirect(url_for('admin_vehiculos'))
        
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
        return redirect(url_for('admin_vehiculos'))

@app.route('/admin/padres')
@login_required
def admin_padres():
    """Gestión de padres/tutores"""
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    padres = Usuario.query.filter_by(rol='padre').all()
    
    # Obtener información de estudiantes y pagos para cada padre
    padres_info = []
    for padre in padres:
        estudiantes = Estudiante.query.filter_by(padre_id=padre.id).all()
        pagos_pendientes = Pago.query.filter(
            Pago.estudiante_id.in_([e.id for e in estudiantes]),
            Pago.estado == 'pendiente'
        ).all()
        
        padres_info.append({
            'padre': padre,
            'estudiantes': estudiantes,
            'pagos_pendientes': pagos_pendientes,
            'total_pendiente': sum(p.monto for p in pagos_pendientes)
        })
    
    return render_template('admin/padres.html', padres_info=padres_info)

# ==================== PANEL DE PADRES ====================
@app.route('/padres/dashboard')
@login_required
def padre_dashboard():
    """Dashboard para padres"""
    if current_user.rol != 'padre':
        flash('⚠️ Esta sección es solo para padres/tutores', 'warning')
        return redirect(url_for('index'))
    
    # Obtener estudiantes del padre
    estudiantes = Estudiante.query.filter_by(padre_id=current_user.id).all()
    
    # Obtener pagos pendientes
    pagos_pendientes = []
    for estudiante in estudiantes:
        pagos = Pago.query.filter_by(
            estudiante_id=estudiante.id,
            estado='pendiente'
        ).order_by(Pago.fecha_vencimiento).all()
        pagos_pendientes.extend(pagos)
    
    # Obtener notificaciones
    notificaciones = Notificacion.query.filter_by(
        usuario_id=current_user.id,
        leida=False
    ).order_by(Notificacion.fecha.desc()).limit(10).all()
    
    return render_template('padres/dashboard.html',
                        estudiantes=estudiantes,
                        pagos_pendientes=pagos_pendientes,
                        notificaciones=notificaciones)

@app.route('/padres/ruta/<int:estudiante_id>')
@login_required
def ver_ruta(estudiante_id):
    """Ver ruta del estudiante con GPS simulado"""
    if current_user.rol != 'padre':
        return redirect(url_for('index'))
    
    estudiante = Estudiante.query.get_or_404(estudiante_id)
    
    # Verificar que el estudiante pertenece al padre
    if estudiante.padre_id != current_user.id:
        flash('⚠️ No tienes acceso a este estudiante', 'error')
        return redirect(url_for('padre_dashboard'))
    
    ruta = Ruta.query.get(estudiante.ruta_id) if estudiante.ruta_id else None
    
    # Datos para el mapa (simulado)
    ubicacion_vehiculo = {
        'lat': 12.1364,
        'lng': -86.2514,
        'placa': 'ABC-123',
        'ultima_actualizacion': datetime.now().strftime('%H:%M')
    }
    
    return render_template('padres/ruta.html',
                        estudiante=estudiante,
                        ruta=ruta,
                        ubicacion_vehiculo=ubicacion_vehiculo)

@app.route('/padres/pagos/realizar/<int:pago_id>', methods=['POST'])
@login_required
def realizar_pago(pago_id):
    """Realizar pago en línea"""
    if current_user.rol != 'padre':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    pago = Pago.query.get_or_404(pago_id)
    
    # Verificar que el pago corresponda a un estudiante del padre
    estudiante = Estudiante.query.get(pago.estudiante_id)
    if not estudiante or estudiante.padre_id != current_user.id:
        return jsonify({'success': False, 'error': 'No tienes permiso para pagar esto'}), 403
    
    try:
        metodo_pago = request.form['metodo_pago']
        referencia = f"ONLINE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Marcar como pagado
        pago.estado = 'pagado'
        pago.metodo_pago = metodo_pago
        pago.referencia = referencia
        pago.fecha_pago = datetime.utcnow()
        
        # Registrar como ingreso
        ingreso = Ingreso(
            tipo='pago_estudiante',
            descripcion=f'Pago en línea - {estudiante.nombre}',
            monto=pago.monto,
            estudiante_id=estudiante.id,
            referencia_pago=referencia
        )
        db.session.add(ingreso)
        
        # Crear siguiente pago
        nuevo_pago = Pago(
            estudiante_id=pago.estudiante_id,
            monto=pago.monto,
            fecha_vencimiento=calcular_vencimiento(pago.meses_cubiertos),
            estado='pendiente',
            meses_cubiertos=pago.meses_cubiertos
        )
        db.session.add(nuevo_pago)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '✅ Pago realizado exitosamente',
            'referencia': referencia
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PANEL DE CONDUCTOR ====================
@app.route('/conductor/dashboard')
@login_required
def conductor_dashboard():
    """Dashboard del conductor"""
    if current_user.rol != 'conductor':
        flash('⚠️ Esta sección es solo para conductores', 'warning')
        return redirect(url_for('index'))
    
    if not current_user.activo:
        flash('❌ Tu cuenta está pendiente de aprobación', 'error')
        return redirect(url_for('index'))
    
    # Obtener ruta asignada
    ruta = Ruta.query.filter_by(conductor_id=current_user.id, activa=True).first()
    
    # Obtener estudiantes de la ruta
    estudiantes = []
    if ruta:
        estudiantes = Estudiante.query.filter_by(ruta_id=ruta.id).all()
    
    # Obtener vehículo asignado
    vehiculo = Vehiculo.query.filter_by(conductor_id=current_user.id).first()
    
    # Asistencias de hoy
    hoy = datetime.utcnow().date()
    asistencias_hoy = Asistencia.query.filter(
        Asistencia.estudiante_id.in_([e.id for e in estudiantes]) if estudiantes else False,
        db.func.date(Asistencia.fecha) == hoy
    ).order_by(Asistencia.fecha.desc()).all()
    
    return render_template('conductor/dashboard.html',
                        ruta=ruta,
                        estudiantes=estudiantes,
                        vehiculo=vehiculo,
                        asistencias_hoy=asistencias_hoy)

@app.route('/conductor/ubicacion/actualizar', methods=['POST'])
@login_required
def actualizar_ubicacion_conductor():
    """Actualizar ubicación GPS del conductor"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        lat = float(request.json['lat'])
        lng = float(request.json['lng'])
        
        # Simular guardado de ubicación
        session['ubicacion_lat'] = lat
        session['ubicacion_lng'] = lng
        
        return jsonify({
            'success': True,
            'message': '✅ Ubicación actualizada',
            'lat': lat,
            'lng': lng
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/conductor/asistencia/registrar', methods=['POST'])
@login_required
def registrar_asistencia_conductor():
    """Registrar asistencia (subida/bajada) de estudiante"""
    if current_user.rol != 'conductor':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        estudiante_id = int(request.json['estudiante_id'])
        tipo = request.json['tipo']  # 'entrada' o 'salida'
        
        estudiante = Estudiante.query.get_or_404(estudiante_id)
        
        # Registrar asistencia
        asistencia = Asistencia(
            estudiante_id=estudiante_id,
            tipo=tipo
        )
        db.session.add(asistencia)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'✅ {estudiante.nombre} registrado(a)',
            'hora': datetime.utcnow().strftime('%H:%M')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== MODO OSCURO ====================
@app.route('/toggle-dark-mode')
def toggle_dark_mode():
    """Cambiar entre modo claro y oscuro"""
    dark_mode = session.get('dark_mode', False)
    session['dark_mode'] = not dark_mode
    return jsonify({'dark_mode': not dark_mode})

# ==================== ERRORES ====================
@app.errorhandler(404)
def pagina_no_encontrada(e):
    return render_template('404.html'), 404

# ==================== INICIALIZACIÓN ====================
if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SISTEMA CAMLEY TRANSPORTE ESCOLAR")
    print("=" * 60)
    
    # Crear carpeta data si no existe
    os.makedirs('data', exist_ok=True)
    
    # Inicializar base de datos
    with app.app_context():
        db.create_all()
        print("✅ Base de datos verificada")
    
    print("\n📍 URL Principal: http://127.0.0.1:5000")
    print("👨‍💼 Panel Admin: http://127.0.0.1:5000/admin/dashboard")
    print("👨‍👧 Panel Padres: http://127.0.0.1:5000/padres/dashboard")
    print("🚍 Panel Conductor: http://127.0.0.1:5000/conductor/dashboard")
    print("=" * 60)
    print("🔑 CREDENCIALES DE PRUEBA:")
    print("   Admin: admin@camley.com / admin123")
    print("   Padre: padre@ejemplo.com / padre123")
    print("   Conductor: conductor@camley.com / conductor123")
    print("=" * 60)
    
    app.run(debug=True, port=5000, host='0.0.0.0')