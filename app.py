# filepath: app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import random
import string

from config import config
from models import db, Student, Category, MenuItem, Order, OrderItem, Feedback


def create_app(config_name=None):
    """Application factory for creating Flask app instance."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    
    # Setup Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return Student.query.get(int(user_id))
    
    # Register routes
    register_routes(app)
    
    # Create database tables
    with app.app_context():
        db.create_all()
        seed_database()
    
    return app


def register_routes(app):
    """Register all application routes."""
    
    # Home page
    @app.route('/')
    def index():
        categories = Category.query.filter_by(is_active=True).order_by(Category.display_order).all()
        featured_items = MenuItem.query.filter_by(is_available=True).order_by(MenuItem.created_at.desc()).limit(6).all()
        return render_template('index.html', categories=categories, featured_items=featured_items)
    
    # Authentication routes
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            student_id = request.form.get('student_id')
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            department = request.form.get('department')
            phone = request.form.get('phone')
            
            # Validation
            if Student.query.filter_by(student_id=student_id).first():
                flash('Student ID already registered.', 'danger')
                return render_template('register.html')
            
            if Student.query.filter_by(email=email).first():
                flash('Email already registered.', 'danger')
                return render_template('register.html')
            
            # Create new student
            student = Student(
                student_id=student_id,
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                department=department,
                phone=phone
            )
            db.session.add(student)
            db.session.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        
        return render_template('register.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            student_id = request.form.get('student_id')
            password = request.form.get('password')
            
            student = Student.query.filter_by(student_id=student_id).first()
            
            if student and check_password_hash(student.password_hash, password):
                login_user(student)
                flash('Logged in successfully!', 'success')
                
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Invalid student ID or password.', 'danger')
        
        return render_template('login.html')
    
    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))
    
    # Menu routes
    @app.route('/menu')
    def menu():
        category_id = request.args.get('category')
        search_query = request.args.get('q')
        
        if category_id:
            items = MenuItem.query.filter_by(category_id=category_id, is_available=True).all()
            category = Category.query.get(category_id)
        elif search_query:
            items = MenuItem.query.filter(
                MenuItem.is_available == True,
                MenuItem.name.ilike(f'%{search_query}%')
            ).all()
        else:
            items = MenuItem.query.filter_by(is_available=True).all()
        
        categories = Category.query.filter_by(is_active=True).order_by(Category.display_order).all()
        return render_template('menu.html', items=items, categories=categories, selected_category=category_id)
    
    @app.route('/menu/<int:item_id>')
    def menu_item_detail(item_id):
        item = MenuItem.query.get_or_404(item_id)
        return render_template('item_detail.html', item=item)
    
    # Cart routes
    @app.route('/cart')
    def cart():
        cart = session.get('cart', {})
        cart_items = []
        total = 0
        
        for item_id, quantity in cart.items():
            item = MenuItem.query.get(int(item_id))
            if item and item.is_available:
                subtotal = item.price * quantity
                cart_items.append({
                    'item': item,
                    'quantity': quantity,
                    'subtotal': subtotal
                })
                total += subtotal
        
        return render_template('cart.html', cart_items=cart_items, total=total)
    
    @app.route('/cart/add/<int:item_id>', methods=['POST'])
    def add_to_cart(item_id):
        item = MenuItem.query.get_or_404(item_id)
        
        if not item.is_available:
            flash('This item is currently unavailable.', 'danger')
            return redirect(url_for('menu'))
        
        quantity = int(request.form.get('quantity', 1))
        
        cart = session.get('cart', {})
        cart[str(item_id)] = cart.get(str(item_id), 0) + quantity
        session['cart'] = cart
        
        flash(f'{item.name} added to cart!', 'success')
        return redirect(url_for('cart'))
    
    @app.route('/cart/update/<int:item_id>', methods=['POST'])
    def update_cart(item_id):
        quantity = int(request.form.get('quantity', 0))
        cart = session.get('cart', {})
        
        if quantity > 0:
            cart[str(item_id)] = quantity
        else:
            cart.pop(str(item_id), None)
        
        session['cart'] = cart
        return redirect(url_for('cart'))
    
    @app.route('/cart/remove/<int:item_id>')
    def remove_from_cart(item_id):
        cart = session.get('cart', {})
        cart.pop(str(item_id), None)
        session['cart'] = cart
        flash('Item removed from cart.', 'info')
        return redirect(url_for('cart'))
    
    @app.route('/cart/clear')
    def clear_cart():
        session.pop('cart', None)
        flash('Cart cleared.', 'info')
        return redirect(url_for('cart'))
    
    # Order routes
    @app.route('/checkout', methods=['GET', 'POST'])
    @login_required
    def checkout():
        cart = session.get('cart', {})
        
        if not cart:
            flash('Your cart is empty.', 'warning')
            return redirect(url_for('menu'))
        
        # Calculate total
        total = 0
        order_items = []
        
        for item_id, quantity in cart.items():
            item = MenuItem.query.get(int(item_id))
            if item and item.is_available:
                subtotal = item.price * quantity
                order_items.append({
                    'item': item,
                    'quantity': quantity,
                    'subtotal': subtotal
                })
                total += subtotal
        
        if request.method == 'POST':
            notes = request.form.get('notes')
            
            # Generate order number
            order_number = generate_order_number()
            
            # Create order
            order = Order(
                order_number=order_number,
                student_id=current_user.id,
                total_amount=total,
                notes=notes,
                estimated_ready_time=datetime.utcnow() + timedelta(minutes=20)
            )
            db.session.add(order)
            db.session.flush()
            
            # Create order items
            for item_id, quantity in cart.items():
                item = MenuItem.query.get(int(item_id))
                if item and item.is_available:
                    order_item = OrderItem(
                        order_id=order.id,
                        menu_item_id=item.id,
                        quantity=quantity,
                        unit_price=item.price,
                        subtotal=item.price * quantity
                    )
                    db.session.add(order_item)
            
            db.session.commit()
            session.pop('cart', None)
            
            flash(f'Order placed successfully! Order number: {order_number}', 'success')
            return redirect(url_for('order_confirmation', order_id=order.id))
        
        return render_template('checkout.html', order_items=order_items, total=total)
    
    @app.route('/order/<int:order_id>')
    @login_required
    def order_confirmation(order_id):
        order = Order.query.get_or_404(order_id)
        
        if order.student_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('index'))
        
        return render_template('order_confirmation.html', order=order)
    
    @app.route('/orders')
    @login_required
    def my_orders():
        orders = Order.query.filter_by(student_id=current_user.id).order_by(Order.created_at.desc()).all()
        return render_template('my_orders.html', orders=orders)
    
    @app.route('/order/<int:order_id>/status')
    @login_required
    def order_status(order_id):
        order = Order.query.get_or_404(order_id)
        
        if order.student_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'order_number': order.order_number,
            'status': order.status,
            'estimated_ready_time': order.estimated_ready_time.isoformat() if order.estimated_ready_time else None
        })
    
    # Feedback route
    @app.route('/order/<int:order_id>/feedback', methods=['GET', 'POST'])
    @login_required
    def submit_feedback(order_id):
        order = Order.query.get_or_404(order_id)
        
        if order.student_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('index'))
        
        if order.status != 'completed':
            flash('You can only provide feedback for completed orders.', 'warning')
            return redirect(url_for('my_orders'))
        
        if order.feedback:
            flash('Feedback already submitted for this order.', 'info')
            return redirect(url_for('my_orders'))
        
        if request.method == 'POST':
            rating = int(request.form.get('rating'))
            comment = request.form.get('comment')
            
            feedback = Feedback(
                order_id=order.id,
                rating=rating,
                comment=comment
            )
            db.session.add(feedback)
            db.session.commit()
            
            flash('Thank you for your feedback!', 'success')
            return redirect(url_for('my_orders'))
        
        return render_template('feedback.html', order=order)
    
    # API routes for menu (for potential future mobile app)
    @app.route('/api/menu')
    def api_menu():
        items = MenuItem.query.filter_by(is_available=True).all()
        return jsonify([item.to_dict() for item in items])
    
    @app.route('/api/categories')
    def api_categories():
        categories = Category.query.filter_by(is_active=True).order_by(Category.display_order).all()
        return jsonify([cat.to_dict() for cat in categories])


def generate_order_number():
    """Generate a unique order number."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M')
    random_suffix = ''.join(random.choices(string.digits, k=4))
    return f'MSU-{timestamp}-{random_suffix}'


def seed_database():
    """Seed the database with initial data."""
    # Check if data already exists
    if Category.query.first():
        return
    
    # Create categories
    categories = [
        Category(name='Main Meals', description='Hearty main dishes', icon='utensils', display_order=1),
        Category(name='Fast Food', description='Quick bites and snacks', icon='hamburger', display_order=2),
        Category(name='Beverages', description='Drinks and refreshments', icon='coffee', display_order=3),
        Category(name='Snacks', description='Light snacks and treats', icon='cookie', display_order=4),
        Category(name='Vegetarian', description='Vegetarian options', icon='leaf', display_order=5),
    ]
    
    for category in categories:
        db.session.add(category)
    
    db.session.commit()
    
    # Create menu items
    menu_items = [
        # Main Meals
        MenuItem(name='Chicken Stew', description='Tender chicken in rich tomato sauce with vegetables', price=45.00, category_id=1, preparation_time=20, calories=450),
        MenuItem(name='Beef Sadza', description='Traditional sadza with tender beef and vegetables', price=50.00, category_id=1, preparation_time=25, calories=550),
        MenuItem(name='Fish and Chips', description='Crispy fried fish with golden chips', price=55.00, category_id=1, preparation_time=15, calories=480),
        MenuItem(name='Pasta Carbonara', description='Creamy pasta with bacon and parmesan', price=40.00, category_id=1, preparation_time=15, calories=520),
        MenuItem(name='Rice and Stew', description='Steamed rice with vegetable stew', price=35.00, category_id=1, preparation_time=15, calories=380),
        
        # Fast Food
        MenuItem(name='Hamburger', description='Beef patty with lettuce, tomato, and special sauce', price=30.00, category_id=2, preparation_time=10, calories=380),
        MenuItem(name='Chicken Wrap', description='Grilled chicken with fresh vegetables in a wrap', price=35.00, category_id=2, preparation_time=8, calories=320),
        MenuItem(name='Pizza Slice', description='Cheese and tomato pizza slice', price=15.00, category_id=2, preparation_time=5, calories=250),
        MenuItem(name='Hot Dog', description='Grilled sausage in a bun with toppings', price=20.00, category_id=2, preparation_time=5, calories=290),
        
        # Beverages
        MenuItem(name='Fresh Juice', description='Mixed fruit juice (seasonal)', price=20.00, category_id=3, preparation_time=3, calories=120),
        MenuItem(name='Coffee', description='Hot brewed coffee', price=15.00, category_id=3, preparation_time=2, calories=5),
        MenuItem(name='Tea', description='Hot tea with milk and sugar', price=10.00, category_id=3, preparation_time=2, calories=40),
        MenuItem(name='Soft Drink', description='Assorted soft drinks (350ml)', price=12.00, category_id=3, preparation_time=1, calories=140),
        MenuItem(name='Water', description='Bottled water (500ml)', price=8.00, category_id=3, preparation_time=1, calories=0),
        
        # Snacks
        MenuItem(name='Sandwich', description='Ham and cheese sandwich', price=25.00, category_id=4, preparation_time=5, calories=280),
        MenuItem(name='Samosa', description='Crispy vegetable samosa (2 pieces)', price=15.00, category_id=4, preparation_time=5, calories=200),
        MenuItem(name='Fried Chips', description='Seasoned fried potato chips', price=20.00, category_id=4, preparation_time=8, calories=310),
        MenuItem(name='Fruit Salad', description='Fresh seasonal fruits', price=25.00, category_id=4, preparation_time=5, calories=150),
        
        # Vegetarian
        MenuItem(name='Vegetable Curry', description='Mixed vegetables in creamy curry sauce', price=35.00, category_id=5, preparation_time=15, calories=320, is_vegetarian=True, is_vegan=True),
        MenuItem(name='Bean Stew', description='Hearty bean stew with rice', price=30.00, category_id=5, preparation_time=15, calories=280, is_vegetarian=True, is_vegan=True),
        MenuItem(name='Veggie Burger', description='Plant-based burger with all the toppings', price=40.00, category_id=5, preparation_time=10, calories=350, is_vegetarian=True, is_vegan=True),
    ]
    
    for item in menu_items:
        db.session.add(item)
    
    db.session.commit()
    print("Database seeded successfully!")


# Run the application
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)