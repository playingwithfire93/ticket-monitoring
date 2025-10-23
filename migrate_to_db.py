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
        
        # Show available folders
        if FOTOS_DIR.exists():
            print(f"\n📂 Available image folders:")
            for folder in sorted(FOTOS_DIR.iterdir()):
                if folder.is_dir():
                    img_count = len([f for f in folder.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']])
                    print(f"   - {folder.name} ({img_count} images)")
        
        with app.app_context():
            # Clear existing data
            print("\n🗑️  Clearing existing data...")
            MusicalLink.query.delete()
            Musical.query.delete()
            db.session.commit()
            
            # Handle different JSON formats
            if isinstance(data, dict):
                print("📋 Processing dictionary format...")
                for musical_name, urls in data.items():
                    process_musical(musical_name, urls, FOTOS_DIR)
                    
            elif isinstance(data, list):
                print("📋 Processing list format...")
                for item in data:
                    if isinstance(item, dict):
                        musical_name = item.get('musical') or item.get('name') or item.get('siteName')
                        urls = item.get('urls') or item.get('url') or []
                        
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
    
    # Manual mapping for special cases (nombres exactos del JSON → nombre de carpeta)
    FOLDER_MAPPING = {
        'Les Misérables': 'les_mis',
        'Les Miserables': 'les_mis',
        'The Book of Mormon': 'book_of_mormon',
        'Book of Mormon': 'book_of_mormon',
        'Wicked': 'wicked',
        'WICKED': 'wicked'
        # Añade más mappings aquí según tus carpetas
    }
    
    print(f"   🔍 Searching images for: '{musical_name}'")
    
    # Check manual mapping first (case-insensitive)
    folder_name = None
    for key, value in FOLDER_MAPPING.items():
        if key.lower() == musical_name.lower():
            folder_name = value
            break
    
    if folder_name:
        matched_folder = fotos_dir / folder_name
        if matched_folder.exists() and matched_folder.is_dir():
            print(f"   ✅ Found via mapping: {matched_folder.name}")
        else:
            print(f"   ⚠️  Mapped folder not found: {folder_name}")
            matched_folder = None
    else:
        # Try automatic matching if no manual mapping exists
        matched_folder = None
        normalized_name = musical_name.lower()
        # Remove common words and special characters
        normalized_name = normalized_name.replace('the ', '').replace(' ', '_').replace('-', '_').replace("'", '')
        
        print(f"   🔍 Normalized: '{normalized_name}'")
        
        for folder in fotos_dir.iterdir():
            if folder.is_dir():
                folder_normalized = folder.name.lower().replace('-', '_').replace("'", '')
                
                # Check if normalized names match
                if (normalized_name in folder_normalized or 
                    folder_normalized in normalized_name or
                    normalized_name == folder_normalized):
                    matched_folder = folder
                    print(f"   ✅ Auto-matched: {folder.name}")
                    break
    
    if matched_folder and matched_folder.exists():
        # Get all images from this folder
        for img_file in sorted(matched_folder.iterdir()):
            if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                img_path = f"/static/fotos/{matched_folder.name}/{img_file.name}"
                images.append(img_path)
                print(f"      📸 {img_file.name}")
    
    if not images:
        print(f"   ⚠️  No images found, using placeholder")
        images = [f"https://via.placeholder.com/400x200/ff69b4/ffffff?text={musical_name.replace(' ', '+')}"]
    else:
        print(f"   ✅ Loaded {len(images)} images")
    
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
    print(f"   ✅ Created musical ID: {musical.id}")
    
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