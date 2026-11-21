from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q

class Recipe(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    ingredients = models.TextField() # We can improve this format later
    instructions = models.TextField()
    image = models.ImageField(upload_to='recipe_pics/', blank=True)
    # The 'author' is linked to the User who created it.
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    date_posted = models.DateTimeField(auto_now_add=True) # Sets date automatically
    prep_time = models.PositiveIntegerField(default=15) # in minutes
    difficulty = models.CharField(max_length=20, choices=[('Easy', 'Easy'), ('Medium', 'Medium'), ('Hard', 'Hard')], default='Easy')
    repost_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reposts')

    def __str__(self):
        return self.title
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', default='default.jpg')
    followers = models.ManyToManyField(User, related_name='following', blank=True, symmetrical=False)

    def __str__(self):
        return f'{self.user.username} Profile'
    
    @property
    def unread_notifications_count(self):
        return self.user.notifications.filter(is_read=False).count()

class Comment(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.author.username} on {self.recipe.title}'

class Reaction(models.Model):
    LIKE = '👍'
    LOVE = '❤️'
    DELICIOUS = '😋'
    REACTION_CHOICES = [
        (LIKE, 'Like'),
        (LOVE, 'Love'),
        (DELICIOUS, 'Delicious'),
    ]
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='reactions')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=2, choices=REACTION_CHOICES)

    class Meta:
        # Prevents a user from reacting multiple times to the same post
        unique_together = ('recipe', 'author')

    def __str__(self):
        return f'{self.author.username} reacted {self.reaction_type} to {self.recipe.title}'
    
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Notification(models.Model):
    # The person who will see the notification (the post owner)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    # The person who did the action
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    # The type of action
    NOTIFICATION_TYPES = (
        ('comment', 'commented on your post'),
        ('react', 'reacted to your post'),
        ('repost', 'reposted your post'),
        ('follow', 'Follow'),
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender} {self.notification_type} {self.recipe.title}"
    
class Message(models.Model):
    # Change 'on_relative' to 'related_name'
    sender = models.ForeignKey(User, related_name='sender_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    body = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['timestamp']

# Logic to filter mutual followers
def get_mutual_friends_with_previews(user):
    # Your existing mutual friends logic
    users_i_follow = User.objects.filter(profile__followers=user)
    users_following_me = user.profile.followers.all()
    mutuals = users_i_follow.filter(id__in=users_following_me.values_list('id', flat=True))

    for friend in mutuals:
        # Get the absolute last message between you two
        last_msg = Message.objects.filter(
            Q(sender=user, receiver=friend) | Q(sender=friend, receiver=user)
        ).order_by('-timestamp').first()

        # Count how many messages the friend sent you that you haven't read
        unread_count = Message.objects.filter(
            sender=friend, receiver=user, is_read=False
        ).count()

        # Attach this data to the friend object dynamically
        friend.unread_count = unread_count
        
        if last_msg:
            prefix = "You: " if last_msg.sender == user else ""
            friend.last_preview = f"{prefix}{last_msg.body[:20]}..." if len(last_msg.body) > 20 else f"{prefix}{last_msg.body}"
        else:
            friend.last_preview = "Click to send message"
            
    return mutuals