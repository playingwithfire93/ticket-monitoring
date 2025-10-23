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
    FOTOS_DIR = BASE / "static" / "fotos"
    
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
                    process_musical(musical_name, urls, FOTOS_DIR)
                    
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
                            process_musical(musical_name, urls, FOTOS_DIR)
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

def get_musical_images(musical_name, fotos_dir):
    """Get images for a musical from the fotos directory"""
    images = []
    
    if not fotos_dir.exists():
        print(f"   ⚠️  Fotos directory not found: {fotos_dir}")
        return images
    
    # Normalize musical name for folder matching
    normalized_name = musical_name.lower().replace(' ', '_').replace('-', '_')
    
    # Look for folders that match the musical name
    for folder in fotos_dir.iterdir():
        if folder.is_dir():
            folder_name = folder.name.lower()
            # Match if folder name contains musical name or vice versa
            if normalized_name in folder_name or folder_name in normalized_name:
                print(f"   📸 Found image folder: {folder.name}")
                
                # Get all images from this folder
                for img_file in folder.iterdir():
                    if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                        # Use relative path from static folder
                        img_path = f"/static/fotos/{folder.name}/{img_file.name}"
                        images.append(img_path)
                
                break
    
    if not images:
        print(f"   ⚠️  No images found for {musical_name}")
        # Add placeholder image
        images = [f"https://via.placeholder.com/400x200/ff69b4/ffffff?text={musical_name.replace(' ', '+')}"]
    else:
        print(f"   ✅ Found {len(images)} images")
    
    return images

def process_musical(musical_name, urls, fotos_dir):
    """Process a single musical and its URLs"""
    print(f"\n🎭 Processing: {musical_name}")
    
    # Get images from fotos directory
    images = get_musical_images(musical_name, fotos_dir)
    
    # Create musical with images
    musical = Musical(
        name=musical_name,
        description=f"Musical: {musical_name}",
        images=images
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