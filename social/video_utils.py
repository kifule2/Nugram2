# social/video_utils.py
import os
import tempfile
import time
import logging
from moviepy.editor import VideoFileClip
import cloudinary.uploader

logger = logging.getLogger(__name__)

class VideoOptimizer:
    """Utility class to optimize videos for web playback"""
    
    @classmethod
    def optimize_video(cls, input_path, output_format='webm'):
        """
        Optimize video for web playback - aggressive compression for smaller size
        """
        try:
            temp_dir = tempfile.gettempdir()
            output_filename = f"optimized_{os.path.basename(input_path).split('.')[0]}.{output_format}"
            output_path = os.path.join(temp_dir, output_filename)
            
            video = VideoFileClip(input_path)
            
            metadata = {
                'duration': video.duration,
                'fps': video.fps,
                'size': video.size,
                'width': video.w,
                'height': video.h,
                'rotation': getattr(video, 'rotation', 0)
            }
            
            # Aggressive resizing for mobile
            if video.h > 720:
                video = video.resize(height=720)
                metadata['resized'] = True
                metadata['new_size'] = video.size
            
            # Reduce fps if too high
            if video.fps > 30:
                video = video.set_fps(30)
                metadata['fps_reduced'] = True
            
            # Aggressive compression settings
            if output_format == 'webm':
                settings = {
                    'codec': 'libvpx',
                    'audio_codec': 'libvorbis',
                    'bitrate': '500k',
                    'audio_bitrate': '64k',
                    'preset': 'medium',
                    'threads': 4
                }
            else:
                settings = {
                    'codec': 'libx264',
                    'audio_codec': 'aac',
                    'bitrate': '500k',
                    'audio_bitrate': '64k',
                    'preset': 'medium',
                    'threads': 4
                }
            
            video.write_videofile(
                output_path,
                codec=settings['codec'],
                audio_codec=settings['audio_codec'],
                bitrate=settings['bitrate'],
                audio_bitrate=settings['audio_bitrate'],
                preset=settings['preset'],
                threads=settings['threads'],
                logger=None
            )
            
            video.close()
            
            metadata['file_size'] = os.path.getsize(output_path)
            metadata['output_path'] = output_path
            metadata['format'] = output_format
            metadata['compression_ratio'] = f"{((1 - metadata['file_size'] / os.path.getsize(input_path)) * 100):.1f}%"
            
            return metadata
            
        except Exception as e:
            logger.error(f"Video optimization failed: {e}")
            return {
                'error': str(e),
                'original_path': input_path
            }
    
    @classmethod
    def extract_thumbnail(cls, video_path, time_in_seconds=1):
        """Extract thumbnail from video at specified time"""
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
    
    @classmethod
    def get_video_info(cls, video_path):
        """Get video metadata without optimization"""
        try:
            video = VideoFileClip(video_path)
            info = {
                'duration': video.duration,
                'fps': video.fps,
                'width': video.w,
                'height': video.h,
                'size': video.size,
                'rotation': getattr(video, 'rotation', 0)
            }
            video.close()
            return info
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            return None

    @classmethod
    def optimize_and_upload(cls, video_file, user_id):
        """
        Complete pipeline: optimize video and upload to Cloudinary
        """
        temp_input = None
        temp_output = None
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                for chunk in video_file.chunks():
                    tmp_file.write(chunk)
                temp_input = tmp_file.name
            
            video_info = cls.get_video_info(temp_input)
            result = cls.optimize_video(temp_input, output_format='webm')
            
            if 'error' in result:
                logger.warning(f"Optimization failed, uploading original: {result['error']}")
                upload_result = cloudinary.uploader.upload(
                    temp_input,
                    folder=f'nusu/users/{user_id}/videos',
                    resource_type='video',
                    transformation=[
                        {'quality': 'auto'},
                        {'fetch_format': 'auto'},
                        {'width': 720, 'height': 1280, 'crop': 'limit'}
                    ]
                )
                upload_result['optimized'] = False
            else:
                upload_result = cloudinary.uploader.upload(
                    result['output_path'],
                    folder=f'nusu/users/{user_id}/videos',
                    resource_type='video',
                    public_id=f"video_{int(time.time())}",
                    transformation=[
                        {'quality': 'auto'},
                        {'fetch_format': 'auto'}
                    ]
                )
                
                upload_result['duration'] = result.get('duration', 0)
                upload_result['optimized'] = True
                upload_result['original_size'] = video_file.size
                upload_result['optimized_size'] = result.get('file_size', 0)
                upload_result['compression_ratio'] = result.get('compression_ratio', '0%')
                
                thumb_path = cls.extract_thumbnail(result['output_path'])
                if thumb_path:
                    thumb_result = cloudinary.uploader.upload(
                        thumb_path,
                        folder=f'nusu/users/{user_id}/thumbnails',
                        transformation=[
                            {'width': 300, 'height': 300, 'crop': 'fill'},
                            {'quality': 'auto'}
                        ]
                    )
                    upload_result['thumbnail_url'] = thumb_result['secure_url']
                    os.unlink(thumb_path)
                
                temp_output = result['output_path']
            
            if video_info:
                upload_result['original_duration'] = video_info.get('duration', 0)
                upload_result['dimensions'] = f"{video_info.get('width', 0)}x{video_info.get('height', 0)}"
            
            return upload_result
            
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            raise
        finally:
            if temp_input and os.path.exists(temp_input):
                os.unlink(temp_input)
            if temp_output and os.path.exists(temp_output):
                os.unlink(temp_output)