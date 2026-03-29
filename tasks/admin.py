from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Task, TaskCompletion, TaskRequest, SocialProfile


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'task_code', 'task_type', 'platform', 'action', 'points_reward', 'is_active', 'participants_count', 'creator_link']
    list_filter = ['task_type', 'platform', 'action', 'is_active', 'verification_method', 'created_at']
    search_fields = ['name', 'task_code', 'description', 'created_by__username']
    readonly_fields = ['task_code', 'created_at', 'updated_at']
    list_editable = ['is_active']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'task_code', 'task_type', 'platform', 'action')
        }),
        ('Target & Data', {
            'fields': ('target_url', 'target_identifier', 'task_data'),
            'classes': ('wide',),
        }),
        ('Rewards', {
            'fields': ('points_reward', 'mining_boost', 'boost_duration_hours'),
            'classes': ('wide',),
        }),
        ('Verification Settings', {
            'fields': ('verification_method', 'requires_approval'),
            'classes': ('wide',),
        }),
        ('Limits', {
            'fields': ('max_participants', 'daily_limit', 'total_limit', 'is_active', 'expiry_date'),
            'classes': ('wide',),
        }),
        ('Creator Info', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def participants_count(self, obj):
        count = obj.completions.filter(status='verified').count()
        if obj.max_participants:
            return f"{count}/{obj.max_participants}"
        return count
    participants_count.short_description = 'Participants'
    
    def creator_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.created_by.id])
        return format_html('<a href="{}">{}</a>', url, obj.created_by.username)
    creator_link.short_description = 'Created By'
    
    actions = ['activate_tasks', 'deactivate_tasks']
    
    def activate_tasks(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f"Activated {queryset.count()} tasks")
    activate_tasks.short_description = "Activate selected tasks"
    
    def deactivate_tasks(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {queryset.count()} tasks")
    deactivate_tasks.short_description = "Deactivate selected tasks"


@admin.register(TaskCompletion)
class TaskCompletionAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'task_link', 'status', 'reward_claimed', 'created_at', 'verified_at']
    list_filter = ['status', 'reward_claimed', 'created_at']
    search_fields = ['user__username', 'task__name', 'task__task_code']
    readonly_fields = ['created_at', 'updated_at', 'verification_data']
    
    fieldsets = (
        ('Task Information', {
            'fields': ('user', 'task')
        }),
        ('Status', {
            'fields': ('status', 'rejection_reason')
        }),
        ('Verification', {
            'fields': ('verified_at', 'verified_by', 'verification_data'),
            'classes': ('collapse',),
        }),
        ('Rewards', {
            'fields': ('reward_claimed', 'reward_claimed_at'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'submission_data', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def task_link(self, obj):
        url = reverse('admin:tasks_task_change', args=[obj.task.id])
        return format_html('<a href="{}">{}</a>', url, obj.task.name)
    task_link.short_description = 'Task'
    
    actions = ['verify_selected', 'fail_selected', 'reject_selected']
    
    def verify_selected(self, request, queryset):
        for completion in queryset:
            if completion.status in ['pending', 'processing']:
                completion.verify(request.user)
        self.message_user(request, f"Verified {queryset.count()} completions")
    verify_selected.short_description = "Verify selected completions"
    
    def fail_selected(self, request, queryset):
        for completion in queryset:
            if completion.status in ['pending', 'processing']:
                completion.fail("Admin marked as failed")
        self.message_user(request, f"Failed {queryset.count()} completions")
    fail_selected.short_description = "Fail selected completions"
    
    def reject_selected(self, request, queryset):
        for completion in queryset:
            completion.status = 'rejected'
            completion.rejection_reason = "Admin rejected"
            completion.save()
        self.message_user(request, f"Rejected {queryset.count()} completions")
    reject_selected.short_description = "Reject selected completions"


@admin.register(TaskRequest)
class TaskRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'task', 'status', 'created_at', 'reviewed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'task__name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Request', {
            'fields': ('user', 'task', 'message')
        }),
        ('Status', {
            'fields': ('status', 'review_notes')
        }),
        ('Review', {
            'fields': ('reviewed_by', 'reviewed_at'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
        }),
    )
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        for req in queryset:
            if req.status == 'pending':
                req.approve(request.user)
        self.message_user(request, f"Approved {queryset.count()} requests")
    approve_requests.short_description = "Approve selected requests"
    
    def reject_requests(self, request, queryset):
        for req in queryset:
            if req.status == 'pending':
                req.reject(request.user, "Admin rejected")
        self.message_user(request, f"Rejected {queryset.count()} requests")
    reject_requests.short_description = "Reject selected requests"


@admin.register(SocialProfile)
class SocialProfileAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'platform', 'handle', 'is_verified', 'created_at']
    list_filter = ['platform', 'is_verified', 'created_at']
    search_fields = ['user__username', 'handle']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'platform', 'handle')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_at'),
            'classes': ('wide',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    actions = ['verify_profiles', 'unverify_profiles']
    
    def verify_profiles(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_verified=True, verified_at=timezone.now())
        self.message_user(request, f"Verified {queryset.count()} profiles")
    verify_profiles.short_description = "Verify selected profiles"
    
    def unverify_profiles(self, request, queryset):
        queryset.update(is_verified=False, verified_at=None)
        self.message_user(request, f"Unverified {queryset.count()} profiles")
    unverify_profiles.short_description = "Unverify selected profiles"