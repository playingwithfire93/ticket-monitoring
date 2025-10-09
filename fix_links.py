"""
Script para añadir los enlaces faltantes a los musicales ya creados
"""
from app import app, db, Musical, MusicalLink
import json
from pathlib import Path

BASE = Path(__file__).parent
URLS_FILE = BASE / "urls.json"

def add_missing_links():
    """Lee urls.json y añade los enlaces a los musicales existentes."""
    with app.app_context():
        print("🔄 Añadiendo enlaces faltantes desde urls.json")
        
        # Leer urls.json
        try:
            with URLS_FILE.open("r", encoding="utf-8") as f:
                urls_data = json.load(f)
        except Exception as e:
            print(f"❌ Error leyendo urls.json: {e}")
            return
        
        added_links = 0
        
        for item in urls_data:
            name = (item.get("musical") or item.get("name") or "").strip()
            if not name:
                continue
            
            # Buscar el musical
            musical = Musical.query.filter_by(name=name).first()
            if not musical:
                print(f"⚠️  Musical '{name}' no encontrado en BD, saltando")
                continue
            
            urls = item.get("urls") or []
            print(f"\n📌 Procesando: {name} (ID: {musical.id})")
            print(f"   URLs encontradas en JSON: {len(urls)}")
            
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
                        notes="Importado de urls.json"
                    )
                    db.session.add(link)
                    added_links += 1
                    print(f"   ✅ Añadido: {url[:70]}...")
                else:
                    print(f"   ℹ️  Ya existe: {url[:70]}...")
        
        # Guardar cambios
        db.session.commit()
        
        print("\n" + "="*60)
        print(f"✅ Enlaces añadidos: {added_links}")
        print("="*60)
        
        # Verificar resultado
        print("\n📊 RESUMEN FINAL:")
        for m in Musical.query.all():
            print(f"   {m.name}: {len(m.links)} enlaces")

if __name__ == "__main__":
    add_missing_links()