from django.urls import path
from . import views

urlpatterns = [
    # Home and Products
    path('', views.home, name='home'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Authentication
    path('register/', views.register_page, name='register'),
    path('login/', views.login_page, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Shopping Cart
    path('cart/', views.view_cart, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('update-cart/<int:item_id>/', views.update_cart, name='update_cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Checkout and Orders
    path('checkout/', views.checkout, name='checkout'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('order-history/', views.order_history, name='order_history'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('request-return/<int:order_id>/', views.request_return, name='request_return'),
    path('update-return-tracking/<int:request_id>/', views.update_return_tracking, name='update_return_tracking'),
    
    # Seller Dashboard
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/add-product/', views.add_product, name='add_product'),
    path('seller/edit-product/<int:product_id>/', views.edit_product, name='edit_product'),
    path('seller/delete-product/<int:product_id>/', views.delete_product, name='delete_product'),
    path('seller/update-order-status/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('seller/handle-return/<int:request_id>/', views.handle_return_request, name='handle_return_request'),
    path('seller/delete-product-image/<int:image_id>/', views.delete_product_image, name='delete_product_image'),
    path('seller/reorder-product-images/<int:product_id>/', views.reorder_product_images, name='reorder_product_images'),

]
