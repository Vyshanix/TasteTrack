import re, requests, json
from collections import Counter
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .forms import RecipeForm, CommentForm # Ensure this matches your forms.py
from .models import Notification, Recipe, Reaction, Message
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce

def get_mutual_friends_data(user):
    if not user.is_authenticated:
        return []
    
    # 1. Get the list of Users that this user follows
    users_i_follow = User.objects.filter(profile__followers=user)
    
    # 2. Get the list of Users who follow this user
    users_following_me = user.profile.followers.all()
    
    # 3. The intersection is our mutual friends list
    mutuals = users_i_follow.filter(id__in=users_following_me.values_list('id', flat=True))

    for friend in mutuals:
        # Get the absolute last message between you two
        last_msg = Message.objects.filter(
            Q(sender=user, receiver=friend) | Q(sender=friend, receiver=user)
        ).order_by('-timestamp').first()

        # Count unread messages from this friend
        friend.unread_count = Message.objects.filter(
            sender=friend, receiver=user, is_read=False
        ).count()
        
        if last_msg:
            prefix = "You: " if last_msg.sender == user else ""
            # Truncate long messages for the preview
            body_preview = last_msg.body[:20] + "..." if len(last_msg.body) > 20 else last_msg.body
            friend.last_preview = f"{prefix}{body_preview}"
        else:
            friend.last_preview = "Click to send message"
            
    return mutuals

@login_required
def recipe_list(request):
    query = request.GET.get('q', '')
    external_results = []
    api_key = 'f29c917187674fd795087b873493bec3' 

    if query:
        recipes = Recipe.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        ).order_by('-date_posted')
        try:
            url = f"https://api.spoonacular.com/recipes/findByIngredients?ingredients={query}&number=3&apiKey={api_key}"
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                external_results = response.json()
        except:
            external_results = [] 
    else:
        recipes = Recipe.objects.all().order_by('-date_posted')

    trending_recipes = Recipe.objects.filter(repost_of__isnull=True) \
                                     .annotate(num_reactions=Count('reactions')) \
                                     .order_by('-num_reactions')[:5]
    
    popular_tags = set()
    for tr in trending_recipes:
        tags_in_desc = [word.strip(",.!") for word in tr.description.split() if word.startswith("#")]
        for tag in tags_in_desc:
            popular_tags.add(tag)

    # FETCH MUTUAL FRIENDS DATA HERE
    mutual_friends = get_mutual_friends_data(request.user)

    return render(request, 'recipes/recipe_list.html', {
        'recipes': recipes,
        'trending_recipes': trending_recipes,
        'popular_tags': list(popular_tags)[:6],
        'external_results': external_results,
        'query': query,
        'mutual_friends': mutual_friends, # Pass this to the template
    })

@login_required
def create_recipe(request):
    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.author = request.user
            recipe.save()
            return redirect('recipe_list')
    else:
        form = RecipeForm()
    return render(request, 'recipes/recipe_form.html', {'form': form})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('recipe_list')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def profile(request, username):
    user_profile = get_object_or_404(User, username=username)
    user_recipes = Recipe.objects.filter(author=user_profile).order_by('-date_posted')
    
    # 1. STATUS LOGIC
    total_likes = Reaction.objects.filter(recipe__author=user_profile).count()
    recipe_count = user_recipes.count()
    
    if recipe_count >= 10 and total_likes >= 1000:
        status = "Top Creator 💎"
    elif recipe_count >= 5:
        status = "Active Cook 🍳"
    else:
        status = "Taste Creator ✨"

    # 2. RISING STAR / FOLLOWERS LOGIC
    follower_count = user_profile.followers.count() if hasattr(user_profile, 'followers') else 0
    star_level = "Elite Creator" if follower_count >= 100 else "New Creator"
    growth_percent = 15 

    # 3. ACCURATE FOOD DETECTION (Fixes measurements like tbsp/500g)
    FOOD_LIBRARY = {
        'meat': ['chicken', 'pork', 'beef', 'steak', 'bacon', 'ham', 'lamb'],
        'seafood': ['fish', 'shrimp', 'prawn', 'crab', 'tuna', 'salmon', 'tilapia'],
        'vegetables': ['potato', 'garlic', 'onion', 'tomato', 'cabbage', 'carrot', 'pepper'],
        'pantry': ['rice', 'pasta', 'flour', 'egg', 'milk', 'cheese', 'butter'],
    }
    
    found_ingredients = []
    for r in user_recipes:
        # Search the title and ingredients for real food words
        search_area = (r.title + " " + r.ingredients).lower()
        for category, items in FOOD_LIBRARY.items():
            for item in items:
                if item in search_area:
                    found_ingredients.append(item.capitalize())

    # 4. COOKING STYLE & TOP INGREDIENT MAPPING
    common_data = Counter(found_ingredients).most_common(5)
    top_ingredient = common_data[0][0] if common_data else "None yet"

    cooking_styles = []
    if any(item.lower() in found_ingredients for item in FOOD_LIBRARY['meat']):
        cooking_styles.append("Meat Lover 🥩")
    if any(item.lower() in found_ingredients for item in FOOD_LIBRARY['seafood']):
        cooking_styles.append("Seafood Fan 🐟")
    if "Rice" in found_ingredients or "Garlic" in found_ingredients:
        cooking_styles.append("Filipino Style 🇵🇭")
    
    if not cooking_styles:
        cooking_styles = ["Home Cook 🏠"]

    is_following = False
    if request.user.is_authenticated:
        if request.user in user_profile.profile.followers.all():
            is_following = True

    return render(request, 'recipes/profile.html', {
        'user_profile': user_profile,
        'recipes': user_recipes,
        'status': status,
        'star_level': star_level,
        'growth_percent': growth_percent,
        'cooking_styles': cooking_styles[:3],
        'top_ingredient': top_ingredient,
        'total_likes': total_likes,
        'is_following': is_following,
        'follower_count': user_profile.profile.followers.count(),
        'following_count': User.objects.filter(profile__followers=user_profile).count(),
    })

@login_required
def edit_profile(request):
    if request.method == 'POST':
        new_bio = request.POST.get('bio') # Gets text from the textarea 'name="bio"'
        profile = request.user.profile
        profile.bio = new_bio
        profile.save()
    return redirect('profile', username=request.user.username)

@login_required
def delete_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.author == request.user:
        if request.method == 'POST':
            recipe.delete()
            return redirect('profile', username=request.user.username)
    return redirect('recipe_detail', pk=pk)

@login_required
def update_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    if recipe.author != request.user or recipe.repost_of:
        return redirect('recipe_list')
    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            form.save()
            return redirect('recipe_list',)
    else:
        form = RecipeForm(instance=recipe)
    return render(request, 'recipes/recipe_form.html', {'form': form, 'edit_mode': True})

def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk)
    comments = recipe.comments.all().order_by('-date_posted')
    
    trending_recipes = Recipe.objects.filter(repost_of__isnull=True) \
                                     .annotate(num_reactions=Count('reactions')) \
                                     .order_by('-num_reactions')[:5]
    
    # DYNAMIC TAGS FIX: Same logic for the detail page sidebar
    popular_tags = set()
    for tr in trending_recipes:
        tags_in_desc = [word.strip(",.!") for word in tr.description.split() if word.startswith("#")]
        for tag in tags_in_desc:
            popular_tags.add(tag)

    related_recipes = Recipe.objects.filter(
        Q(author=recipe.author) | Q(title__icontains=recipe.title.split()[0]),
    ).exclude(pk=recipe.pk).order_by('-date_posted')[:3]

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.recipe = recipe
            comment.author = request.user
            comment.save()
        return redirect('recipe_detail', pk=pk)
    else:
        form = CommentForm()

    return render(request, 'recipes/recipe_detail.html', {
        'recipe': recipe, 
        'comments': comments,
        'comment_form': form,
        'trending_recipes': trending_recipes,
        'related_recipes': related_recipes,
        'popular_tags': list(popular_tags)[:6] # Pass real tags here too
    })

@login_required
@login_required
def add_reaction(request, pk, type):
    recipe = get_object_or_404(Recipe, pk=pk)
    existing_reaction = Reaction.objects.filter(recipe=recipe, author=request.user).first()
    
    if existing_reaction:
        if existing_reaction.reaction_type == type:
            # 1. UNDO ACTION: User clicked the same reaction again
            existing_reaction.delete()
            
            # FIX: Remove the notification when they undo the reaction
            Notification.objects.filter(
                recipient=recipe.author,
                sender=request.user,
                recipe=recipe,
                notification_type='react'
            ).delete()
        else:
            # User changed reaction type (e.g., from Like to Love)
            existing_reaction.reaction_type = type
            existing_reaction.save()
            # We don't need a new notification here since they already reacted
    else:
        # 2. NEW ACTION: User reacted for the first time
        Reaction.objects.create(recipe=recipe, author=request.user, reaction_type=type)
        
        # FIX: Use get_or_create to prevent duplicate notifications if they click fast
        if recipe.author != request.user:
            Notification.objects.get_or_create(
                recipient=recipe.author,
                sender=request.user,
                recipe=recipe,
                notification_type='react'
            )
            
    return redirect(request.META.get('HTTP_REFERER', 'recipe_list'))

@login_required
def repost_recipe(request, pk):
    original_recipe = get_object_or_404(Recipe, pk=pk)
    
    # If the user tries to repost a repost, we point to the actual original source
    source_recipe = original_recipe.repost_of if original_recipe.repost_of else original_recipe

    Recipe.objects.create(
        title=f"Repost: {source_recipe.title}",
        description=source_recipe.description,
        ingredients=source_recipe.ingredients,
        instructions=source_recipe.instructions,
        image=source_recipe.image,
        author=request.user,
        repost_of=source_recipe # This links it so the Trending list can filter it out
    )
    
    if source_recipe.author != request.user:
        Notification.objects.create(
            recipient=source_recipe.author,
            sender=request.user,
            notification_type='repost',
            recipe=source_recipe
        )
    return redirect('profile', username=request.user.username)

@login_required
def notifications(request):
    notes = request.user.notifications.all().order_by('-timestamp')
    notes.update(is_read=True)
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'recipes/notification_list_partial.html', {'notes': notes})
    
    return render(request, 'recipes/notifications.html', {'notes': notes})

@login_required
def toggle_follow(request, username):
    user_to_follow = get_object_or_404(User, username=username)
    profile = user_to_follow.profile

    if request.user != user_to_follow:
        if request.user in profile.followers.all():
            profile.followers.remove(request.user)
        else:
            profile.followers.add(request.user)
            # Notify the user they have a new follower
            Notification.objects.create(
                recipient=user_to_follow,
                sender=request.user,
                notification_type='follow' # Ensure your Notification model supports this type
            )

    return redirect('profile', username=username)

def get_user_list(request, username, list_type):
    user_profile = get_object_or_404(User, username=username)
    
    if list_type == 'followers':
        # This works because 'followers' exists on the Profile
        users = user_profile.profile.followers.all() 
        title = "Followers"
    else:
        # FIX: Find all Users whose profile followers includes this user
        # This is the "Reverse Lookup" for Following
        users = User.objects.filter(profile__followers=user_profile)
        title = "Following"
        
    return render(request, 'recipes/user_list_partial.html', {
        'users': users, 
        'title': title
    })

def discover_recipes(request):
    api_key = 'f29c917187674fd795087b873493bec3' #API Key
    ingredients = request.GET.get('ingredients', '')
    external_recipes = []

    if ingredients:
        # 1. Search for recipes by ingredients
        search_url = f"https://api.spoonacular.com/recipes/findByIngredients"
        params = {
            'ingredients': ingredients,
            'number': 6, # Show 6 results
            'apiKey': api_key,
            'ranking': 1 # Maximize used ingredients
        }
        
        response = requests.get(search_url, params=params)
        if response.status_code == 200:
            external_recipes = response.json()

    return render(request, 'recipes/discover.html', {
        'external_recipes': external_recipes,
        'query': ingredients
    })

def popular_recipes(request):
    # 1. Get recipes for the main grid (ranked by their individual popularity)
    popular_dishes = Recipe.objects.annotate(
        reaction_count=Count('reactions')
    ).order_by('-reaction_count')[:10]
    
    top_chef = User.objects.annotate(
        true_total_likes=Coalesce(Count('recipe__reactions'), Value(0))
    ).order_by('-true_total_likes', 'username').first()

    context = {
        'recipes': popular_dishes,
        'top_chef': top_chef,
    }
    
    return render(request, 'recipes/popular_now.html', context)

@login_required
def private_chat(request, username):
    # This finds the person you want to chat with
    receiver = get_object_or_404(User, username=username)
    
    # For now, we'll just render the page. 
    # You'll eventually pass your message history here.
    return render(request, 'recipes/private_chat.html', {
        'receiver': receiver,
    })

def send_message(request, username):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message_text = data.get('message')
            receiver_user = User.objects.get(username=username)
            
            # Create the message using your 'body' field
            Message.objects.create(
                sender=request.user,
                receiver=receiver_user,
                body=message_text
            )
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'failed'})

def get_messages(request, username):
    other_user = User.objects.get(username=username)

    # Mark messages as read
    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
    
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) | 
        Q(sender=other_user, receiver=request.user)
    ).order_by('timestamp')

    message_list = []
    for msg in messages:
        message_list.append({
            'sender': msg.sender.username,
            'body': msg.body,
            'timestamp': msg.timestamp.strftime('%H:%M')
        })
    
    return JsonResponse({'messages': message_list})