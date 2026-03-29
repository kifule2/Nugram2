import os
import tempfile
import time
import logging
from moviepy import VideoFileClip  # Changed from moviepy.editor
import cloudinary.uploader

logger = logging.getLogger(__name__)

class VideoOptimizer:
    @staticmethod
    def optimize_video(video_path, output_format='mp4'):
        try:
            video = VideoFileClip(video_path)
            
            # Get video info
            duration = video.duration
            width = video.w
            height = video.h
            
            # Create output path
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"optimized_{os.path.basename(video_path)}.{output_format}")
            
            # Write video with compression
            video.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                bitrate='500k',
                preset='medium'
            )
            
            video.close()
            
            return {
                'output_path': output_path,
                'duration': duration,
                'width': width,
                'height': height,
                'size': os.path.getsize(output_path)
            }
        except Exception as e:
            logger.error(f"Video optimization failed: {e}")
            return {'error': str(e), 'output_path': video_path}
    
    @staticmethod
    def extract_thumbnail(video_path, time_in_seconds=1):
        try:
            video = VideoFileClip(video_path)
            frame = video.get_frame(time_in_seconds)
            
            temp_dir = tempfile.gettempdir()
            thumb_path = os.path.join(temp_dir, f"thumb_{os.path.basename(video_path)}.jpg")
            
            from PIL import Image
            import numpy as np
            img = Image.fromarray(np.uint8(frame))
            img.save(thumb_path, 'JPEG', quality=85)
            
            video.close()
            return thumb_path
        except Exception as e:
            logger.error(f"Thumbnail extraction failed: {e}")
            return None
    
    @staticmethod
    def get_video_info(video_path):
        try:
            video = VideoFileClip(video_path)
            info = {
                'duration': video.duration,
                'width': video.w,
                'height': video.h,
                'fps': video.fps,
                'size': os.path.getsize(video_path)
            }
            video.close()
            return info
        except Exception as e:
            logger.error(f"Video info extraction failed: {e}")
            return {'duration': 0, 'width': 0, 'height': 0}