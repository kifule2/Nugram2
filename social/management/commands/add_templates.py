# social/management/commands/add_templates.py
from django.core.management.base import BaseCommand
from social.models import BackgroundTemplate

class Command(BaseCommand):
    help = 'Add initial background templates for text posts'

    def handle(self, *args, **options):
        templates = [
            {
                'name': 'Sunset Gradient',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #667eea, #764ba2)',
                'css_class': 'gradient-sunset',
                'is_animated': False,
                'order': 1
            },
            {
                'name': 'Pink Dream',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #f093fb, #f5576c)',
                'css_class': 'gradient-pink',
                'is_animated': False,
                'order': 2
            },
            {
                'name': 'Ocean Waves',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #4facfe, #00f2fe)',
                'css_class': 'gradient-ocean',
                'is_animated': False,
                'order': 3
            },
            {
                'name': 'Northern Lights',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #ff6b6b, #4ecdc4, #45b7d1)',
                'css_class': 'animated-northern',
                'is_animated': True,
                'animation_duration': 3,
                'order': 4
            },
            {
                'name': 'Pastel Paradise',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #a8edea, #fed6e3, #ffd3b6)',
                'css_class': 'animated-pastel',
                'is_animated': True,
                'animation_duration': 3,
                'order': 5
            },
            {
                'name': 'Crypto King',
                'template_type': 'themed',
                'gradient_css': '#000000',
                'css_class': 'themed-crypto',
                'is_animated': False,
                'order': 6
            },
            {
                'name': 'Motivation Station',
                'template_type': 'themed',
                'gradient_css': 'linear-gradient(135deg, #ffd700, #ffa500)',
                'css_class': 'themed-motivation',
                'is_animated': False,
                'order': 7
            },
            {
                'name': 'Neon Nights',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #f12711, #f5af19, #00c6fb)',
                'css_class': 'animated-neon',
                'is_animated': True,
                'animation_duration': 4,
                'order': 8
            },
            {
                'name': 'Midnight Purple',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #8e2de2, #4a00e0)',
                'css_class': 'gradient-purple',
                'is_animated': False,
                'order': 9
            },
            {
                'name': 'Sunrise Orange',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #f2994a, #f2c94c)',
                'css_class': 'gradient-orange',
                'is_animated': False,
                'order': 10
            },
            {
                'name': 'Forest Green',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #11998e, #38ef7d)',
                'css_class': 'gradient-forest',
                'is_animated': False,
                'order': 11
            },
            {
                'name': 'Cotton Candy',
                'template_type': 'gradient',
                'gradient_css': 'linear-gradient(135deg, #fbc2eb, #a6c1ee)',
                'css_class': 'gradient-cotton',
                'is_animated': False,
                'order': 12
            }
        ]

        for template_data in templates:
            template, created = BackgroundTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults=template_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created template: {template.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Template already exists: {template.name}'))