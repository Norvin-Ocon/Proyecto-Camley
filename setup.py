#!/usr/bin/env python3
"""
Script de configuración para Camley Transporte
Ejecutar: python setup.py
"""

import os
import sys

def main():
    print("=" * 50)
    print("🛠️  CONFIGURACIÓN DE CAMLEY TRANSPORTE")
    print("=" * 50)
    
    # Crear estructura de carpetas
    print("\n📁 Creando estructura de carpetas...")
    carpetas = [
        'data',
        'static/css',
        'static/js',
        'templates/admin',
        'templates/padres',
        'templates/conductor'
    ]
    
    for carpeta in carpetas:
        os.makedirs(carpeta, exist_ok=True)
        print(f"  ✅ {carpeta}")
    
    # Instalar dependencias
    print("\n📦 Instalando dependencias...")
    try:
        os.system('pip install flask flask-sqlalchemy flask-login reportlab')
        print("✅ Dependencias instaladas")
    except:
        print("⚠️  No se pudieron instalar las dependencias automáticamente")
        print("   Ejecuta manualmente: pip install flask flask-sqlalchemy flask-login reportlab")
    
    # Crear archivos básicos si no existen
    print("\n📄 Creando archivos de configuración...")
    
    # requirements.txt
    if not os.path.exists('requirements.txt'):
        with open('requirements.txt', 'w') as f:
            f.write("""Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Flask-Login==0.6.2
reportlab==4.0.4
""")
        print("✅ requirements.txt creado")
    
    print("\n" + "=" * 50)
    print("✅ CONFIGURACIÓN COMPLETADA")
    print("=" * 50)
    print("\n🚀 Para iniciar el sistema:")
    print("   1. Ejecuta: python app.py")
    print("   2. Abre tu navegador en: http://127.0.0.1:5000")
    print("\n🔑 Credenciales de prueba:")
    print("   👨‍💼 Admin: admin@camley.com / admin123")
    print("   👨‍👧 Padre: padre@ejemplo.com / padre123")
    print("   🚍 Conductor: conductor@camley.com / conductor123")
    print("=" * 50)

if __name__ == '__main__':
    main()