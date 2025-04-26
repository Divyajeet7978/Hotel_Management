import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import pdfkit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='staff')  # 'admin' or 'staff'

class Room(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    number = db.Column(db.String(20), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    amenities = db.Column(db.String(200))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='available')  # 'available', 'booked', 'maintenance'
    image = db.Column(db.String(100))

class Customer(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    id_proof = db.Column(db.String(50))
    id_number = db.Column(db.String(50))
    address = db.Column(db.Text)

class Booking(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    room_id = db.Column(db.String(36), db.ForeignKey('room.id'), nullable=False)
    customer_id = db.Column(db.String(36), db.ForeignKey('customer.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')  # 'active', 'completed'
    payment_status = db.Column(db.String(20), default='pending')  # 'pending', 'paid'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    room = db.relationship('Room', backref='bookings')
    customer = db.relationship('Customer', backref='bookings')

# Helper Functions
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid!'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin access required!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

def calculate_total_amount(room_id, check_in, check_out):
    room = Room.query.get(room_id)
    if not room:
        return 0
    
    delta = datetime.strptime(check_out, '%Y-%m-%d') - datetime.strptime(check_in, '%Y-%m-%d')
    return room.price * delta.days

def check_room_availability(room_id, check_in, check_out):
    check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
    check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
    
    conflicting_bookings = Booking.query.filter(
        Booking.room_id == room_id,
        Booking.status == 'active',
        (
            (Booking.check_in <= check_in_date) & (Booking.check_out > check_in_date) |
            (Booking.check_in < check_out_date) & (Booking.check_out >= check_out_date) |
            (Booking.check_in >= check_in_date) & (Booking.check_out <= check_out_date)
        )
    ).count()
    
    return conflicting_bookings == 0

# Routes
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password required!'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials!'}), 401
    
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=8)
    }, app.config['SECRET_KEY'])
    
    return jsonify({
        'success': True,
        'token': token,
        'user': {
            'id': user.id,
            'name': user.name,
            'username': user.username,
            'role': user.role
        }
    })

@app.route('/api/dashboard', methods=['GET'])
@token_required
def dashboard(current_user):
    stats = {
        'total_rooms': Room.query.count(),
        'available_rooms': Room.query.filter_by(status='available').count(),
        'active_bookings': Booking.query.filter_by(status='active').count(),
        'total_customers': Customer.query.count()
    }
    
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
    
    bookings_data = []
    for booking in recent_bookings:
        bookings_data.append({
            'id': booking.id,
            'room': {
                'type': booking.room.type,
                'number': booking.room.number
            },
            'customer': {
                'name': booking.customer.name
            },
            'check_in': booking.check_in.strftime('%Y-%m-%d'),
            'check_out': booking.check_out.strftime('%Y-%m-%d'),
            'total_amount': booking.total_amount,
            'status': booking.status
        })
    
    return jsonify({
        'stats': stats,
        'recent_bookings': bookings_data
    })

@app.route('/api/rooms', methods=['GET', 'POST'])
@token_required
def rooms(current_user):
    if request.method == 'GET':
        # Handle filters
        search = request.args.get('search', '')
        room_type = request.args.get('type', '')
        status = request.args.get('status', '')
        
        query = Room.query
        
        if search:
            query = query.filter(
                (Room.number.contains(search)) |
                (Room.type.contains(search)) |
                (Room.description.contains(search))
            )
        
        if room_type:
            query = query.filter_by(type=room_type)
        
        if status:
            query = query.filter_by(status=status)
        
        rooms = query.all()
        
        rooms_data = []
        for room in rooms:
            rooms_data.append({
                'id': room.id,
                'number': room.number,
                'type': room.type,
                'price': room.price,
                'capacity': room.capacity,
                'amenities': room.amenities,
                'description': room.description,
                'status': room.status,
                'image': room.image
            })
        
        return jsonify({'rooms': rooms_data})
    
    elif request.method == 'POST':
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin access required!'}), 403
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
            else:
                return jsonify({'message': 'Invalid file type!'}), 400
        else:
            unique_filename = None
        
        try:
            room = Room(
                number=request.form['number'],
                type=request.form['type'],
                price=float(request.form['price']),
                capacity=int(request.form['capacity']),
                amenities=request.form.get('amenities', ''),
                description=request.form.get('description', ''),
                image=unique_filename
            )
            db.session.add(room)
            db.session.commit()
            
            return jsonify({
                'message': 'Room added successfully!',
                'room_id': room.id
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 400

@app.route('/api/rooms/<room_id>', methods=['GET', 'DELETE'])
@token_required
def room_detail(current_user, room_id):
    room = Room.query.get_or_404(room_id)
    
    if request.method == 'GET':
        return jsonify({
            'id': room.id,
            'number': room.number,
            'type': room.type,
            'price': room.price,
            'capacity': room.capacity,
            'amenities': room.amenities,
            'description': room.description,
            'status': room.status,
            'image': room.image
        })
    
    elif request.method == 'DELETE':
        if current_user.role != 'admin':
            return jsonify({'message': 'Admin access required!'}), 403
        
        # Check if room has active bookings
        active_bookings = Booking.query.filter_by(room_id=room_id, status='active').count()
        if active_bookings > 0:
            return jsonify({'message': 'Cannot delete room with active bookings!'}), 400
        
        try:
            # Delete associated image if exists
            if room.image:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], room.image))
                except:
                    pass
            
            db.session.delete(room)
            db.session.commit()
            return jsonify({'message': 'Room deleted successfully!'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 400

@app.route('/api/bookings', methods=['GET', 'POST'])
@token_required
def bookings(current_user):
    if request.method == 'GET':
        # Handle filters
        search = request.args.get('search', '')
        status = request.args.get('status', '')
        
        query = Booking.query
        
        if search:
            query = query.join(Room).join(Customer).filter(
                (Room.number.contains(search)) |
                (Room.type.contains(search)) |
                (Customer.name.contains(search)) |
                (Customer.email.contains(search))
            )
        
        if status:
            query = query.filter_by(status=status)
        
        bookings = query.order_by(Booking.created_at.desc()).all()
        
        bookings_data = []
        for booking in bookings:
            bookings_data.append({
                'id': booking.id,
                'room': {
                    'id': booking.room.id,
                    'type': booking.room.type,
                    'number': booking.room.number,
                    'price': booking.room.price
                },
                'customer': {
                    'id': booking.customer.id,
                    'name': booking.customer.name,
                    'email': booking.customer.email,
                    'phone': booking.customer.phone
                },
                'check_in': booking.check_in.strftime('%Y-%m-%d'),
                'check_out': booking.check_out.strftime('%Y-%m-%d'),
                'total_amount': booking.total_amount,
                'status': booking.status,
                'payment_status': booking.payment_status,
                'created_at': booking.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify({'bookings': bookings_data})
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if not data or not data.get('room_id') or not data.get('customer_id') or not data.get('check_in') or not data.get('check_out'):
            return jsonify({'message': 'Missing required fields!'}), 400
        
        # Check room availability
        if not check_room_availability(data['room_id'], data['check_in'], data['check_out']):
            return jsonify({'message': 'Room is not available for the selected dates!'}), 400
        
        # Calculate total amount
        total_amount = calculate_total_amount(data['room_id'], data['check_in'], data['check_out'])
        
        try:
            booking = Booking(
                room_id=data['room_id'],
                customer_id=data['customer_id'],
                check_in=datetime.strptime(data['check_in'], '%Y-%m-%d').date(),
                check_out=datetime.strptime(data['check_out'], '%Y-%m-%d').date(),
                total_amount=total_amount
            )
            
            # Update room status
            room = Room.query.get(data['room_id'])
            room.status = 'booked'
            
            db.session.add(booking)
            db.session.commit()
            
            return jsonify({
                'message': 'Booking created successfully!',
                'booking_id': booking.id
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 400

@app.route('/api/bookings/<booking_id>', methods=['GET'])
@token_required
def booking_detail(current_user, booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    return jsonify({
        'id': booking.id,
        'room': {
            'id': booking.room.id,
            'type': booking.room.type,
            'number': booking.room.number,
            'price': booking.room.price,
            'capacity': booking.room.capacity,
            'amenities': booking.room.amenities,
            'description': booking.room.description,
            'status': booking.room.status,
            'image': booking.room.image
        },
        'customer': {
            'id': booking.customer.id,
            'name': booking.customer.name,
            'email': booking.customer.email,
            'phone': booking.customer.phone,
            'id_proof': booking.customer.id_proof,
            'id_number': booking.customer.id_number,
            'address': booking.customer.address
        },
        'check_in': booking.check_in.strftime('%Y-%m-%d'),
        'check_out': booking.check_out.strftime('%Y-%m-%d'),
        'total_amount': booking.total_amount,
        'status': booking.status,
        'payment_status': booking.payment_status,
        'created_at': booking.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/bookings/<booking_id>/checkout', methods=['POST'])
@token_required
def checkout_booking(current_user, booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    if booking.status != 'active':
        return jsonify({'message': 'Booking is not active!'}), 400
    
    try:
        # Update booking status
        booking.status = 'completed'
        booking.payment_status = 'paid'
        
        # Update room status
        room = Room.query.get(booking.room_id)
        room.status = 'available'
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Checkout completed successfully!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@app.route('/api/customers', methods=['GET', 'POST'])
@token_required
def customers(current_user):
    if request.method == 'GET':
        # Handle search
        search = request.args.get('search', '')
        
        query = Customer.query
        
        if search:
            query = query.filter(
                (Customer.name.contains(search)) |
                (Customer.email.contains(search)) |
                (Customer.phone.contains(search)) |
                (Customer.id_number.contains(search))
            )
        
        customers = query.order_by(Customer.name).all()
        
        customers_data = []
        for customer in customers:
            customers_data.append({
                'id': customer.id,
                'name': customer.name,
                'email': customer.email,
                'phone': customer.phone,
                'id_proof': customer.id_proof,
                'id_number': customer.id_number,
                'address': customer.address
            })
        
        return jsonify({'customers': customers_data})
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if not data or not data.get('name') or not data.get('email') or not data.get('phone'):
            return jsonify({'message': 'Missing required fields!'}), 400
        
        try:
            customer = Customer(
                name=data['name'],
                email=data['email'],
                phone=data['phone'],
                id_proof=data.get('id_proof'),
                id_number=data.get('id_number'),
                address=data.get('address')
            )
            
            db.session.add(customer)
            db.session.commit()
            
            return jsonify({
                'message': 'Customer added successfully!',
                'customer_id': customer.id
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 400

@app.route('/api/customers/<customer_id>', methods=['PUT'])
@token_required
def update_customer(current_user, customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'message': 'No data provided!'}), 400
    
    try:
        if 'name' in data:
            customer.name = data['name']
        if 'email' in data:
            customer.email = data['email']
        if 'phone' in data:
            customer.phone = data['phone']
        if 'id_proof' in data:
            customer.id_proof = data['id_proof']
        if 'id_number' in data:
            customer.id_number = data['id_number']
        if 'address' in data:
            customer.address = data['address']
        
        db.session.commit()
        
        return jsonify({
            'message': 'Customer updated successfully!',
            'customer_id': customer.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@app.route('/api/invoice/<booking_id>', methods=['GET'])
@token_required
def generate_invoice(current_user, booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Calculate duration
    duration = (booking.check_out - booking.check_in).days
    
    # HTML template for the invoice
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice #{booking.id[:8]}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .invoice-container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .hotel-name {{ font-size: 24px; font-weight: bold; }}
            .invoice-title {{ font-size: 20px; margin-top: 10px; }}
            .details {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
            .section {{ margin-bottom: 20px; }}
            .section-title {{ font-weight: bold; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f5f5f5; }}
            .total {{ text-align: right; font-weight: bold; font-size: 18px; }}
            .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="invoice-container">
            <div class="header">
                <div class="hotel-name">Hotel Management System</div>
                <div class="invoice-title">INVOICE</div>
            </div>
            
            <div class="details">
                <div>
                    <div><strong>Invoice #:</strong> {booking.id[:8]}</div>
                    <div><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</div>
                </div>
                <div>
                    <div><strong>Customer:</strong> {booking.customer.name}</div>
                    <div><strong>Status:</strong> {booking.status.capitalize()}</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Booking Details</div>
                <div><strong>Room:</strong> {booking.room.type} (Room #{booking.room.number})</div>
                <div><strong>Check-in:</strong> {booking.check_in.strftime('%Y-%m-%d')}</div>
                <div><strong>Check-out:</strong> {booking.check_out.strftime('%Y-%m-%d')}</div>
                <div><strong>Duration:</strong> {duration} nights</div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Rate</th>
                        <th>Nights</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Room {booking.room.number} ({booking.room.type})</td>
                        <td>${booking.room.price:.2f}</td>
                        <td>{duration}</td>
                        <td>${booking.total_amount:.2f}</td>
                    </tr>
                </tbody>
            </table>
            
            <div class="total">
                Total Amount: ${booking.total_amount:.2f}
            </div>
            
            <div class="footer">
                Thank you for your stay! We hope to see you again soon.
            </div>
        </div>
    </body>
    </html>
    """
    
    # Generate PDF from HTML
    try:
        pdf = pdfkit.from_string(html, False, options={
            'encoding': 'UTF-8',
            'quiet': ''
        })
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=invoice_{booking.id[:8]}.pdf'
        return response
    except Exception as e:
        return jsonify({'message': f'Failed to generate invoice: {str(e)}'}), 500

@app.route('/api/room-image/<filename>', methods=['GET'])
def get_room_image(filename):
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    except FileNotFoundError:
        return jsonify({'message': 'Image not found'}), 404

# Initialize database and create admin user
@app._got_first_request
def initialize():
    db.create_all()
    
    # Create admin user if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            name='Admin',
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)