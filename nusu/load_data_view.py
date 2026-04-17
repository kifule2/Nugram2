# nusu/load_data_view.py
import json
import tempfile
from django.http import JsonResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["POST"])
def load_migration_data(request):
    """Load data from SQLite dump into PostgreSQL"""
    
    try:
        # Get JSON data from request body
        data = request.body.decode('utf-8')
        
        if not data:
            return JsonResponse({'error': 'No data provided'}, status=400)
        
        # Validate it's valid JSON
        try:
            json.loads(data)
        except json.JSONDecodeError as e:
            return JsonResponse({'error': f'Invalid JSON: {str(e)}'}, status=400)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(data)
            temp_file = f.name
        
        # Load the data
        call_command('loaddata', temp_file, verbosity=1)
        
        return JsonResponse({'status': 'success', 'message': 'Data loaded successfully'})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)