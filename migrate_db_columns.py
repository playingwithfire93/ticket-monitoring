"""
Migración: Añade columnas faltantes a la BD existente sin perder datos
"""
from app import app, db
from sqlalchemy import text

def migrate_database():
    with app.app_context():
        print("🔄 Verificando columnas de la base de datos...")
        
        try:
            # Intentar añadir updated_at a musicals
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE musicals ADD COLUMN updated_at DATETIME"))
                conn.commit()
                print("✅ Añadida columna 'updated_at' a musicals")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("ℹ️  Columna 'updated_at' ya existe")
            else:
                print(f"⚠️  Error añadiendo updated_at: {e}")
        
        try:
            # Intentar añadir last_checked a musical_links
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE musical_links ADD COLUMN last_checked DATETIME"))
                conn.commit()
                print("✅ Añadida columna 'last_checked' a musical_links")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("ℹ️  Columna 'last_checked' ya existe")
            else:
                print(f"⚠️  Error añadiendo last_checked: {e}")
        
        try:
            # Intentar añadir status a musical_links
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE musical_links ADD COLUMN status VARCHAR(50) DEFAULT 'active'"))
                conn.commit()
                print("✅ Añadida columna 'status' a musical_links")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("ℹ️  Columna 'status' ya existe")
            else:
                print(f"⚠️  Error añadiendo status: {e}")
        
        print("\n✅ Migración completada")

if __name__ == "__main__":
    migrate_database()