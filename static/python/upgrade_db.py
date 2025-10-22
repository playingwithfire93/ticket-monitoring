"""
Actualiza la base de datos añadiendo los campos de tracking de cambios
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app, db

def upgrade_database():
    with app.app_context():
        print("🔄 Actualizando estructura de base de datos...")
        
        # Crear nuevas tablas y columnas
        db.create_all()
        
        print("✅ Base de datos actualizada correctamente")
        print("\nNuevas capacidades:")
        print("  • updated_at en musicals")
        print("  • last_checked y status en musical_links")
        print("  • Tabla musical_changes para historial completo")

if __name__ == "__main__":
    upgrade_database()