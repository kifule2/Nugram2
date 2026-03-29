# ============================================
# COMPLETE VIDEO UPLOAD TEST
# Run this in Django shell: python manage.py shell
# ============================================

import os
import sys
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nusu.settings')
django.setup()

import cloudinary
import cloudinary.uploader
import cloudinary.api
from django.contrib.auth import get_user_model
from social.models import Post, PostMedia, BackgroundTemplate
import requests
from io import BytesIO
import time

User = get_user_model()

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
    secure=True
)

print("\n" + "="*60)
print("🔧 VIDEO UPLOAD DIAGNOSTIC TEST")
print("="*60)

# ============================================
# TEST 1: Check Cloudinary Connection
# ============================================
print("\n📡 TEST 1: Cloudinary Connection")
print("-" * 40)

try:
    result = cloudinary.api.ping()
    print(f"✅ Connected! Status: {result.get('status', 'OK')}")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    exit()

# ============================================
# TEST 2: Get Current Account Info
# ============================================
print("\n📊 TEST 2: Account Usage")
print("-" * 40)

try:
    usage = cloudinary.api.usage()
    print(f"   Plan: {usage.get('plan', 'Unknown')}")
    print(f"   Images: {usage.get('images', 0)}")
    print(f"   Videos: {usage.get('videos', 0)}")
    print(f"   Storage: {usage.get('storage', {}).get('used', 0) / (1024*1024):.2f} MB")
except Exception as e:
    print(f"⚠️ Could not get usage: {e}")

# ============================================
# TEST 3: Upload a Small Test Video
# ============================================
print("\n🎬 TEST 3: Upload Test Video")
print("-" * 40)

# Multiple video sources to try
video_sources = [
    "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4",
    "https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
]

video_data = None
video_source = None

for source in video_sources:
    print(f"   Trying: {source[:50]}...")
    try:
        response = requests.get(source, timeout=15)
        if response.status_code == 200:
            video_data = BytesIO(response.content)
            video_source = source
            print(f"   ✅ Downloaded {len(response.content) / (1024*1024):.2f} MB")
            break
        else:
            print(f"   ⚠️ HTTP {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Failed: {str(e)[:50]}...")
        continue

if not video_data:
    print("   ❌ Could not download test video from any source")
else:
    try:
        timestamp = int(time.time())
        folder_path = f"nusu/users/test/videos"
        public_id = f"test_video_{timestamp}"
        
        print(f"   📁 Uploading to: {folder_path}")
        
        upload_result = cloudinary.uploader.upload(
            video_data,
            folder=folder_path,
            public_id=public_id,
            resource_type='video',
            overwrite=True,
            quality='auto'
        )
        
        print(f"   ✅ Upload successful!")
        print(f"      URL: {upload_result['secure_url']}")
        print(f"      Public ID: {upload_result['public_id']}")
        print(f"      Resource Type: {upload_result['resource_type']}")
        print(f"      Duration: {upload_result.get('duration', 'N/A')} seconds")
        print(f"      Format: {upload_result.get('format', 'N/A')}")
        
        # Test thumbnail generation
        try:
            thumbnail = cloudinary.utils.cloudinary_url(
                upload_result['public_id'],
                resource_type='video',
                transformation=[
                    {'width': 300, 'height': 300, 'crop': 'fill'},
                    {'start_offset': 1}
                ],
                format='jpg'
            )[0]
            print(f"      Thumbnail URL: {thumbnail}")
        except Exception as e:
            print(f"      ⚠️ Thumbnail generation: {e}")
        
        # Clean up
        cloudinary.uploader.destroy(upload_result['public_id'], resource_type='video')
        print(f"      ✅ Test video cleaned up")
        
    except Exception as e:
        print(f"   ❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()

# ============================================
# TEST 4: Check Existing Posts
# ============================================
print("\n📝 TEST 4: Check Existing Posts")
print("-" * 40)

try:
    from social.models import Post, PostMedia
    
    recent_posts = Post.objects.filter(post_type__in=['media', 'mixed']).order_by('-created_at')[:5]
    
    if recent_posts:
        print(f"   Found {recent_posts.count()} recent media posts:")
        for post in recent_posts:
            print(f"\n   Post #{post.id} (User: {post.user.username})")
            print(f"      Created: {post.created_at}")
            print(f"      Type: {post.post_type}")
            
            for media in post.media_items.all():
                print(f"\n      📎 Media ID: {media.id}")
                print(f"         Type: {media.media_type}")
                print(f"         Is Video: {media.is_video}")
                print(f"         Is Image: {media.is_image}")
                print(f"         Has Video Field: {bool(media.video)}")
                print(f"         Has Image Field: {bool(media.image)}")
                print(f"         URL: {media.url}")
                print(f"         Thumbnail: {media.thumbnail_url}")
                print(f"         Public ID: {media.public_id}")
                
                # Test if URL is accessible
                if media.url:
                    try:
                        r = requests.head(media.url, timeout=5)
                        print(f"         URL Status: HTTP {r.status_code} {'✅' if r.status_code == 200 else '❌'}")
                    except:
                        print(f"         URL Status: ❌ Not accessible")
    else:
        print("   No media posts found")
        
except Exception as e:
    print(f"   ❌ Error checking posts: {e}")

# ============================================
# TEST 5: Check Cloudinary Folders
# ============================================
print("\n📁 TEST 5: Check Cloudinary Folder Structure")
print("-" * 40)

try:
    # Check for nusu folder
    nusu_resources = cloudinary.api.resources(
        prefix="nusu/",
        max_results=20
    )
    
    if nusu_resources['resources']:
        print(f"   Found {len(nusu_resources['resources'])} resources in nusu/:")
        for r in nusu_resources['resources'][:5]:
            print(f"      - {r['public_id']} ({r['resource_type']})")
    else:
        print("   ℹ️ No resources found in nusu/ folder")
    
    # Check for any videos
    videos = cloudinary.api.resources(
        resource_type='video',
        max_results=20
    )
    
    if videos['resources']:
        print(f"\n   Found {len(videos['resources'])} total videos:")
        for v in videos['resources'][:5]:
            print(f"      - {v['public_id']}")
            print(f"        URL: {v['secure_url']}")
            print(f"        Duration: {v.get('duration', 'N/A')} sec")
    else:
        print(f"\n   ℹ️ No videos found in your Cloudinary account")
        
except Exception as e:
    print(f"   ❌ Error checking folders: {e}")

# ============================================
# TEST 6: Check Model Properties
# ============================================
print("\n🔧 TEST 6: Check PostMedia Model Properties")
print("-" * 40)

try:
    from social.models import PostMedia
    
    # Get a sample media item
    sample_media = PostMedia.objects.filter(media_type='video').first()
    
    if sample_media:
        print(f"   Sample Media ID: {sample_media.id}")
        print(f"   Media Type: {sample_media.media_type}")
        print(f"   is_video: {sample_media.is_video}")
        print(f"   is_image: {sample_media.is_image}")
        print(f"   has video field: {bool(sample_media.video)}")
        print(f"   has image field: {bool(sample_media.image)}")
        print(f"   URL: {sample_media.url}")
        print(f"   Thumbnail URL: {sample_media.thumbnail_url}")
    else:
        print("   No video media found in database")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

# ============================================
# SUMMARY
# ============================================
print("\n" + "="*60)
print("📋 SUMMARY")
print("="*60)

print("""
If video uploads are failing, check:

1. Cloudinary Settings:
   - Verify CLOUDINARY_STORAGE in settings.py
   - Ensure RESOURCE_TYPE = 'auto' is set

2. Model Properties:
   - Make sure is_video property uses: self.media_type == 'video' or self.video is not None
   - Ensure media_type is set to 'video' when saving

3. View Logic:
   - Check that resource_type='video' is used for video uploads
   - Verify folder path: nusu/users/{user_id}/videos/

4. Template Display:
   - Use {% if media.is_video %} for video tags
   - Use {% if media.is_image %} for image tags

5. Quick Fix:
   - Run: python manage.py shell
   - Execute: from social.models import PostMedia
   - For each media item, set media.media_type = 'video' if it has video field
   - Save: media.save()
""")

print("\n✅ Test complete!")