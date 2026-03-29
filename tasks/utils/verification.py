"""
Main verification service - async with proper error handling
"""
import asyncio
import logging
from typing import Tuple, Optional
from . import twitter, youtube, tiktok, custom

logger = logging.getLogger(__name__)


class VerificationService:
    """Main verification handler with async support"""
    
    @staticmethod
    async def verify(completion) -> Tuple[Optional[bool], dict]:
        """
        Verify a task completion asynchronously
        Returns: (verified: bool, data: dict)
        """
        task = completion.task
        user = completion.user
        
        # Mark as processing
        completion.status = 'processing'
        completion.save()
        
        try:
            # Route based on task type
            if task.task_type == 'twitter' or task.platform == 'twitter':
                result = await VerificationService._verify_twitter(completion)
            elif task.task_type == 'youtube' or task.platform == 'youtube':
                result = await VerificationService._verify_youtube(completion)
            elif task.task_type == 'tiktok' or task.platform == 'tiktok':
                result = await VerificationService._verify_tiktok(completion)
            elif task.task_type == 'custom' or task.platform == 'custom':
                result = await VerificationService._verify_custom(completion)
            else:
                result = (None, {'error': 'Unknown platform', 'needs_manual_review': True})
            
            verified, data = result
            
            # Store verification data
            completion.verification_data = data
            completion.save()
            
            if verified:
                completion.verify()
                return True, data
            elif verified is False:
                completion.fail(data.get('reason', 'Verification failed'))
                return False, data
            else:
                # Needs manual review or retry
                completion.status = 'pending'
                completion.save()
                
                # If needs_manual_review flag is set, notify creator
                if data.get('needs_manual_review'):
                    from users.models import Notification
                    Notification.objects.create(
                        user=task.created_by,
                        message=f"⚠️ Manual review needed for {user.username}'s submission for '{task.name}'",
                        notification_type='manual_review_needed'
                    )
                
                return None, data
                
        except Exception as e:
            logger.error(f"Verification error: {e}")
            completion.status = 'pending'
            completion.save()
            return None, {'error': str(e), 'needs_manual_review': True}
    
    @staticmethod
    async def _verify_twitter(completion):
        """Twitter verification"""
        task = completion.task
        user = completion.user
        
        # Get user's Twitter handle
        try:
            profile = user.social_profiles.get(platform='twitter')
            user_handle = profile.handle.replace('@', '').strip()
        except:
            return None, {'error': 'No Twitter account linked', 'needs_manual_review': True}
        
        if task.action == 'follow':
            target = task.target_identifier.replace('@', '').strip()
            return await twitter.verify_follow(user_handle, target)
        
        elif task.action == 'like':
            return await twitter.verify_like(user_handle, task.target_url)
        
        else:
            return None, {'error': f'Unsupported action: {task.action}'}
    
    @staticmethod
    async def _verify_youtube(completion):
        """YouTube verification"""
        task = completion.task
        user = completion.user
        
        # Get user's YouTube handle/channel ID
        try:
            profile = user.social_profiles.get(platform='youtube')
            user_handle = profile.handle.strip()
        except:
            return None, {'error': 'No YouTube account linked', 'needs_manual_review': True}
        
        if task.action == 'comment':
            return await youtube.verify_comment(user_handle, task.target_url)
        
        elif task.action == 'watch':
            required_seconds = task.task_data.get('required_seconds', 30)
            watch_time = completion.submission_data.get('watch_time', 0)
            if watch_time >= required_seconds:
                return True, {'watch_time': watch_time, 'required': required_seconds}
            else:
                return None, {'watch_time': watch_time, 'required': required_seconds}
        
        elif task.action == 'subscribe':
            target = task.target_identifier
            return await youtube.verify_subscribe(user_handle, target)
        
        else:
            return None, {'error': f'Unsupported action: {task.action}'}
    
    @staticmethod
    async def _verify_tiktok(completion):
        """TikTok verification with cooldown"""
        task = completion.task
        user = completion.user
        
        # Get user's TikTok handle
        try:
            profile = user.social_profiles.get(platform='tiktok')
            user_handle = profile.handle.replace('@', '').strip()
        except:
            return None, {'error': 'No TikTok account linked', 'needs_manual_review': True}
        
        target = task.target_identifier.replace('@', '').strip()
        
        # Check if user clicked the link
        if not completion.submission_data.get('clicked'):
            return None, {'message': 'Click the link to complete this task'}
        
        return await tiktok.verify_follow(user_handle, target, completion)
    
    @staticmethod
    async def _verify_custom(completion):
        """Custom URL verification"""
        task = completion.task
        keyword = task.task_data.get('keyword', '')
        target_url = task.target_url
        
        if keyword:
            return await custom.verify_url_contains(target_url, keyword)
        
        # If no keyword, check if they clicked
        if completion.submission_data.get('clicked'):
            return True, {'clicked_at': completion.submission_data.get('clicked_at')}
        
        return None, {'message': 'Visit the link to complete this task'}
    
    
    @staticmethod
    async def verify_batch(completions):
        """
        Batch verify multiple completions
        Groups by video/target to save requests
        """
        # Group by platform and target
        twitter_targets = {}
        youtube_videos = {}
        tiktok_targets = {}
        
        for completion in completions:
            task = completion.task
            if task.platform == 'twitter':
                target = task.target_identifier
                if target not in twitter_targets:
                    twitter_targets[target] = []
                twitter_targets[target].append(completion)
            
            elif task.platform == 'youtube' and task.action == 'comment':
                url = task.target_url
                if url not in youtube_videos:
                    youtube_videos[url] = []
                youtube_videos[url].append(completion)
            
            elif task.platform == 'tiktok':
                target = task.target_identifier
                if target not in tiktok_targets:
                    tiktok_targets[target] = []
                tiktok_targets[target].append(completion)
        
        # Process in parallel
        tasks = []
        
        for target, completions_list in twitter_targets.items():
            tasks.append(VerificationService._batch_twitter(target, completions_list))
        
        for url, completions_list in youtube_videos.items():
            tasks.append(VerificationService._batch_youtube(url, completions_list))
        
        for target, completions_list in tiktok_targets.items():
            tasks.append(VerificationService._batch_tiktok(target, completions_list))
        
        if tasks:
            await asyncio.gather(*tasks)
    
    @staticmethod
    async def _batch_twitter(target, completions):
        """Batch Twitter verifications"""
        user_handles = []
        for c in completions:
            try:
                profile = c.user.social_profiles.get(platform='twitter')
                user_handles.append((c.id, profile.handle))
            except:
                pass
        
        if not user_handles:
            return
        
        handles = [h for _, h in user_handles]
        results = await twitter.verify_follow_batch(handles, target)
        
        for completion_id, handle in user_handles:
            completion = next(c for c in completions if c.id == completion_id)
            verified = results.get(handle, False)
            
            if verified:
                completion.verify()
            else:
                completion.fail('Not following target account')
    
    @staticmethod
    async def _batch_youtube(url, completions):
        """Batch YouTube verifications"""
        user_ids = []
        for c in completions:
            try:
                profile = c.user.social_profiles.get(platform='youtube')
                user_ids.append((c.id, profile.handle))
            except:
                pass
        
        if not user_ids:
            return
        
        identifiers = [i for _, i in user_ids]
        results = await youtube.verify_comment_batch(identifiers, url)
        
        for completion_id, identifier in user_ids:
            completion = next(c for c in completions if c.id == completion_id)
            verified = results.get(identifier, False)
            
            if verified:
                completion.verify()
            else:
                completion.fail('Comment not found')
    
    @staticmethod
    async def _batch_tiktok(target, completions):
        """Batch TikTok verifications"""
        user_handles = []
        for c in completions:
            try:
                profile = c.user.social_profiles.get(platform='tiktok')
                user_handles.append((c.id, profile.handle))
            except:
                pass
        
        if not user_handles:
            return
        
        handles = [h for _, h in user_handles]
        results = await tiktok.verify_follow_batch(handles, target)
        
        for completion_id, handle in user_handles:
            completion = next(c for c in completions if c.id == completion_id)
            verified = results.get(handle, False)
            
            if verified:
                completion.verify()
            else:
                completion.fail('Not following target account')