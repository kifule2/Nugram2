import cloudinary
import cloudinary.uploader
from django.conf import settings

# Configure cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
    secure=True
)

# Test upload with explicit folder
try:
    result = cloudinary.uploader.upload(
        "https://ui-avatars.com/api/?name=Test&background=3b82f6&color=fff&size=100",
        folder="nusu/test_folder",
        public_id="test_image",
        overwrite=True
    )
    print("✅ SUCCESS!")
    print(f"URL: {result['secure_url']}")
    print(f"Public ID: {result['public_id']}")
except Exception as e:
    print(f"❌ ERROR: {e}")