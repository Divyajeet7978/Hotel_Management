import os
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import json
import uuid
from datetime import datetime, timedelta
import pdfkit
from faker import Faker
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = 'your-secret-key-here'

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Mock database
db = {
    'users': {
        'admin': {
            'password': generate_password_hash('admin123'),
            'role': 'admin',
            'name': 'Admin User'
        },
        'staff': {
            'password': generate_password_hash('staff123'),
            'role': 'staff',
            'name': 'Staff Member'
        }
    },
    'rooms': [],
    'bookings': [],
    'customers': []
}

# Initialize with fake data
fake = Faker()
if not db['rooms']:
    room_types = ['Deluxe', 'Standard', 'Suite', 'Executive']
    for i in range(1, 21):
        db['rooms'].append({
            'id': i,
            'number': f"{i:03d}",
            'type': fake.random_element(room_types),
            'price': fake.random_int(80, 300),
            'capacity': fake.random_int(1, 4),
            'description': fake.sentence(),
            'amenities': ', '.join(fake.words(5)),
            'status': 'available',
            'image': f'https://raw.githubusercontent.com/Divyajeet7978/Hotel_Management/main/images/{fake.random_element(room_types)}.png'
        })

if not db['customers']:
    for i in range(1, 11):
        db['customers'].append({
            'id': str(uuid.uuid4()),
            'name': fake.name(),
            'email': fake.email(),
            'phone': fake.phone_number(),
            'address': fake.address(),
            'id_proof': 'AADHAR' if i % 2 else 'PASSPORT',
            'id_number': fake.random_number(digits=12)
        })

if not db['bookings']:
    for i in range(1, 6):
        check_in = fake.date_between(start_date='-30d', end_date='today')
        check_out = check_in + timedelta(days=fake.random_int(1, 14))
        room = fake.random_element(db['rooms'])
        customer = fake.random_element(db['customers'])
        
        db['bookings'].append({
            'id': str(uuid.uuid4()),
            'room_id': room['id'],
            'customer_id': customer['id'],
            'check_in': check_in.strftime('%Y-%m-%d'),
            'check_out': check_out.strftime('%Y-%m-%d'),
            'status': 'completed' if check_out < datetime.now().date() else 'active',
            'total_amount': room['price'] * (check_out - check_in).days,
            'payment_status': 'paid',
            'created_at': (check_in - timedelta(days=fake.random_int(1, 30))).strftime('%Y-%m-%d')
        })

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'message': 'Authentication required'}), 401
        
        token = auth_header.split(' ')[1]
        if token not in db['users']:
            return jsonify({'message': 'Invalid credentials'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

# API Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    if username not in db['users']:
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    
    if not check_password_hash(db['users'][username]['password'], password):
        return jsonify({'success': False, 'message': 'Invalid credentials'})
    
    return jsonify({
        'success': True,
        'token': username,
        'user': {
            'username': username,
            'name': db['users'][username]['name'],
            'role': db['users'][username]['role']
        }
    })

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    total_rooms = len(db['rooms'])
    available_rooms = len([r for r in db['rooms'] if r['status'] == 'available'])
    active_bookings = len([b for b in db['bookings'] if b['status'] == 'active'])
    total_customers = len(db['customers'])
    
    recent_bookings = sorted(db['bookings'], key=lambda x: x['created_at'], reverse=True)[:5]
    
    detailed_bookings = []
    for booking in recent_bookings:
        room = next((r for r in db['rooms'] if r['id'] == booking['room_id']), None)
        customer = next((c for c in db['customers'] if c['id'] == booking['customer_id']), None)
        
        if room and customer:
            detailed_booking = booking.copy()
            detailed_booking['room'] = room
            detailed_booking['customer'] = customer
            detailed_bookings.append(detailed_booking)
    
    return jsonify({
        'stats': {
            'total_rooms': total_rooms,
            'available_rooms': available_rooms,
            'active_bookings': active_bookings,
            'total_customers': total_customers
        },
        'recent_bookings': detailed_bookings
    })

@app.route('/api/rooms', methods=['GET', 'POST'])
@login_required
def manage_rooms():
    if request.method == 'GET':
        search = request.args.get('search', '')
        room_type = request.args.get('type', '')
        status = request.args.get('status', '')
        
        filtered_rooms = db['rooms']
        
        if search:
            filtered_rooms = [r for r in filtered_rooms if search.lower() in r['number'].lower() or search.lower() in r['type'].lower()]
        
        if room_type:
            filtered_rooms = [r for r in filtered_rooms if r['type'].lower() == room_type.lower()]
        
        if status:
            filtered_rooms = [r for r in filtered_rooms if r['status'].lower() == status.lower()]
        
        return jsonify({'rooms': filtered_rooms})
    
    elif request.method == 'POST':
        image_url = 'https://raw.githubusercontent.com/Divyajeet7978/Hotel_Management/main/images/Standard.png'
        
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"room_{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f'/static/uploads/{filename}'
        
        data = request.form
        
        required_fields = ['number', 'type', 'price', 'capacity']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        new_room = {
            'id': len(db['rooms']) + 1,
            'number': data['number'],
            'type': data['type'],
            'price': float(data['price']),
            'capacity': int(data['capacity']),
            'description': data.get('description', ''),
            'amenities': data.get('amenities', ''),
            'status': 'available',
            'image': image_url
        }
        
        db['rooms'].append(new_room)
        return jsonify({'success': True, 'room': new_room}), 201

@app.route('/api/rooms/<int:room_id>', methods=['GET', 'DELETE'])
@login_required
def manage_room(room_id):
    if request.method == 'GET':
        room = next((r for r in db['rooms'] if r['id'] == room_id), None)
        if not room:
            return jsonify({'message': 'Room not found'}), 404
        return jsonify(room)
    
    elif request.method == 'DELETE':
        room = next((r for r in db['rooms'] if r['id'] == room_id), None)
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404
        
        active_bookings = [b for b in db['bookings'] 
                          if b['room_id'] == room_id and b['status'] == 'active']
        
        if active_bookings:
            return jsonify({
                'success': False,
                'message': 'Cannot delete room with active bookings'
            }), 400
        
        db['rooms'] = [r for r in db['rooms'] if r['id'] != room_id]
        return jsonify({'success': True, 'message': 'Room deleted successfully'})

@app.route('/api/bookings', methods=['GET', 'POST'])
@login_required
def manage_bookings():
    if request.method == 'GET':
        status = request.args.get('status', '')
        search = request.args.get('search', '')
        
        bookings = db['bookings']
        
        if status:
            bookings = [b for b in bookings if b['status'] == status]
        
        if search:
            bookings = [b for b in bookings if search.lower() in b['id'].lower()]
        
        detailed_bookings = []
        for booking in bookings:
            room = next((r for r in db['rooms'] if r['id'] == booking['room_id']), None)
            customer = next((c for c in db['customers'] if c['id'] == booking['customer_id']), None)
            
            if room and customer:
                detailed_booking = booking.copy()
                detailed_booking['room'] = room
                detailed_booking['customer'] = customer
                detailed_bookings.append(detailed_booking)
        
        return jsonify({'bookings': detailed_bookings})
    
    elif request.method == 'POST':
        data = request.get_json()
        
        required_fields = ['room_id', 'customer_id', 'check_in', 'check_out']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        room = next((r for r in db['rooms'] if r['id'] == data['room_id']), None)
        if not room:
            return jsonify({'success': False, 'message': 'Room not found'}), 404
        
        customer = next((c for c in db['customers'] if c['id'] == data['customer_id']), None)
        if not customer:
            return jsonify({'success': False, 'message': 'Customer not found'}), 404
        
        check_in = datetime.strptime(data['check_in'], '%Y-%m-%d').date()
        check_out = datetime.strptime(data['check_out'], '%Y-%m-%d').date()
        
        conflicting_bookings = [
            b for b in db['bookings'] 
            if b['room_id'] == data['room_id'] and b['status'] == 'active' and 
            not (check_out <= datetime.strptime(b['check_in'], '%Y-%m-%d').date() or 
                 check_in >= datetime.strptime(b['check_out'], '%Y-%m-%d').date())
        ]
        
        if conflicting_bookings:
            return jsonify({
                'success': False,
                'message': 'Room is already booked for the selected dates'
            }), 400
        
        booking_id = str(uuid.uuid4())
        days = (check_out - check_in).days
        total_amount = room['price'] * days
        
        new_booking = {
            'id': booking_id,
            'room_id': data['room_id'],
            'customer_id': data['customer_id'],
            'check_in': data['check_in'],
            'check_out': data['check_out'],
            'status': 'active',
            'total_amount': total_amount,
            'payment_status': 'pending',
            'created_at': datetime.now().strftime('%Y-%m-%d')
        }
        
        db['bookings'].append(new_booking)
        room['status'] = 'booked'
        
        return jsonify({
            'success': True,
            'booking': new_booking
        }), 201

@app.route('/api/bookings/<booking_id>', methods=['GET'])
@login_required
def get_booking(booking_id):
    booking = next((b for b in db['bookings'] if b['id'] == booking_id), None)
    if not booking:
        return jsonify({'message': 'Booking not found'}), 404
    
    room = next((r for r in db['rooms'] if r['id'] == booking['room_id']), None)
    customer = next((c for c in db['customers'] if c['id'] == booking['customer_id']), None)
    
    if not room or not customer:
        return jsonify({'message': 'Room or customer not found'}), 404
    
    detailed_booking = booking.copy()
    detailed_booking['room'] = room
    detailed_booking['customer'] = customer
    
    return jsonify(detailed_booking)

@app.route('/api/bookings/<booking_id>/checkout', methods=['POST'])
@login_required
def checkout_booking(booking_id):
    booking = next((b for b in db['bookings'] if b['id'] == booking_id), None)
    if not booking:
        return jsonify({'success': False, 'message': 'Booking not found'}), 404
    
    if booking['status'] == 'completed':
        return jsonify({'success': False, 'message': 'Booking already completed'}), 400
    
    booking['status'] = 'completed'
    booking['payment_status'] = 'paid'
    
    room = next((r for r in db['rooms'] if r['id'] == booking['room_id']), None)
    if room:
        room['status'] = 'available'
    
    return jsonify({'success': True, 'message': 'Checkout completed successfully'})

@app.route('/api/customers', methods=['GET', 'POST'])
@login_required
def manage_customers():
    if request.method == 'GET':
        search = request.args.get('search', '')
        
        customers = db['customers']
        
        if search:
            customers = [c for c in customers if search.lower() in c['name'].lower() or search.lower() in c['email'].lower()]
        
        return jsonify({'customers': customers})
    
    elif request.method == 'POST':
        data = request.get_json()
        
        required_fields = ['name', 'email', 'phone']
        if not all(field in data for field in required_fields):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        customer_id = str(uuid.uuid4())
        
        new_customer = {
            'id': customer_id,
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'address': data.get('address', ''),
            'id_proof': data.get('id_proof', ''),
            'id_number': data.get('id_number', '')
        }
        
        db['customers'].append(new_customer)
        
        return jsonify({
            'success': True,
            'customer': new_customer
        }), 201

@app.route('/api/invoice/<booking_id>', methods=['GET'])
@login_required
def generate_invoice(booking_id):
    booking = next((b for b in db['bookings'] if b['id'] == booking_id), None)
    if not booking:
        return jsonify({'message': 'Booking not found'}), 404
    
    room = next((r for r in db['rooms'] if r['id'] == booking['room_id']), None)
    customer = next((c for c in db['customers'] if c['id'] == booking['customer_id']), None)
    
    if not room or not customer:
        return jsonify({'message': 'Room or customer not found'}), 404
    
    invoice_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice - {booking_id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .invoice {{ width: 80%; margin: 0 auto; padding: 20px; border: 1px solid #eee; }}
            .header {{ text-align: center; margin-bottom: 20px; }}
            .details {{ margin-bottom: 30px; }}
            .table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
            .table th, .table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            .table th {{ background-color: #f2f2f2; }}
            .total {{ text-align: right; font-weight: bold; font-size: 1.2em; }}
        </style>
    </head>
    <body>
        <div class="invoice">
            <div class="header">
                <h1>Hotel Grand Plaza</h1>
                <p>123 Luxury Street, Hospitality City</p>
                <h2>INVOICE</h2>
                <p>Invoice #: {booking_id}</p>
            </div>
            
            <div class="details">
                <div style="float: left; width: 50%;">
                    <h3>Bill To:</h3>
                    <p>{customer['name']}</p>
                    <p>{customer['email']}</p>
                    <p>{customer['phone']}</p>
                </div>
                <div style="float: right; width: 50%; text-align: right;">
                    <p><strong>Invoice Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
                    <p><strong>Check-in:</strong> {booking['check_in']}</p>
                    <p><strong>Check-out:</strong> {booking['check_out']}</p>
                </div>
                <div style="clear: both;"></div>
            </div>
            
            <table class="table">
                <thead>
                    <tr>
                        <th>Description</th>
                        <th>Quantity</th>
                        <th>Unit Price</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{room['type']} Room (Room #{room['number']})</td>
                        <td>{(datetime.strptime(booking['check_out'], '%Y-%m-%d') - datetime.strptime(booking['check_in'], '%Y-%m-%d')).days} nights</td>
                        <td>${room['price']}</td>
                        <td>${booking['total_amount']}</td>
                    </tr>
                </tbody>
            </table>
            
            <div class="total">
                <p>Total Amount: ${booking['total_amount']}</p>
                <p>Payment Status: {booking['payment_status'].capitalize()}</p>
            </div>
            
            <div style="margin-top: 50px; text-align: center;">
                <p>Thank you for staying with us!</p>
                <p>Hotel Grand Plaza</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        pdf = pdfkit.from_string(invoice_html, False)
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=invoice_{booking_id}.pdf'
        return response
    except Exception as e:
        return jsonify({'message': f'Failed to generate PDF: {str(e)}'}), 500

@app.route('/static/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)