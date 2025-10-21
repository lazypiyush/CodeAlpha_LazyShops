from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import models
from .models import Product, CartItem, Order, OrderItem, Profile, ProductImage, ReturnRequest
import json


# Home page - Product listing with search and filters
def home(request):
    products = Product.objects.all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(name__icontains=search_query)
    
    # Price filter
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    
    # Stock filter
    stock_filter = request.GET.get('stock', '')
    if stock_filter == 'in_stock':
        products = products.filter(stock__gt=0)
    elif stock_filter == 'out_of_stock':
        products = products.filter(stock=0)
    
    # Sorting
    sort_by = request.GET.get('sort', '')
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    elif sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == 'newest':
        products = products.order_by('-created_at')
    else:
        products = products.order_by('-created_at')  # Default: newest first
    
    context = {
        'products': products,
        'search_query': search_query,
        'min_price': min_price,
        'max_price': max_price,
        'stock_filter': stock_filter,
        'sort_by': sort_by,
    }
    
    return render(request, 'home.html', context)



# Product detail page
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'product_detail.html', {'product': product})


# User registration
def register_page(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'customer')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken!')
            return redirect('register')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered!')
            return redirect('register')
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        user.save()
        
        Profile.objects.create(user=user, user_type=user_type)
        
        messages.success(request, f'Account created successfully as {user_type.title()}!')
        return redirect('login')
    
    return render(request, 'register.html')


# User login
def login_page(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if not User.objects.filter(username=username).exists():
            messages.error(request, 'Invalid username')
            return redirect('login')
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            messages.error(request, 'Invalid password')
            return redirect('login')
        else:
            login(request, user)
            
            if hasattr(user, 'profile') and user.profile.is_seller():
                return redirect('seller_dashboard')
            return redirect('home')
    
    return render(request, 'login.html')


# User logout
def logout_view(request):
    logout(request)
    return redirect('home')


# Add to cart
@login_required(login_url='login')
def add_to_cart(request, product_id):
    if hasattr(request.user, 'profile') and request.user.profile.is_seller():
        messages.error(request, 'Sellers cannot purchase products. Please register as a customer.')
        return redirect('home')
    
    product = get_object_or_404(Product, id=product_id)
    
    if product.stock <= 0:
        messages.error(request, f'Sorry! {product.name} is out of stock.')
        return redirect('product_detail', product_id=product_id)
    
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product
    )
    
    if not created:
        if cart_item.quantity + 1 > product.stock:
            messages.error(request, f'Sorry! Only {product.stock} items available.')
            return redirect('cart')
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{product.name} added to cart!')
    return redirect('cart')


# View cart
@login_required(login_url='login')
def view_cart(request):
    if hasattr(request.user, 'profile') and request.user.profile.is_seller():
        messages.error(request, 'Sellers cannot access cart. Please use Seller Dashboard.')
        return redirect('seller_dashboard')
    
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.get_total() for item in cart_items)
    return render(request, 'cart.html', {'cart_items': cart_items, 'total': total})


# Update cart
@login_required(login_url='login')
def update_cart(request, item_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
        quantity = int(request.POST.get('quantity', 1))
        
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    
    return redirect('cart')


# Remove from cart
@login_required(login_url='login')
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    messages.success(request, 'Item removed from cart!')
    return redirect('cart')


# Checkout
@login_required(login_url='login')
def checkout(request):
    if hasattr(request.user, 'profile') and request.user.profile.is_seller():
        messages.error(request, 'Sellers cannot place orders.')
        return redirect('seller_dashboard')
    
    cart_items = CartItem.objects.filter(user=request.user)
    
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty!')
        return redirect('cart')
    
    total = sum(item.get_total() for item in cart_items)
    
    if request.method == 'POST':
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        
        for cart_item in cart_items:
            if cart_item.product.stock < cart_item.quantity:
                messages.error(request, f'Sorry! {cart_item.product.name} has only {cart_item.product.stock} items in stock.')
                return redirect('cart')
        
        order = Order.objects.create(
            customer=request.user,
            total_price=total,
            address=address,
            phone=phone
        )
        
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price=cart_item.product.price
            )
            
            cart_item.product.stock -= cart_item.quantity
            cart_item.product.save()
        
        cart_items.delete()
        
        messages.success(request, 'Order placed successfully!')
        return redirect('order_confirmation', order_id=order.id)
    
    return render(request, 'checkout.html', {'cart_items': cart_items, 'total': total})


# Order confirmation
@login_required(login_url='login')
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    return render(request, 'order_confirmation.html', {'order': order})


# Order history
@login_required(login_url='login')
def order_history(request):
    orders = Order.get_orders_by_customer(request.user.id)
    return render(request, 'order_history.html', {'orders': orders})


# Cancel Order
@login_required(login_url='login')
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status in ['shipped', 'delivered']:
        messages.error(request, 'Cannot cancel order that has been shipped or delivered.')
        return redirect('order_history')
    
    order.status = 'cancelled'
    order.save()
    
    for item in order.items.all():
        item.product.stock += item.quantity
        item.product.save()
    
    messages.success(request, f'Order #{order.id} has been cancelled successfully.')
    return redirect('order_history')


# Request Return
@login_required(login_url='login')
def request_return(request, order_id):
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    
    if order.status != 'delivered':
        messages.error(request, 'Only delivered orders can be returned.')
        return redirect('order_history')
    
    if order.return_requests.exists():
        messages.warning(request, 'A return request already exists for this order.')
        return redirect('order_history')
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        
        ReturnRequest.objects.create(
            order=order,
            reason=reason
        )
        
        messages.success(request, 'Return request submitted successfully! We will review it shortly.')
        return redirect('order_history')
    
    return render(request, 'request_return.html', {'order': order})


# Update Return Tracking
@login_required(login_url='login')
def update_return_tracking(request, request_id):
    if request.method == 'POST':
        return_request = get_object_or_404(ReturnRequest, id=request_id, order__customer=request.user)
        
        if return_request.status == 'approved':
            tracking_number = request.POST.get('tracking_number')
            return_request.tracking_number = tracking_number
            return_request.save()
            messages.success(request, 'Tracking number updated! Seller will process once item is received.')
        
        return redirect('order_history')
    
    return redirect('order_history')


# Seller Dashboard
@login_required(login_url='login')
def seller_dashboard(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.is_seller():
        messages.error(request, 'Access denied! Sellers only.')
        return redirect('home')
    
    from decimal import Decimal
    
    products = Product.objects.filter(seller=request.user)
    orders = OrderItem.objects.filter(product__seller=request.user).select_related('order', 'product')
    
    return_requests = ReturnRequest.objects.filter(
        order__items__product__seller=request.user
    ).distinct().order_by('-created_at')
    
    total_refunded = Decimal('0.00')
    refunded_order_ids = []
    
    for return_req in return_requests:
        if return_req.status == 'refund_completed' and return_req.refund_amount:
            total_refunded += Decimal(str(return_req.refund_amount))
            refunded_order_ids.append(return_req.order.id)
    
    total_sales = Decimal('0.00')
    for item in orders:
        if item.order.id not in refunded_order_ids:
            total_sales += Decimal(str(item.quantity)) * Decimal(str(item.price))
    
    total_products = products.count()
    total_orders = orders.count()
    
    context = {
        'products': products,
        'orders': orders,
        'return_requests': return_requests,
        'total_products': total_products,
        'total_sales': total_sales,
        'total_orders': total_orders,
        'total_refunded': total_refunded,
    }
    
    return render(request, 'seller_dashboard.html', context)


# Add Product
@login_required(login_url='login')
def add_product(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.is_seller():
        messages.error(request, 'Access denied! Sellers only.')
        return redirect('home')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        
        print(f"\n=== ADD PRODUCT DEBUG ===")
        print(f"Name: {name}")
        print(f"Files in request: {request.FILES}")
        print(f"Images: {request.FILES.getlist('images')}")
        
        product = Product.objects.create(
            name=name,
            description=description,
            price=price,
            stock=stock,
            seller=request.user
        )
        
        images = request.FILES.getlist('images')
        print(f"Total images to save: {len(images)}")
        
        for index, image in enumerate(images):
            ProductImage.objects.create(
                product=product,
                image=image,
                order=index
            )
            print(f"✓ Saved image {index + 1}: {image.name}")
        
        messages.success(request, f'Product "{product.name}" added successfully with {len(images)} images!')
        return redirect('seller_dashboard')
    
    return render(request, 'add_product.html')


# Edit Product
@login_required(login_url='login')
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.description = request.POST.get('description')
        product.price = request.POST.get('price')
        product.stock = request.POST.get('stock')
        product.save()
        
        # Handle new images
        new_images = request.FILES.getlist('images')
        
        print(f"\n=== EDIT PRODUCT DEBUG ===")
        print(f"Files in request: {request.FILES}")
        print(f"New images: {len(new_images)}")
        
        if new_images:
            # Get current max order
            max_order_result = product.images.aggregate(models.Max('order'))
            max_order = max_order_result['order__max']
            
            # If no images exist yet, start from 0
            if max_order is None:
                max_order = -1
            
            print(f"Current max order: {max_order}")
            
            # Add new images after existing ones
            for index, image in enumerate(new_images):
                new_order = max_order + index + 1
                ProductImage.objects.create(
                    product=product,
                    image=image,
                    order=new_order
                )
                print(f"✓ Added image {index + 1} with order {new_order}: {image.name}")
        
        messages.success(request, f'Product updated successfully! Added {len(new_images)} new images.')
        return redirect('seller_dashboard')
    
    return render(request, 'edit_product.html', {'product': product})



# Delete Product
@login_required(login_url='login')
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    product_name = product.name
    product.delete()
    messages.success(request, f'Product "{product_name}" deleted successfully!')
    return redirect('seller_dashboard')


# Delete Product Image
@login_required(login_url='login')
def delete_product_image(request, image_id):
    image = get_object_or_404(ProductImage, id=image_id, product__seller=request.user)
    product_id = image.product.id
    image.delete()
    messages.success(request, 'Image deleted successfully!')
    return redirect('edit_product', product_id=product_id)


# Reorder Product Images
@login_required(login_url='login')
def reorder_product_images(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, seller=request.user)
        order_data = json.loads(request.body)
        
        # Get all images and create order mapping
        all_images = list(product.images.all().order_by('order'))
        
        # Update orders based on swap/move
        for item in order_data:
            image = ProductImage.objects.get(id=item['id'], product=product)
            
            # Find image at target position
            target_image = next((img for img in all_images if img.order == item['order']), None)
            
            if target_image and target_image.id != image.id:
                # Swap orders
                temp_order = image.order
                image.order = target_image.order
                target_image.order = temp_order
                
                image.save()
                target_image.save()
            else:
                image.order = item['order']
                image.save()
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'})

    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id, seller=request.user)
        order_data = json.loads(request.body)
        
        for item in order_data:
            image = ProductImage.objects.get(id=item['id'], product=product)
            image.order = item['order']
            image.save()
        
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error'})


# Update Order Status
@login_required(login_url='login')
def update_order_status(request, order_id):
    if not hasattr(request.user, 'profile') or not request.user.profile.is_seller():
        messages.error(request, 'Access denied! Sellers only.')
        return redirect('home')
    
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        
        order_items = order.items.filter(product__seller=request.user)
        
        if not order_items.exists():
            messages.error(request, 'You do not have permission to update this order.')
            return redirect('seller_dashboard')
        
        new_status = request.POST.get('status')
        order.status = new_status
        order.save()
        
        messages.success(request, f'Order #{order.id} status updated to {order.get_status_display()}!')
        return redirect('seller_dashboard')
    
    return redirect('seller_dashboard')


# Handle Return Request
@login_required(login_url='login')
def handle_return_request(request, request_id):
    if request.method == 'POST':
        return_request = get_object_or_404(ReturnRequest, id=request_id)
        
        if not request.user.is_staff:
            if not hasattr(request.user, 'profile') or not request.user.profile.is_seller():
                messages.error(request, 'Access denied!')
                return redirect('home')
            
            order_items = return_request.order.items.filter(product__seller=request.user)
            if not order_items.exists():
                messages.error(request, 'You do not have permission to handle this return request.')
                return redirect('seller_dashboard')
        
        action = request.POST.get('action')
        admin_response = request.POST.get('admin_response', '')
        tracking_number = request.POST.get('tracking_number', '')
        
        if action == 'approve':
            return_request.status = 'approved'
            return_request.admin_response = admin_response
            return_request.refund_amount = return_request.order.total_price
            return_request.save()
            messages.success(request, f'Return request for Order #{return_request.order.id} approved!')
            
        elif action == 'reject':
            return_request.status = 'rejected'
            return_request.admin_response = admin_response
            return_request.save()
            messages.success(request, f'Return request for Order #{return_request.order.id} rejected!')
            
        elif action == 'item_received':
            return_request.status = 'item_received'
            return_request.tracking_number = tracking_number
            if not return_request.refund_amount:
                return_request.refund_amount = return_request.order.total_price
            return_request.save()
            
            for item in return_request.order.items.all():
                item.product.stock += item.quantity
                item.product.save()
            
            messages.success(request, f'Item received for Order #{return_request.order.id}. Stock restored.')
            
        elif action == 'initiate_refund':
            if not return_request.refund_amount:
                return_request.refund_amount = return_request.order.total_price
            return_request.status = 'refund_processing'
            return_request.save()
            messages.success(request, f'Refund initiated for Order #{return_request.order.id}. Amount: ₹{return_request.refund_amount}')
            
        elif action == 'complete_refund':
            from django.utils import timezone
            refund_method = request.POST.get('refund_method', 'Original Payment Method')
            
            if not return_request.refund_amount:
                return_request.refund_amount = return_request.order.total_price
            
            return_request.status = 'refund_completed'
            return_request.refund_date = timezone.now()
            return_request.refund_method = refund_method
            return_request.save()
            
            messages.success(request, f'Refund completed for Order #{return_request.order.id}!')
        
        return redirect('seller_dashboard')
    
    return redirect('seller_dashboard')

