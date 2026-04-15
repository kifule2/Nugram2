import cloudinary.uploader
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class VideoOptimizer:
    
    @staticmethod
    def upload_video(video_file, user_id, options=None):
        """
        Upload original video to Cloudinary
        Cloudinary handles ALL processing: trim, mute, VP9 conversion
        No backend CPU usage!
        """
        if options is None:
            options = {}
        
        start_time = options.get('start_time', 0)
        end_time = options.get('end_time')
        mute_audio = options.get('mute_audio', False)
        
        # Build Cloudinary transformations (applied on their servers)
        transformations = []
        
        # 1. Trim video (Cloudinary does this)
        if start_time > 0 or end_time:
            trim = {}
            if start_time > 0:
                trim['start_offset'] = start_time
            if end_time:
                trim['end_offset'] = end_time
            transformations.append(trim)
        
        # 2. Mute audio (Cloudinary does this)
        if mute_audio:
            transformations.append({"audio": "mute"})
        
        # 3. VP9 conversion (Cloudinary does this)
        transformations.append({
            "format": "webm",
            "codec": "vp9",
            "quality": "auto"
        })
        
        # Upload original video - Cloudinary processes transformations asynchronously
        upload_result = cloudinary.uploader.upload(
            video_file,
            resource_type='video',
            folder=f'nusu/users/{user_id}/videos',
            eager=transformations,
            eager_async=True,  # Don't wait - processes in background
            timeout=120,
            invalidate=True  # Force CDN to refresh when ready
        )
        
        return {
            'success': True,
            'public_id': upload_result['public_id'],
            'original_url': upload_result['secure_url'],
            'duration': upload_result.get('duration'),
            'size_bytes': upload_result.get('bytes'),
            'format': upload_result.get('format'),
            'conversion_queued': True
        }
    
    @staticmethod
    def get_processed_url(public_id, start_time=0, end_time=None, mute_audio=False):
        """
        Generate URL with transformations (trim, mute, VP9)
        Useful for displaying video before async conversion completes
        """
        from cloudinary import CloudinaryImage
        
        transformations = []
        
        if start_time > 0 or end_time:
            trim = {}
            if start_time > 0:
                trim['start_offset'] = start_time
            if end_time:
                trim['end_offset'] = end_time
            transformations.append(trim)
        
        if mute_audio:
            transformations.append({"audio": "mute"})
        
        transformations.append({"format": "webm", "codec": "vp9"})
        
        image = CloudinaryImage(public_id)
        return image.build_url(
            resource_type='video',
            transformation=transformations,
            sign_url=True
        )
    
    @staticmethod
    def get_video_info(public_id):
        """
        Get video info from Cloudinary (duration, format, etc.)
        """
        from cloudinary.api import resource
        
        try:
            info = resource(public_id, resource_type='video')
            return {
                'duration': info.get('duration'),
                'format': info.get('format'),
                'size': info.get('bytes'),
                'width': info.get('width'),
                'height': info.get('height')
            }
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return None