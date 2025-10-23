"""
Script to migrate URLs from urls.json to the database
Run this once to populate the database with existing musicals
"""
import os
import json
from pathlib import Path
from app import app, db
from models import Musical, MusicalLink
from datetime import datetime, timezone

def migrate_urls():
    """Migrate URLs from JSON file to database"""
    BASE = Path(__file__).parent
    URLS_FILE = BASE / "static" / "python" / "urls.json"
    
    if not URLS_FILE.exists():
        print(f"❌ File not found: {URLS_FILE}")
        return
    
    print("=" * 60)
    print("🔄 Starting migration from urls.json to database")
    print("=" * 60)
    
    try:
        with open(URLS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📁 Loaded data from JSON")
        print(f"📊 Data type: {type(data)}")
        
        with app.app_context():
            # Clear existing data
            print("🗑️  Clearing existing data...")
            MusicalLink.query.delete()
            Musical.query.delete()
            db.session.commit()
            
            # Handle different JSON formats
            if isinstance(data, dict):
                # Format: {"Musical Name": ["url1", "url2"]}
                print("📋 Processing dictionary format...")
                for musical_name, urls in data.items():
                    process_musical(musical_name, urls)
                    
            elif isinstance(data, list):
                # Format: [{"musical": "Name", "urls": ["url1"]}, ...]
                print("📋 Processing list format...")
                for item in data:
                    if isinstance(item, dict):
                        musical_name = item.get('musical') or item.get('name') or item.get('siteName')
                        urls = item.get('urls') or item.get('url') or []
                        
                        # Handle single URL string
                        if isinstance(urls, str):
                            urls = [urls]
                        
                        if musical_name and urls:
                            process_musical(musical_name, urls)
                        else:
                            print(f"⚠️  Skipping invalid item: {item}")
            else:
                print(f"❌ Unsupported JSON format: {type(data)}")
                return
            
            # Summary
            total_musicals = Musical.query.count()
            total_links = MusicalLink.query.count()
            
            print("\n" + "=" * 60)
            print("✅ Migration completed successfully!")
            print(f"📊 Total musicals: {total_musicals}")
            print(f"🔗 Total links: {total_links}")
            print("=" * 60)
            
    except json.JSONDecodeError as e:
        print(f"❌ Error reading JSON file: {e}")
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()

def process_musical(musical_name, urls):
    """Process a single musical and its URLs"""
    print(f"\n🎭 Processing: {musical_name}")
    
    # Default images (puedes personalizarlas por musical)
    default_images = [
        f"https://via.placeholder.com/400x200/ff69b4/ffffff?text={musical_name.replace(' ', '+')}+1",
        f"https://via.placeholder.com/400x200/ffb6d9/ffffff?text={musical_name.replace(' ', '+')}+2",
        f"https://via.placeholder.com/400x200/d63384/ffffff?text={musical_name.replace(' ', '+')}+3"
    ]
    
    # Create musical with images
    musical = Musical(
        name=musical_name,
        description=f"Musical: {musical_name}",
        images=default_images  # ← AÑADIR IMÁGENES
    )
    db.session.add(musical)
    db.session.flush()
    print(f"   ✅ Created musical: {musical_name} (ID: {musical.id})")
    
    # Add URLs
    url_count = 0
    if isinstance(urls, list):
        for url in urls:
            if isinstance(url, str) and url.strip():
                link = MusicalLink(
                    musical_id=musical.id,
                    url=url.strip()
                )
                db.session.add(link)
                url_count += 1
    
    db.session.commit()
    print(f"   ✅ Added {url_count} URLs")

if __name__ == '__main__':
    migrate_urls()