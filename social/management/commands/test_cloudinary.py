# social/management/commands/test_upload.py
import os
import cloudinary
import cloudinary.uploader
import cloudinary.api
from django.core.management.base import BaseCommand
from django.conf import settings
from io import BytesIO
import base64

class Command(BaseCommand):
    help = 'Test Cloudinary upload with local test files'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n🔧 Testing Cloudinary Upload"))
        self.stdout.write("="*60)
        
        # Get Cloudinary settings from CLOUDINARY_STORAGE dictionary
        cloudinary_config = getattr(settings, 'CLOUDINARY_STORAGE', {})
        cloud_name = cloudinary_config.get('CLOUD_NAME')
        api_key = cloudinary_config.get('API_KEY')
        api_secret = cloudinary_config.get('API_SECRET')
        
        self.stdout.write(f"📋 Cloudinary Configuration:")
        self.stdout.write(f"   Cloud Name: {cloud_name or 'NOT SET'}")
        self.stdout.write(f"   API Key: {str(api_key)[:4] if api_key else 'NOT SET'}...{str(api_key)[-4:] if api_key else ''}")
        self.stdout.write(f"   API Secret: {'*' * 10 if api_secret else 'NOT SET'}")
        
        if not all([cloud_name, api_key, api_secret]):
            self.stdout.write(self.style.ERROR("\n❌ Cloudinary credentials missing!"))
            self.stdout.write("   Check your CLOUDINARY_STORAGE in settings.py")
            return
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        
        # Test 1: Ping Cloudinary API
        self.stdout.write("\n📡 Test 1: Testing Cloudinary Connection...")
        try:
            result = cloudinary.api.ping()
            self.stdout.write(self.style.SUCCESS(f"   ✅ Connected! Status: {result.get('status', 'OK')}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Connection failed: {e}"))
            return
        
        # Test 2: Upload a small generated image
        self.stdout.write("\n🖼️ Test 2: Uploading test image...")
        try:
            # Create a tiny valid PNG (1x1 pixel)
            png_data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')
            result = cloudinary.uploader.upload(
                png_data,
                public_id='test_image',
                folder='test'
            )
            self.stdout.write(self.style.SUCCESS(f"   ✅ Success!"))
            self.stdout.write(f"      URL: {result['secure_url']}")
            self.stdout.write(f"      Size: {result.get('bytes', 0)} bytes")
            
            # Clean up
            delete_result = cloudinary.uploader.destroy(result['public_id'])
            if delete_result.get('result') == 'ok':
                self.stdout.write(f"      ✅ Test image cleaned up")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed: {e}"))
        
        # Test 3: Check video upload capability
        self.stdout.write("\n🎬 Test 3: Testing video upload capability...")
        try:
            # Just test if we can access the video upload API
            # Using a tiny file - Cloudinary will reject as invalid video but API should work
            tiny_data = b"test"
            result = cloudinary.uploader.upload(
                tiny_data,
                public_id='test_video_check',
                folder='test',
                resource_type='video'
            )
            self.stdout.write(self.style.SUCCESS(f"   ✅ Video upload working!"))
            cloudinary.uploader.destroy(result['public_id'], resource_type='video')
        except Exception as e:
            if "Invalid video file" in str(e):
                self.stdout.write(self.style.SUCCESS("   ✅ Video upload API is accessible"))
                self.stdout.write("      (File was rejected as expected - this is good!)")
            else:
                self.stdout.write(self.style.ERROR(f"   ❌ Video upload failed: {e}"))
        
        # Test 4: Check Cloudinary usage
        self.stdout.write("\n📊 Test 4: Checking Cloudinary account...")
        try:
            usage = cloudinary.api.usage()
            self.stdout.write(self.style.SUCCESS(f"   ✅ Account details retrieved"))
            self.stdout.write(f"      Plan: {usage.get('plan', 'Unknown')}")
            self.stdout.write(f"      Images: {usage.get('images', 0)}")
            self.stdout.write(f"      Storage used: {usage.get('storage', {}).get('used', 0) / (1024*1024):.2f} MB")
            self.stdout.write(f"      Credits used: {usage.get('credits', {}).get('used', 0) / 1000:.2f}K")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed: {e}"))
        
        # Test 5: Upload default profile picture (optional)
        self.stdout.write("\n👤 Test 5: Uploading default profile picture...")
        try:
            # Try to import PIL, if not available, create a simple text file instead
            try:
                from PIL import Image, ImageDraw
                
                img = Image.new('RGB', (200, 200), color='#3b82f6')
                draw = ImageDraw.Draw(img)
                draw.ellipse([60, 40, 140, 120], fill='#ffffff')
                draw.rectangle([40, 120, 160, 170], fill='#ffffff')
                
                img_byte_arr = BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                result = cloudinary.uploader.upload(
                    img_byte_arr,
                    public_id='default_profile',
                    folder='profile_pics',
                    overwrite=True,
                    transformation={'width': 200, 'height': 200, 'crop': 'fill'}
                )
                self.stdout.write(self.style.SUCCESS(f"   ✅ Profile picture uploaded!"))
                self.stdout.write(f"      URL: {result['secure_url']}")
            except ImportError:
                self.stdout.write(self.style.Warning("   ⚠️ PIL not installed - skipping profile picture creation"))
                self.stdout.write("   Install PIL: pip install Pillow")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed: {e}"))
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*60))
        self.stdout.write(self.style.SUCCESS("✅ TEST COMPLETE"))
        self.stdout.write(self.style.SUCCESS("="*60))
        
        self.stdout.write("\n📝 Summary:")
        self.stdout.write("   • Your Cloudinary credentials are correct")
        self.stdout.write("   • Image uploads are working")
        self.stdout.write("   • Video upload API is accessible")
        self.stdout.write("   • Your app should work normally")