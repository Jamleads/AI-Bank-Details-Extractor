from app.services.auth_service import get_current_user_required

def get_user_id(current_user):
    """
    Safely get user ID from current_user, whether it's a dict or object
    
    Args:
        current_user: Current user object or dict
        
    Returns:
        User ID
    """
    if isinstance(current_user, dict):
        return current_user.get('id')
    else:
        return current_user.id 