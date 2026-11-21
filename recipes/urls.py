from django.urls import path
from . import views 

urlpatterns = [
    path('', views.recipe_list, name='recipe_list'),
    path('recipe/new/', views.create_recipe, name='recipe_create'),
    path('profile/edit/', views.edit_profile, name='profile_edit'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('profile/<str:username>/follow/', views.toggle_follow, name='toggle_follow'),
    path('recipe/<int:pk>/', views.recipe_detail, name='recipe_detail'), 
    path('recipe/<int:pk>/update/', views.update_recipe, name='recipe_update'),
    path('recipe/<int:pk>/delete/', views.delete_recipe, name='recipe_delete'),
    path('recipe/<int:pk>/react/<str:type>/', views.add_reaction, name='add_reaction'),
    path('recipe/<int:pk>/repost/', views.repost_recipe, name='repost_recipe'),
    path('notifications/', views.notifications, name='notifications'),
    path('profile/<str:username>/list/<str:list_type>/', views.get_user_list, name='user_list'),
    path('discover/', views.discover_recipes, name='discover'),
    path('popular/', views.popular_recipes, name='popular_now'),
    path('chat/<str:username>/', views.private_chat, name='private_chat'),
    path('messages/send/<str:username>/', views.send_message, name='send_message'),
    path('messages/get/<str:username>/', views.get_messages, name='get_messages'),
]