from .models import Notification, Task

def task_notifications(request):
    if not request.user.is_authenticated:
        return {}
    notifications = Notification.objects.filter(
        user=request.user, is_read=False
    ).select_related('task').order_by('-created')[:10]
    unread_count = notifications.count()
    print("unread count :", unread_count)
    print("Notifications :", notifications)
    return {
        'task_notifications': notifications,
        'task_unread_count': unread_count,
    }