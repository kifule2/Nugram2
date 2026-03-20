from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
import cloudinary
import cloudinary.uploader
import cloudinary.api
import requests
from io import BytesIO
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Directly test video upload to Cloudinary'

    def handle(self, *args, **options):
        self.stdout.write("\n🔧 DIRECT VIDEO UPLOAD TEST")
        self.stdout.write("=" * 60)
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
            api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
            api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
            secure=True
        )
        
        self.stdout.write(f"✅ Cloud Name: {settings.CLOUDINARY_STORAGE['CLOUD_NAME']}")
        
        # Test 1: Check if we can upload ANY file
        self.stdout.write("\n📁 Test 1: Basic folder creation test")
        try:
            test_content = b"test file content"
            result = cloudinary.uploader.upload(
                test_content,
                folder="nusu/test_folder",
                public_id="test_file",
                resource_type='raw',
                overwrite=True
            )
            self.stdout.write(self.style.SUCCESS(f"   ✅ Raw upload successful!"))
            self.stdout.write(f"      Public ID: {result['public_id']}")
            self.stdout.write(f"      URL: {result['secure_url']}")
            
            # Clean up
            cloudinary.uploader.destroy(result['public_id'], resource_type='raw')
            self.stdout.write(f"      ✅ Cleaned up")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed: {e}"))
        
        # Test 2: Upload a real video
        self.stdout.write("\n🎬 Test 2: Real video upload test")
        video_url = "https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4"
        
        try:
            self.stdout.write(f"   Downloading test video...")
            response = requests.get(video_url, timeout=30)
            
            if response.status_code == 200:
                video_data = BytesIO(response.content)
                video_size = len(response.content) / (1024 * 1024)
                self.stdout.write(f"   ✅ Downloaded: {video_size:.2f} MB")
                
                # Upload with explicit folder
                result = cloudinary.uploader.upload(
                    video_data,
                    folder="nusu/users/test/videos",
                    public_id="test_video",
                    resource_type='video',
                    overwrite=True
                )
                
                self.stdout.write(self.style.SUCCESS(f"   ✅ Video upload successful!"))
                self.stdout.write(f"      Public ID: {result['public_id']}")
                self.stdout.write(f"      URL: {result['secure_url']}")
                self.stdout.write(f"      Resource Type: {result['resource_type']}")
                
                # Check if folder exists
                folder_check = cloudinary.api.resources(
                    prefix="nusu/users/test/",
                    max_results=10
                )
                self.stdout.write(f"      Files in folder: {len(folder_check['resources'])}")
                
                # Clean up
                cloudinary.uploader.destroy(result['public_id'], resource_type='video')
                self.stdout.write(f"      ✅ Cleaned up")
            else:
                self.stdout.write(self.style.ERROR(f"   ❌ Download failed: HTTP {response.status_code}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Video upload failed: {e}"))
        
        # Test 3: List all resources
        self.stdout.write("\n📊 Test 3: Current Cloudinary resources")
        try:
            # Check nusu folder
            nusu_resources = cloudinary.api.resources(
                prefix="nusu/",
                max_results=20
            )
            
            if nusu_resources['resources']:
                self.stdout.write(f"   Found {len(nusu_resources['resources'])} resources in nusu/:")
                for r in nusu_resources['resources']:
                    self.stdout.write(f"      - {r['public_id']} ({r['resource_type']})")
            else:
                self.stdout.write(f"   ℹ️ No resources found in nusu/ folder")
            
            # Check all videos
            videos = cloudinary.api.resources(
                resource_type='video',
                max_results=20
            )
            self.stdout.write(f"\n   Total videos in account: {len(videos['resources'])}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error listing resources: {e}"))
        
        self.stdout.write("\n" + "=" * 60)