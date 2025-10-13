"""
Actualiza la base de datos añadiendo los campos de tracking de cambios
"""
from app import app, db
from models import Musical, MusicalLink, MusicalChange

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