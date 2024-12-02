#!/usr/bin/env python3

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit
from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import relationship
import jwt
import uuid
from flask_cors import CORS
from flask_migrate import Migrate
import pymysql
pymysql.install_as_MySQLdb()

# Configurations
secret_key = 'cgdr9gdmr5'
sql_alchemy_uri = 'sqlite:///my_database.db'

app = Flask(__name__)
CORS(app, resources={"*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]}})
app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = sql_alchemy_uri
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app)

# Models
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(
        Enum('admin', 'customer', 'sales_rep', name='user_roles'),
        nullable=False
    )

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), nullable=False, unique=True)
    customer_id = db.Column(db.String(36), ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, ForeignKey('product.id'), nullable=False)
    product_quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(
        Enum('pending', 'completed', 'cancelled', name='order_status'),
        nullable=False,
        default='pending'
    )
    customer = relationship('User', foreign_keys=[customer_id])
    product = relationship('Product', foreign_keys=[product_id])


# Endpoints

@app.route('/api/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')

    user = User.query.filter_by(email=email, password=password).first()

    if user:
        token = jwt.encode({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role
        }, secret_key, algorithm='HS256')

        return jsonify({'token': token}), 200
    
    return jsonify({'message': 'Invalid Credentials'}), 401

@app.route('/api/register', methods=['POST'])
def register():
    name = request.json.get('name')
    email = request.json.get('email')
    password = request.json.get('password')

    if not name or not email or not password:
        return jsonify({'message': 'Required fields are missing'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'User already exists'}), 400
    
    user_id = str(uuid.uuid4())
    user = User(id=user_id, name=name, email=email, password=password, role='customer')


    db.session.add(user)
    db.session.commit()

    token = jwt.encode({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'role': user.role
        }, secret_key, algorithm='HS256')

    return jsonify({'token': token}), 201


@app.route('/api/user', methods=['GET'])
def get_user():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401

    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]

    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user = User.query.get(data['id'])
    
    if not user:
        return jsonify({'message': 'User not found'}), 404  # Add this check to return an error if no user is found

    return jsonify({
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200

@app.route('/api/users', methods=['GET'])
def fetch_all_users():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401

    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]


    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user = User.query.get(data['id'])

    if user.role != 'admin':
        return jsonify({'message': 'Permission denied'}), 403
    
    if not user:
        return jsonify({'message': 'User not found'}), 404  # Add this check to return an error if no user is found

    users = User.query.all()

    return jsonify([{
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    } for user in users]), 200
# Product endpoints

@app.route('/api/products', methods=['POST'])
def create_product():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401

    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]

    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user = User.query.get(data['id'])
    if user.role != 'admin':
        return jsonify({'message': 'Permission denied'}), 403

    name = request.json.get('product')
    price = request.json.get('price')
    quantity = request.json.get('quantity')

    if not name or not price or not quantity:
        return jsonify({'message': 'Required fields are missing'}), 400

    product = Product(name=name, price=price, quantity=quantity)
    db.session.add(product)
    db.session.commit()

    return jsonify({'message': 'Product created successfully'}), 201

@app.route('/api/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    products_array = []
    for product in products:
        products_array.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'quantity': product.quantity
        })
    return jsonify(products_array), 200

# Order endpoints

@app.route('/api/orders', methods=['POST'])
def create_order():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401
    
    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]

    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user = User.query.get(data['id'])
    if user.role != 'customer':
        return jsonify({'message': 'Permission denied'}), 403

    product_id = request.json.get('product_id')
    quantity = request.json.get('quantity')

    if not product_id or not quantity:
        return jsonify({'message': 'Required fields are missing'}), 400
    
    if quantity < 1:
        return jsonify({'message': 'Quantity must be greater than 0'}), 400

    product = Product.query.get(product_id)

    if not product:
        return jsonify({'message': 'Product not found'}), 404
    
    if product.quantity < quantity:
        return jsonify({'message': 'Insufficient quantity'}), 400

    order_no = str(uuid.uuid4())
        

    order = Order(order_no=order_no, product_id=product.id, customer_id=user.id, product_quantity=quantity, status='pending')
    db.session.add(order)
    product.quantity -= quantity
    db.session.commit()

    return jsonify({'message': 'Order placed successfully'}), 201

@app.route('/api/orders', methods=['GET'])
def get_orders():
    token = request.headers.get('Authorization')

    # Check if the token exists
    if not token:
        return jsonify({'message': 'Token is missing'}), 401

    # Validate the token format
    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    # Extract the actual token value
    token = token.split(' ')[1]

    # Decode the JWT token
    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    # Fetch the user from the database
    user = User.query.get(data['id'])

    # Check if the user exists
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Fetch orders based on user role
    if user.role == 'admin' or user.role == 'sales_rep':
        orders = Order.query.all()
    else:
        orders = Order.query.filter_by(customer_id=user.id).all()

    # Return the orders as JSON
    return jsonify([{
        'order_no': order.order_no,
        'product_name': order.product.name,
        'product_quantity': order.product_quantity,
        'product_price': order.product.price,
        'status': order.status
    } for order in orders]), 200


@app.route('/api/orders/cancel/<order_id>', methods=['PUT'])
def cancel_order(order_id):
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401
    
    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]

    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user = User.query.get(data['id'])
    if user.role != 'customer':
        return jsonify({'message': 'Permission denied'}), 403

    order = Order.query.filter_by(order_no=order_id).first()

    if not order:
        return jsonify({'message': 'Order not found'}), 404

    if order.status == 'completed':
        return jsonify({'message': 'Order already completed'}), 400
    
    if order.status == 'cancelled':
        return jsonify({'message': 'Order already cancelled'}), 400

    order.status = 'cancelled'
    db.session.commit()

    return jsonify({'message': 'Order cancelled successfully'}), 200


@app.route('/api/orders/complete/<order_id>', methods=['PUT'])
def complete_order(order_id):
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401
    
    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]

    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user = User.query.get(data['id'])
    if user.role != 'sales_rep':
        return jsonify({'message': 'Permission denied'}), 403

    order = Order.query.filter_by(order_no=order_id).first()

    if not order:
        return jsonify({'message': 'Order not found'}), 404

    if order.status == 'completed':
        return jsonify({'message': 'Order already completed'}), 400
    
    if order.status == 'cancelled':
        return jsonify({'message': 'Order already cancelled'}), 400

    order.status = 'completed'
    db.session.commit()

    return jsonify({'message': 'Order completed successfully'}), 200

@app.route('/api/users', methods=['PUT'])
def update_user_role():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing'}), 401
    
    if not token.startswith('Bearer '):
        return jsonify({'message': 'Invalid token format'}), 401

    token = token.split(' ')[1]

    try:
        data = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

    user_id = request.json.get('user_id')
    role = request.json.get('role')
    client_user = User.query.get(user_id)

    user = User.query.get(data['id'])


    if user.role != 'admin':
        return jsonify({'message': 'Permission denied'}), 403


    if not client_user:
        return jsonify({'message': 'User not found'}), 404

    client_user.role = role
    db.session.commit()

    return jsonify({'message': 'Role Changed successfully'}), 200


@socketio.on('connect')
def handle_connect():
    print('A client connected')


@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected')


if __name__ == '__main__':
    socketio.run(app, debug=True)
