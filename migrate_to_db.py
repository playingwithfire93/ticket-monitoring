"""
Script de migración: importa todos los musicales y enlaces de urls.json a la BD (musicals.db)
Evita duplicados y reporta el progreso.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import app, db
from models import Musical, MusicalLink
import json

BASE = Path(__file__).parent
URLS_FILE = BASE / "urls.json"

def migrate_urls_to_db():
    """Lee urls.json y crea registros en la BD si no existen."""
    with app.app_context():
        print("🔄 Iniciando migración de urls.json → musicals.db")
        
        # Leer urls.json
        try:
            with URLS_FILE.open("r", encoding="utf-8") as f:
                urls_data = json.load(f)
        except Exception as e:
            print(f"❌ Error leyendo urls.json: {e}")
            return
        
        if not isinstance(urls_data, list):
            print("❌ urls.json debe ser una lista")
            return
        
        created_musicals = 0
        created_links = 0
        skipped_musicals = 0
        skipped_links = 0
        
        for item in urls_data:
            name = (item.get("musical") or item.get("name") or "").strip()
            if not name:
                print(f"⚠️  Saltando item sin nombre: {item}")
                continue
            
            urls = item.get("urls") or []
            if not urls:
                print(f"⚠️  Musical '{name}' sin URLs, saltando")
                continue
            
            # Buscar o crear musical
            musical = Musical.query.filter_by(name=name).first()
            if not musical:
                musical = Musical(
                    name=name,
                    description=item.get("description", ""),
                    image_url=item.get("image", "")
                )
                db.session.add(musical)
                db.session.flush()  # obtener ID
                created_musicals += 1
                print(f"✅ Creado musical: {name} (ID: {musical.id})")
            else:
                skipped_musicals += 1
                print(f"ℹ️  Musical ya existe: {name} (ID: {musical.id})")
            
            # Añadir enlaces
            for url in urls:
                url = url.strip()
                if not url:
                    continue
                
                # Verificar si el enlace ya existe
                existing = MusicalLink.query.filter_by(
                    musical_id=musical.id,
                    url=url
                ).first()
                
                if not existing:
                    link = MusicalLink(
                        musical_id=musical.id,
                        url=url,
                        notes=f"Importado de urls.json"
                    )
                    db.session.add(link)
                    created_links += 1
                    print(f"   ➕ Añadido enlace: {url[:60]}...")
                else:
                    skipped_links += 1
                    print(f"   ℹ️  Enlace ya existe: {url[:60]}...")
        
        # Guardar cambios
        db.session.commit()
        
        print("\n" + "="*60)
        print("📊 RESUMEN DE MIGRACIÓN")
        print("="*60)
        print(f"✅ Musicales creados:    {created_musicals}")
        print(f"ℹ️  Musicales existentes: {skipped_musicals}")
        print(f"✅ Enlaces añadidos:     {created_links}")
        print(f"ℹ️  Enlaces existentes:  {skipped_links}")
        print("="*60)
        print(f"🎉 Total en BD: {Musical.query.count()} musicales, {MusicalLink.query.count()} enlaces")
        print("="*60)

if __name__ == "__main__":
    migrate_urls_to_db()