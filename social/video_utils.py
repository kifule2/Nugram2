import os
import tempfile
import time
import logging
from moviepy import VideoFileClip
import cloudinary.uploader

logger = logging.getLogger(__name__)

class VideoOptimizer:
    """Video optimization with VP9 WebM support"""
    
    @staticmethod
    def optimize_video(video_path, output_format='webm', quality='balanced'):
        """
        Optimize video for web with VP9 codec
        
        Args:
            video_path: Path to input video
            output_format: 'webm' (VP9) or 'mp4' (H.264)
            quality: 'fast', 'balanced', 'best'
        """
        try:
            video = VideoFileClip(video_path)
            duration = video.duration
            width = video.w
            height = video.h
            
            # Auto-resize if too large (max 720p for mobile)
            if height > 720:
                video = video.resize(height=720)
                logger.info(f"Resized video from {height}p to 720p")
            
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"optimized_{int(time.time())}_{os.path.basename(video_path)}.{output_format}")
            
            # Quality presets
            presets = {
                'fast': {
                    'bitrate': '400k',
                    'preset': 'ultrafast',
                    'crf': 35
                },
                'balanced': {
                    'bitrate': '500k',
                    'preset': 'medium',
                    'crf': 30
                },
                'best': {
                    'bitrate': '800k',
                    'preset': 'slow',
                    'crf': 25
                }
            }
            
            preset = presets.get(quality, presets['balanced'])
            
            if output_format == 'webm':
                # VP9 WebM encoding
                video.write_videofile(
                    output_path,
                    codec='libvpx-vp9',
                    audio_codec='libopus',
                    bitrate=preset['bitrate'],
                    audio_bitrate='128k',
                    preset=preset['preset'],
                    threads=2,
                    ffmpeg_params=[
                        '-crf', str(preset['crf']),
                        '-pix_fmt', 'yuv420p',
                        '-row-mt', '1',
                        '-deadline', 'good'
                    ]
                )
                logger.info(f"Video converted to VP9 WebM: {output_path}")
            else:
                # H.264 MP4 fallback
                video.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate=preset['bitrate'],
                    audio_bitrate='128k',
                    preset=preset['preset'],
                    ffmpeg_params=['-crf', str(preset['crf'])]
                )
                logger.info(f"Video converted to H.264 MP4: {output_path}")
            
            video.close()
            
            file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
            
            return {
                'output_path': output_path,
                'duration': duration,
                'width': width,
                'height': height,
                'size_mb': round(file_size_mb, 2),
                'format': output_format,
                'codec': 'vp9' if output_format == 'webm' else 'h264',
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Video optimization failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'output_path': video_path
            }
    
    @staticmethod
    def trim_video(video_path, start_time, end_time, output_format='webm'):
        """Trim video to specified time range"""
        try:
            clip = VideoFileClip(video_path)
            trimmed = clip.subclipped(start_time, end_time)
            
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"trimmed_{int(time.time())}.{output_format}")
            
            if output_format == 'webm':
                trimmed.write_videofile(
                    output_path,
                    codec='libvpx-vp9',
                    audio_codec='libopus',
                    bitrate='500k',
                    preset='medium',
                    threads=2
                )
            else:
                trimmed.write_videofile(
                    output_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate='500k',
                    preset='medium'
                )
            
            clip.close()
            trimmed.close()
            
            return {
                'success': True,
                'output_path': output_path,
                'duration': end_time - start_time,
                'format': output_format
            }
            
        except Exception as e:
            logger.error(f"Video trim failed: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_video_info(video_path):
        """Get video metadata without processing"""
        try:
            video = VideoFileClip(video_path)
            info = {
                'duration': video.duration,
                'width': video.w,
                'height': video.h,
                'fps': video.fps,
                'size_mb': os.path.getsize(video_path) / (1024 * 1024)
            }
            video.close()
            return info
        except Exception as e:
            logger.error(f"Video info extraction failed: {e}")
            return {'error': str(e)}