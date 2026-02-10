from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

# ==================== CONFIGURACIÓN ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'camley-transporte-escolar-2024-secret-key'
db_uri = os.getenv('DATABASE_URL', 'sqlite:///camley_transporte.db')
# SQLAlchemy requiere "postgresql://" en lugar de "postgres://"
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== MODELOS SIMPLIFICADOS ====================

class Usuario(db.Model):
    """Modelo de usuario para todos los roles"""
    __tablename__ = 'usuario'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    genero = db.Column(db.String(10))
    rol = db.Column(db.String(20), nullable=False)  # 'admin', 'padre', 'conductor'
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones SIMPLIFICADAS (sin duplicados)
    # Estudiantes hijos (solo para padres)
    hijos = db.relationship('Estudiante', backref='padre_rel', 
                        foreign_keys='Estudiante.padre_id', lazy=True)
    
    # Rutas asignadas (solo para conductores)
    rutas = db.relationship('Ruta', backref='conductor_rel', 
                        foreign_keys='Ruta.conductor_id', lazy=True)
    
    # Notificaciones
    notificaciones = db.relationship('Notificacion', backref='usuario', lazy=True)
    
    # Flask-Login
    @property
    def is_authenticated(self):
        return True
    
    @property
    def is_active(self):
        return self.activo
    
    @property
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f'<Usuario {self.nombre} - {self.rol}>'

class Estudiante(db.Model):
    """Modelo de estudiante - VERSIÓN CORREGIDA"""
    __tablename__ = 'estudiante'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    edad = db.Column(db.Integer)
    genero = db.Column(db.String(10))
    grado = db.Column(db.String(50))
    escuela = db.Column(db.String(200))
    condicion = db.Column(db.String(200))
    padre_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    ruta_id = db.Column(db.Integer, db.ForeignKey('ruta.id'))
    fecha_inscripcion = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    
    # RELACIÓN CON PAGOS - ¡IMPORTANTE PARA EL ERROR!
    pagos = db.relationship('Pago', backref='estudiante', lazy=True)
    
    # Relación con asistencias
    asistencias = db.relationship('Asistencia', backref='estudiante', lazy=True)
    
    def __repr__(self):
        return f'<Estudiante {self.nombre}>'

class Ruta(db.Model):
    """Modelo de ruta de transporte"""
    __tablename__ = 'ruta'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    hora_inicio = db.Column(db.String(10))  # formato: "07:00"
    hora_fin = db.Column(db.String(10))     # formato: "08:30"
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculo.id'))
    activa = db.Column(db.Boolean, default=True)
    
    # Estudiantes en esta ruta
    estudiantes = db.relationship('Estudiante', backref='ruta', lazy=True)
    
    # Vehículo asignado
    vehiculo = db.relationship('Vehiculo', foreign_keys=[vehiculo_id])
    
    def __repr__(self):
        return f'<Ruta {self.nombre}>'

class Vehiculo(db.Model):
    """Modelo de vehículo"""
    __tablename__ = 'vehiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(20), unique=True, nullable=False)
    modelo = db.Column(db.String(100))
    marca = db.Column(db.String(100))
    año = db.Column(db.Integer)
    capacidad = db.Column(db.Integer)
    color = db.Column(db.String(50))
    activo = db.Column(db.Boolean, default=True)
    estado = db.Column(db.String(20), default='activo')  # activo, mantenimiento, inactivo
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    kilometraje = db.Column(db.Integer)
    ultimo_mantenimiento = db.Column(db.DateTime)
    observaciones = db.Column(db.Text)
    
    conductor = db.relationship('Usuario', foreign_keys=[conductor_id])
    
    def __repr__(self):
        return f'<Vehiculo {self.placa}>'

class Pago(db.Model):
    """Modelo de pago - ¡CORREGIDO!"""
    __tablename__ = 'pago'
    
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fecha_pago = db.Column(db.DateTime)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(20), default='pendiente')  # 'pagado', 'pendiente', 'vencido'
    meses_cubiertos = db.Column(db.Integer, default=1)
    metodo_pago = db.Column(db.String(50))
    referencia = db.Column(db.String(100))
    visto_padre = db.Column(db.Boolean, default=False)
    descripcion = db.Column(db.String(200))
    
    
    
    
    def __repr__(self):
        return f'<Pago ${self.monto} - {self.estado}>'

class Gasto(db.Model):
    """Modelo de gasto"""
    __tablename__ = 'gasto'
    
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50))  # mantenimiento, salarios, combustible, otros
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    comprobante = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Gasto ${self.monto} - {self.categoria}>'

class Ingreso(db.Model):
    """Modelo de ingreso"""
    __tablename__ = 'ingreso'
    
    id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    fuente = db.Column(db.String(50))  # pago_estudiante, otros
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Ingreso ${self.monto} - {self.fuente}>'

class Notificacion(db.Model):
    """Modelo de notificación"""
    __tablename__ = 'notificacion'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    tipo = db.Column(db.String(50))  # sistema, pago, asistencia, retraso, estudiante
    mensaje = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    leida = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Notificacion {self.tipo}>'

class Asistencia(db.Model):
    """Modelo de asistencia"""
    __tablename__ = 'asistencia'
    
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time)
    estado = db.Column(db.String(20))  # presente, ausente, tardanza, justificado
    observaciones = db.Column(db.Text)
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    
    conductor = db.relationship('Usuario', foreign_keys=[conductor_id])
    
    def __repr__(self):
        return f'<Asistencia {self.estado} - {self.fecha}>'

class AsistenciaManual(db.Model):
    """Resumen manual de asistencia por conductor"""
    __tablename__ = 'asistencia_manual'
    
    id = db.Column(db.Integer, primary_key=True)
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    presentes = db.Column(db.Integer, default=0)
    ausentes = db.Column(db.Integer, default=0)
    notas = db.Column(db.Text)
    
    conductor = db.relationship('Usuario', foreign_keys=[conductor_id])

class TicketSoporte(db.Model):
    """Mensajes de soporte enviados por padres"""
    __tablename__ = 'ticket_soporte'
    
    id = db.Column(db.Integer, primary_key=True)
    remitente_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    remitente_rol = db.Column(db.String(20), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='abierto')  # abierto, respondido, cerrado
    respuesta = db.Column(db.Text)
    respondido_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    respondido_en = db.Column(db.DateTime)
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    
    remitente = db.relationship('Usuario', foreign_keys=[remitente_id])
    respondido_por = db.relationship('Usuario', foreign_keys=[respondido_por_id])
    conductor = db.relationship('Usuario', foreign_keys=[conductor_id])

class UbicacionVehiculo(db.Model):
    """Última ubicación del conductor"""
    __tablename__ = 'ubicacion_vehiculo'
    
    id = db.Column(db.Integer, primary_key=True)
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    ultima_actualizacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    conductor = db.relationship('Usuario', foreign_keys=[conductor_id])
    
    def __repr__(self):
        return f'<UbicacionVehiculo {self.conductor_id}>'

# ==================== FUNCIONES AUXILIARES ====================

def crear_usuarios_ejemplo():
    """Crear usuarios de ejemplo si no existen"""
    with app.app_context():
        # Verificar si ya existe admin
        if not Usuario.query.filter_by(email='admin@camley.com').first():
            
            admin = Usuario(
                nombre='Administrador Camley',
                email='admin@camley.com',
                password='admin123',
                telefono='+1234567890',
                direccion='Oficina Central',
                genero='masculino',
                rol='admin',
                activo=True
            )
            
            padre = Usuario(
                nombre='Juan Pérez',
                email='padre@camley.com',
                password='padre123',
                telefono='+0987654321',
                direccion='Calle Ejemplo 123',
                genero='masculino',
                rol='padre',
                activo=True
            )
            
            conductor = Usuario(
                nombre='Carlos López',
                email='conductor@camley.com',
                password='conductor123',
                telefono='+1122334455',
                direccion='Avenida Conductores 456',
                genero='masculino',
                rol='conductor',
                activo=True
            )
            
            db.session.add_all([admin, padre, conductor])
            db.session.commit()
            print("✅ Usuarios de ejemplo creados")
            print("   👑 Admin: admin@camley.com / admin123")
            print("   👨 Padre: padre@camley.com / padre123")
            print("   🚍 Conductor: conductor@camley.com / conductor123")

def inicializar_base_datos():
    """Crear tablas si no existen"""
    with app.app_context():
        try:
            # Crear tablas
            db.create_all()
            
            # Crear usuarios
            crear_usuarios_ejemplo()
            
            print("\n" + "=" * 50)
            print("✅ BASE DE DATOS INICIALIZADA CORRECTAMENTE")
            print("   Sin advertencias, sin errores")
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            print("💡 Si hay error de 'tabla ya existe', ignóralo")

# ==================== EJECUCIÓN ====================

if __name__ == '__main__':
    print("=" * 50)
    print("INICIALIZANDO BASE DE DATOS - VERSIÓN CORREGIDA")
    print("=" * 50)
    
    inicializar_base_datos()
