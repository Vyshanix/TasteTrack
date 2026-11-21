from django.contrib.auth.models import User

def chat_context(request):
    if request.user.is_authenticated:
        # Get users that follow the current user
        followers = request.user.profile.followers.all()
        # Get users that the current user is following
        # (Using the related_name 'following' from your User model)
        following = User.objects.filter(profile__followers=request.user)
        
        # Intersection = Mutual Friends
        mutual_friends = followers.filter(id__in=following.values_list('id', flat=True))
        
        return {'mutual_friends': mutual_friends}
    return {'mutual_friends': []}