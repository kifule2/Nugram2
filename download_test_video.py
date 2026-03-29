# download_test_video.py
import os
import requests
from pathlib import Path

# Create media/test_videos directory
media_dir = Path('media/test_videos')
media_dir.mkdir(parents=True, exist_ok=True)

# Video URLs (multiple options for reliability)
video_urls = [
    {
        'url': 'https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4',
        'name': 'big_buck_bunny_720p_10s.mp4',
        'size_mb': 1
    },
    {
        'url': 'https://storage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
        'name': 'for_bigger_blazes.mp4',
        'size_mb': 15
    },
    {
        'url': 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
        'name': 'flower_video.mp4',
        'size_mb': 0.5
    },
    {
        'url': 'https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4',
        'name': 'big_buck_bunny_720p_1mb.mp4',
        'size_mb': 1
    }
]

print("\n" + "="*60)
print("📥 DOWNLOADING TEST VIDEOS")
print("="*60)

for video in video_urls:
    filepath = media_dir / video['name']
    
    # Skip if file already exists
    if filepath.exists():
        print(f"⏭️  {video['name']} already exists - skipping")
        continue
    
    print(f"\n📹 Downloading: {video['name']} ({video['size_mb']} MB)")
    print(f"   From: {video['url']}")
    
    try:
        response = requests.get(video['url'], stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r   Progress: {percent:.1f}%", end='')
        
        print(f"\n   ✅ Saved to: {filepath}")
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")

print("\n" + "="*60)
print("✅ Download complete!")
print(f"📁 Videos saved to: {media_dir.absolute()}")
print("="*60)

# List downloaded files
print("\n📋 Downloaded files:")
for file in media_dir.glob('*.mp4'):
    size_mb = file.stat().st_size / (1024 * 1024)
    print(f"   • {file.name} - {size_mb:.2f} MB")