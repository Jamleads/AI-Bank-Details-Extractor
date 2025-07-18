"""
Admin configuration settings
"""

# List of admin email addresses that are allowed to access the admin panel
ADMIN_EMAILS = [
    "admin@example.com",
    "salbiz2021@gmail.com",  # User's actual email
    "ogunyemiadetunji17@gmail.com",
    "mikaelcbernard@gmail.com"
    # Add more admin emails as needed
]

def is_admin_email(email: str) -> bool:
    """
    Check if an email is in the admin list
    
    Args:
        email: Email address to check
        
    Returns:
        True if the email is in the admin list, False otherwise
    """
    return email.lower() in [admin_email.lower() for admin_email in ADMIN_EMAILS] 