from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import os

# ==================== CONFIGURACIÓN ====================
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'camley-seguro-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data', 'camley.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== MODELOS ====================

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), nullable=False)  # admin, padre, conductor
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)


class Estudiante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    edad = db.Column(db.Integer)
    grado = db.Column(db.String(50))
    escuela = db.Column(db.String(100))
    padre_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    ruta_id = db.Column(db.Integer, db.ForeignKey('ruta.id'))
    fecha_inscripcion = db.Column(db.DateTime, default=datetime.utcnow)


class Ruta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    hora_inicio = db.Column(db.String(10))
    activa = db.Column(db.Boolean, default=True)


class Vehiculo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(20), unique=True, nullable=False)
    marca = db.Column(db.String(50))
    modelo = db.Column(db.String(50))
    año = db.Column(db.Integer)
    capacidad = db.Column(db.Integer)
    estado = db.Column(db.String(20), default='activo')
    conductor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))


class Pago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'))
    monto = db.Column(db.Float, nullable=False)
    fecha_emision = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_vencimiento = db.Column(db.DateTime)
    fecha_pago = db.Column(db.DateTime)
    metodo_pago = db.Column(db.String(50))
    estado = db.Column(db.String(20), default='pendiente')
    meses_cubiertos = db.Column(db.Integer, default=1)


class Gasto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))


class Ingreso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    monto = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'))


class Notificacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    tipo = db.Column(db.String(50))
    mensaje = db.Column(db.Text)
    link = db.Column(db.String(200))
    leida = db.Column(db.Boolean, default=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)


class Asistencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiante.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # entrada / salida
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== INICIALIZACIÓN ====================

def inicializar_base_datos():
    """Crear datos iniciales COMPLETOS"""
    with app.app_context():
        db.create_all()
        print("🔄 Creando base de datos...")

        # Crear usuarios si no existen
        if not Usuario.query.filter_by(email='admin@camley.com').first():
            admin = Usuario(
                email='admin@camley.com',
                password='admin123',
                nombre='Administrador Principal',
                rol='admin',
                telefono='8952-9405',
                activo=True
            )
            db.session.add(admin)
            print("✅ Admin creado")

        if not Usuario.query.filter_by(email='padre@ejemplo.com').first():
            padre = Usuario(
                email='padre@ejemplo.com',
                password='padre123',
                nombre='Juan Pérez',
                rol='padre',
                telefono='1234-5678',
                activo=True
            )
            db.session.add(padre)
            print("✅ Padre creado")

        if not Usuario.query.filter_by(email='conductor@camley.com').first():
            conductor = Usuario(
                email='conductor@camley.com',
                password='conductor123',
                nombre='Carlos López',
                rol='conductor',
                telefono='8765-4321',
                activo=True
            )
            db.session.add(conductor)
            print("✅ Conductor creado")

        # Crear vehículo de prueba
        if not Vehiculo.query.first():
            conductor = Usuario.query.filter_by(email='conductor@camley.com').first()
            if conductor:
                vehiculo = Vehiculo(
                    placa='ABC-123',
                    marca='Toyota',
                    modelo='Hiace',
                    año=2022,
                    capacidad=15,
                    conductor_id=conductor.id,
                    estado='activo'
                )
                db.session.add(vehiculo)
                print("✅ Vehículo creado")

        # Crear ruta de prueba
        if not Ruta.query.first():
            conductor = Usuario.query.filter_by(email='conductor@camley.com').first()
            if conductor:
                ruta = Ruta(
                    nombre='Ruta Norte - Mañana',
                    descripcion='Recoge estudiantes del sector norte',
                    conductor_id=conductor.id,
                    hora_inicio='07:00',
                    activa=True
                )
                db.session.add(ruta)
                print("✅ Ruta creada")

        # Crear estudiante de prueba CON PADRE
        if not Estudiante.query.first():
            padre = Usuario.query.filter_by(email='padre@ejemplo.com').first()
            ruta = Ruta.query.first()
            estudiante = Estudiante(
                nombre='Ana Pérez',
                edad=10,
                grado='4to Grado',
                escuela='Escuela Central',
                padre_id=padre.id if padre else None,
                ruta_id=ruta.id if ruta else None,
                fecha_inscripcion=datetime.utcnow()
            )
            db.session.add(estudiante)
            print("✅ Estudiante creado (asignado a padre)")

        # Crear pago de prueba
        if not Pago.query.first():
            estudiante = Estudiante.query.first()
            if estudiante:
                pago = Pago(
                    estudiante_id=estudiante.id,
                    monto=50.00,
                    fecha_vencimiento=datetime.utcnow(),
                    estado='pendiente',
                    meses_cubiertos=1
                )
                db.session.add(pago)
                print("✅ Pago de prueba creado")

        db.session.commit()
        print("🎉 Base de datos inicializada correctamente")
        print("\n📋 CREDENCIALES:")
        print("   👨‍💼 Admin: admin@camley.com / admin123")
        print("   👨‍👧 Padre: padre@ejemplo.com / padre123")
        print("   🚍 Conductor: conductor@camley.com / conductor123")

# Ejecutar solo si se llama directo
if __name__ == '__main__':
    inicializar_base_datos()