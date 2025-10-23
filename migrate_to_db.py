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
        
        print(f"📁 Loaded {len(data)} musicals from JSON")
        
        with app.app_context():
            # Clear existing data (optional - remove if you want to keep existing data)
            print("🗑️  Clearing existing data...")
            MusicalLink.query.delete()
            Musical.query.delete()
            db.session.commit()
            
            # Migrate each musical
            for musical_name, urls in data.items():
                print(f"\n🎭 Processing: {musical_name}")
                
                # Create musical
                musical = Musical(
                    name=musical_name,
                    description=f"Musical: {musical_name}",
                    is_available=True,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                db.session.add(musical)
                db.session.flush()  # Get the ID
                print(f"   ✅ Created musical: {musical_name} (ID: {musical.id})")
                
                # Add URLs
                url_count = 0
                for url in urls:
                    if isinstance(url, str):
                        link = MusicalLink(
                            musical_id=musical.id,
                            url=url,
                            is_available=True,
                            created_at=datetime.now(timezone.utc),
                            last_checked=datetime.now(timezone.utc)
                        )
                        db.session.add(link)
                        url_count += 1
                
                db.session.commit()
                print(f"   ✅ Added {url_count} URLs")
            
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

if __name__ == '__main__':
    migrate_urls()