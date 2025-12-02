from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta  # Add timedelta to the import
import os
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cultural_tours.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------ MODELS ------------

class Place(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    state = db.Column(db.String(50), nullable=False)  # Karnataka, Tamil Nadu, etc.
    city = db.Column(db.String(80), nullable=True)
    short_intro = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    culture_description = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(300), nullable=True)
    video_url = db.Column(db.String(300), nullable=True)
    price_per_person = db.Column(db.Float, nullable=False, default=0.0)
    duration_days = db.Column(db.Integer, nullable=False, default=2)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(db.Integer, db.ForeignKey('place.id'), nullable=False)
    place = db.relationship('Place', backref=db.backref('bookings', lazy=True))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    travel_date = db.Column(db.Date, nullable=False)
    num_people = db.Column(db.Integer, nullable=False)
    special_requests = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pending')  # Pending / Confirmed / Rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
# Add these new models after the existing ones in app.py

class Hotel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(db.Integer, db.ForeignKey('place.id'), nullable=False)
    place = db.relationship('Place', backref=db.backref('hotels', lazy=True))
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price_per_night = db.Column(db.Float, nullable=False, default=0.0)
    rating = db.Column(db.Float, nullable=True)  # 1-5 stars
    amenities = db.Column(db.String(300), nullable=True)  # comma separated
    image_url = db.Column(db.String(300), nullable=True)
    contact_info = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    place_id = db.Column(db.Integer, db.ForeignKey('place.id'), nullable=False)
    place = db.relationship('Place', backref=db.backref('transports', lazy=True))
    transport_type = db.Column(db.String(20), nullable=False)  # bus, cab, train
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False, default=0.0)
    capacity = db.Column(db.Integer, nullable=True)
    duration_hours = db.Column(db.Float, nullable=True)
    operating_hours = db.Column(db.String(100), nullable=True)
    contact_info = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServiceBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # Main booking reference
    main_booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=True)
    main_booking = db.relationship('Booking', backref=db.backref('service_bookings', lazy=True))
    
    # Direct booking without main tour booking
    customer_name = db.Column(db.String(120), nullable=True)
    customer_email = db.Column(db.String(120), nullable=True)
    customer_phone = db.Column(db.String(20), nullable=True)
    
    place_id = db.Column(db.Integer, db.ForeignKey('place.id'), nullable=False)
    place = db.relationship('Place', backref=db.backref('service_bookings', lazy=True))
    
    # Service details
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=True)
    hotel = db.relationship('Hotel', backref=db.backref('service_bookings', lazy=True))
    transport_id = db.Column(db.Integer, db.ForeignKey('transport.id'), nullable=True)
    transport = db.relationship('Transport', backref=db.backref('service_bookings', lazy=True))
    
    # Booking details
    check_in_date = db.Column(db.Date, nullable=True)
    check_out_date = db.Column(db.Date, nullable=True)
    num_people = db.Column(db.Integer, nullable=False, default=1)
    num_rooms = db.Column(db.Integer, nullable=False, default=1)
    num_days = db.Column(db.Integer, nullable=False, default=1)
    special_requests = db.Column(db.Text, nullable=True)
    
    # Pricing
    hotel_total = db.Column(db.Float, nullable=False, default=0.0)
    transport_total = db.Column(db.Float, nullable=False, default=0.0)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    
    status = db.Column(db.String(20), default='Pending')  # Pending / Confirmed / Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ------------ SIMPLE ADMIN CONFIG ------------

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"  # change in production


def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper


# ------------ PUBLIC ROUTES ------------
def to_youtube_embed(url: str) -> str:
    if not url:
        return ""

    parsed = urlparse(url)

    # https://www.youtube.com/watch?v=XXXX
    if 'youtube.com' in parsed.netloc and parsed.path == '/watch':
        video_id = parse_qs(parsed.query).get('v', [''])[0]
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    # https://youtu.be/XXXX
    if 'youtu.be' in parsed.netloc:
        video_id = parsed.path.lstrip('/')
        if video_id:
            return f"https://www.youtube.com/embed/{video_id}"

    # already an embed or something else
    return url

@app.template_filter('youtube_embed')
def youtube_embed(url):
    return to_youtube_embed(url)
@app.route('/')
def index():
    state_filter = request.args.get('state')
    query = Place.query
    if state_filter:
        query = query.filter_by(state=state_filter)
    places = query.order_by(Place.created_at.desc()).all()

    # Preload related data
    for place in places:
        place.hotels = Hotel.query.filter_by(place_id=place.id).all()
        place.transports = Transport.query.filter_by(place_id=place.id).all()

    states = ["Karnataka", "Tamil Nadu", "Andhra Pradesh", "Maharashtra"]
    return render_template('index.html', places=places, states=states, selected_state=state_filter)


@app.route('/place/<int:place_id>')
def place_detail(place_id):
    place = Place.query.get_or_404(place_id)
    return render_template('place_detail.html', place=place)


@app.route('/book/<int:place_id>', methods=['GET', 'POST'])
def book_place(place_id):
    place = Place.query.get_or_404(place_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        travel_date_str = request.form.get('travel_date', '')
        num_people = request.form.get('num_people', '1')
        special_requests = request.form.get('special_requests', '').strip()

        if not (name and email and phone and travel_date_str):
            flash("All required fields must be filled.", "danger")
            return redirect(url_for('book_place', place_id=place.id))

        try:
            travel_date = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid travel date.", "danger")
            return redirect(url_for('book_place', place_id=place.id))

        # Check if travel date is in the past
        if travel_date < datetime.now().date():
            flash("Travel date cannot be in the past.", "danger")
            return redirect(url_for('book_place', place_id=place.id))

        try:
            num_people = int(num_people)
            if num_people <= 0:
                raise ValueError
        except ValueError:
            flash("Number of people must be a positive number.", "danger")
            return redirect(url_for('book_place', place_id=place.id))

        # Check if user already has a booking on the same date
        existing_booking = Booking.query.filter(
            Booking.email == email,
            Booking.travel_date == travel_date,
            Booking.status.in_(['Pending', 'Confirmed'])
        ).first()

        if existing_booking:
            flash(f"You already have a booking on {travel_date_str}. Please choose a different date or contact us to modify your existing booking.", "danger")
            return redirect(url_for('book_place', place_id=place.id))

        booking = Booking(
            place_id=place.id,
            name=name,
            email=email,
            phone=phone,
            travel_date=travel_date,
            num_people=num_people,
            special_requests=special_requests
        )
        db.session.add(booking)
        db.session.commit()
        flash("Your booking request has been submitted!", "success")
        return redirect(url_for('booking_success', booking_id=booking.id))

    return render_template('booking_form.html', place=place)

@app.route('/booking-success/<int:booking_id>')
def booking_success(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    return render_template('booking_success.html', booking=booking)


# ------------ ADMIN ROUTES ------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            flash("Logged in as admin.", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('admin_login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    session.pop('admin_logged_in', None)
    flash("Logged out.", "info")
    return redirect(url_for('index'))


@app.route('/admin')
@login_required
def admin_dashboard():
    total_places = Place.query.count()
    total_bookings = Booking.query.count()
    pending = Booking.query.filter_by(status='Pending').count()
    hotels_count = Hotel.query.count()
    
    return render_template(
        'admin_dashboard.html',
        total_places=total_places,
        total_bookings=total_bookings,
        pending=pending,
        hotels_count=hotels_count
    )


@app.route('/admin/places')
@login_required
def admin_places():
    places = Place.query.order_by(Place.created_at.desc()).all()
    return render_template('admin_places.html', places=places)
@app.route('/admin/places/<int:place_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_place(place_id):
    place = Place.query.get_or_404(place_id)
    
    if request.method == 'POST':
        place.name = request.form.get('name', '').strip()
        place.state = request.form.get('state', '').strip()
        place.city = request.form.get('city', '').strip()
        place.short_intro = request.form.get('short_intro', '').strip()
        place.description = request.form.get('description', '').strip()
        place.culture_description = request.form.get('culture_description', '').strip()
        place.image_url = request.form.get('image_url', '').strip()
        place.video_url = request.form.get('video_url', '').strip()
        price_per_person = request.form.get('price_per_person', '0')
        duration_days = request.form.get('duration_days', '1')

        if not (place.name and place.state and place.short_intro and place.description and place.culture_description):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('admin_edit_place', place_id=place.id))

        try:
            place.price_per_person = float(price_per_person)
        except ValueError:
            place.price_per_person = 0.0

        try:
            place.duration_days = int(duration_days)
        except ValueError:
            place.duration_days = 1

        db.session.commit()
        flash("Place updated successfully.", "success")
        return redirect(url_for('admin_places'))

    states = ["Karnataka", "Tamil Nadu", "Andhra Pradesh", "Maharashtra"]
    return render_template('admin_edit_place.html', place=place, states=states)


@app.route('/admin/places/<int:place_id>/delete', methods=['POST'])
@login_required
def admin_delete_place(place_id):
    place = Place.query.get_or_404(place_id)
    
    # Check if there are any bookings for this place
    has_bookings = Booking.query.filter_by(place_id=place_id).first() is not None
    
    if has_bookings:
        flash("Cannot delete this place because there are existing bookings. Please delete the bookings first or mark the place as inactive.", "danger")
    else:
        db.session.delete(place)
        db.session.commit()
        flash("Place deleted successfully.", "success")
    
    return redirect(url_for('admin_places'))


@app.route('/admin/places/add', methods=['GET', 'POST'])
@login_required
def admin_add_place():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        state = request.form.get('state', '').strip()
        city = request.form.get('city', '').strip()
        short_intro = request.form.get('short_intro', '').strip()
        description = request.form.get('description', '').strip()
        culture_description = request.form.get('culture_description', '').strip()
        image_url = request.form.get('image_url', '').strip()
        video_url = request.form.get('video_url', '').strip()
        price_per_person = request.form.get('price_per_person', '0')
        duration_days = request.form.get('duration_days', '1')

        if not (name and state and short_intro and description and culture_description):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('admin_add_place'))

        try:
            price_per_person = float(price_per_person)
        except ValueError:
            price_per_person = 0.0

        try:
            duration_days = int(duration_days)
        except ValueError:
            duration_days = 1

        place = Place(
            name=name,
            state=state,
            city=city,
            short_intro=short_intro,
            description=description,
            culture_description=culture_description,
            image_url=image_url or None,
            video_url=video_url or None,
            price_per_person=price_per_person,
            duration_days=duration_days
        )
        db.session.add(place)
        db.session.commit()
        flash("Place added successfully.", "success")
        return redirect(url_for('admin_places'))

    states = ["Karnataka", "Tamil Nadu", "Andhra Pradesh", "Maharashtra"]
    return render_template('admin_add_place.html', states=states)
@app.route('/admin/hotels')
@login_required
def admin_hotels():
    hotels = Hotel.query.order_by(Hotel.created_at.desc()).all()
    places = Place.query.all()
    return render_template('admin_hotels.html', hotels=hotels, places=places)

@app.route('/admin/hotels/add', methods=['GET', 'POST'])
@login_required
def admin_add_hotel():
    if request.method == 'POST':
        place_id = request.form.get('place_id')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price_per_night = request.form.get('price_per_night', '0')
        rating = request.form.get('rating', '')
        amenities = request.form.get('amenities', '').strip()
        image_url = request.form.get('image_url', '').strip()
        contact_info = request.form.get('contact_info', '').strip()

        if not (place_id and name):
            flash("Place and name are required.", "danger")
            return redirect(url_for('admin_add_hotel'))

        try:
            price_per_night = float(price_per_night)
        except ValueError:
            price_per_night = 0.0

        try:
            rating = float(rating) if rating else None
        except ValueError:
            rating = None

        hotel = Hotel(
            place_id=place_id,
            name=name,
            description=description or None,
            price_per_night=price_per_night,
            rating=rating,
            amenities=amenities or None,
            image_url=image_url or None,
            contact_info=contact_info or None
        )
        db.session.add(hotel)
        db.session.commit()
        flash("Hotel added successfully.", "success")
        return redirect(url_for('admin_hotels'))

    places = Place.query.all()
    return render_template('admin_add_hotel.html', places=places)
@app.route('/admin/hotels/<int:hotel_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_hotel(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    
    if request.method == 'POST':
        hotel.place_id = request.form.get('place_id')
        hotel.name = request.form.get('name', '').strip()
        hotel.description = request.form.get('description', '').strip()
        price_per_night = request.form.get('price_per_night', '0')
        rating = request.form.get('rating', '')
        hotel.amenities = request.form.get('amenities', '').strip()
        hotel.image_url = request.form.get('image_url', '').strip()
        hotel.contact_info = request.form.get('contact_info', '').strip()

        if not (hotel.place_id and hotel.name):
            flash("Place and name are required.", "danger")
            return redirect(url_for('admin_edit_hotel', hotel_id=hotel.id))

        try:
            hotel.price_per_night = float(price_per_night)
        except ValueError:
            hotel.price_per_night = 0.0

        try:
            hotel.rating = float(rating) if rating else None
        except ValueError:
            hotel.rating = None

        db.session.commit()
        flash("Hotel updated successfully.", "success")
        return redirect(url_for('admin_hotels'))

    places = Place.query.all()
    return render_template('admin_edit_hotel.html', hotel=hotel, places=places)

@app.route('/admin/hotels/<int:hotel_id>/delete', methods=['POST'])
@login_required
def admin_delete_hotel(hotel_id):
    hotel = Hotel.query.get_or_404(hotel_id)
    
    # Check if there are any service bookings for this hotel
    has_bookings = ServiceBooking.query.filter_by(hotel_id=hotel_id).first() is not None
    
    if has_bookings:
        flash("Cannot delete this hotel because there are existing service bookings. Please delete the bookings first or mark the hotel as inactive.", "danger")
    else:
        db.session.delete(hotel)
        db.session.commit()
        flash("Hotel deleted successfully.", "success")
    
    return redirect(url_for('admin_hotels'))

@app.route('/admin/transport')
@login_required
def admin_transport():
    transports = Transport.query.order_by(Transport.created_at.desc()).all()
    places = Place.query.all()
    return render_template('admin_transport.html', transports=transports, places=places)

@app.route('/admin/transport/add', methods=['GET', 'POST'])
@login_required
def admin_add_transport():
    if request.method == 'POST':
        place_id = request.form.get('place_id')
        transport_type = request.form.get('transport_type')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        capacity = request.form.get('capacity', '')
        duration_hours = request.form.get('duration_hours', '')
        operating_hours = request.form.get('operating_hours', '').strip()
        contact_info = request.form.get('contact_info', '').strip()

        if not (place_id and transport_type and name):
            flash("Place, transport type and name are required.", "danger")
            return redirect(url_for('admin_add_transport'))

        try:
            price = float(price)
        except ValueError:
            price = 0.0

        try:
            capacity = int(capacity) if capacity else None
        except ValueError:
            capacity = None

        try:
            duration_hours = float(duration_hours) if duration_hours else None
        except ValueError:
            duration_hours = None

        transport = Transport(
            place_id=place_id,
            transport_type=transport_type,
            name=name,
            description=description or None,
            price=price,
            capacity=capacity,
            duration_hours=duration_hours,
            operating_hours=operating_hours or None,
            contact_info=contact_info or None
        )
        db.session.add(transport)
        db.session.commit()
        flash("Transport service added successfully.", "success")
        return redirect(url_for('admin_transport'))

    places = Place.query.all()
    return render_template('admin_add_transport.html', places=places)
@app.route('/admin/transport/<int:transport_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_transport(transport_id):
    transport = Transport.query.get_or_404(transport_id)
    
    if request.method == 'POST':
        transport.place_id = request.form.get('place_id')
        transport.transport_type = request.form.get('transport_type')
        transport.name = request.form.get('name', '').strip()
        transport.description = request.form.get('description', '').strip()
        price = request.form.get('price', '0')
        capacity = request.form.get('capacity', '')
        duration_hours = request.form.get('duration_hours', '')
        transport.operating_hours = request.form.get('operating_hours', '').strip()
        transport.contact_info = request.form.get('contact_info', '').strip()

        if not (transport.place_id and transport.transport_type and transport.name):
            flash("Place, transport type and name are required.", "danger")
            return redirect(url_for('admin_edit_transport', transport_id=transport.id))

        try:
            transport.price = float(price)
        except ValueError:
            transport.price = 0.0

        try:
            transport.capacity = int(capacity) if capacity else None
        except ValueError:
            transport.capacity = None

        try:
            transport.duration_hours = float(duration_hours) if duration_hours else None
        except ValueError:
            transport.duration_hours = None

        db.session.commit()
        flash("Transport service updated successfully.", "success")
        return redirect(url_for('admin_transport'))

    places = Place.query.all()
    return render_template('admin_edit_transport.html', transport=transport, places=places)

@app.route('/admin/transport/<int:transport_id>/delete', methods=['POST'])
@login_required
def admin_delete_transport(transport_id):
    transport = Transport.query.get_or_404(transport_id)
    
    # Check if there are any service bookings for this transport
    has_bookings = ServiceBooking.query.filter_by(transport_id=transport_id).first() is not None
    
    if has_bookings:
        flash("Cannot delete this transport service because there are existing service bookings. Please delete the bookings first or mark the transport as inactive.", "danger")
    else:
        db.session.delete(transport)
        db.session.commit()
        flash("Transport service deleted successfully.", "success")
    
    return redirect(url_for('admin_transport'))

@app.route('/book-services/<int:place_id>', methods=['GET', 'POST'])
def book_services(place_id):
    place = Place.query.get_or_404(place_id)
    
    if request.method == 'POST':
        # Get form data
        customer_name = request.form.get('customer_name', '').strip()
        customer_email = request.form.get('customer_email', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        hotel_id = request.form.get('hotel_id')
        transport_id = request.form.get('transport_id')
        check_in_str = request.form.get('check_in', '')
        check_out_str = request.form.get('check_out', '')
        num_people = request.form.get('num_people', '1')
        num_rooms = request.form.get('num_rooms', '1')
        special_requests = request.form.get('special_requests', '').strip()
        
        # Validation
        if not (customer_name and customer_email and customer_phone):
            flash("Please fill in all required customer details.", "danger")
            return redirect(url_for('book_services', place_id=place.id))
        
        if not (hotel_id or transport_id):
            flash("Please select at least one service (hotel or transport).", "danger")
            return redirect(url_for('book_services', place_id=place.id))
        
        # Date validation
        try:
            check_in_date = datetime.strptime(check_in_str, '%Y-%m-%d').date() if check_in_str else None
            check_out_date = datetime.strptime(check_out_str, '%Y-%m-%d').date() if check_out_str else None
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for('book_services', place_id=place.id))
        
        if check_in_date and check_out_date:
            if check_in_date >= check_out_date:
                flash("Check-out date must be after check-in date.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
            
            if check_in_date < datetime.now().date():
                flash("Check-in date cannot be in the past.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
            
            num_days = (check_out_date - check_in_date).days
            if num_days <= 0:
                flash("Minimum stay must be at least 1 day.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
        else:
            num_days = 1
        
        # Numeric field validation
        try:
            num_people = int(num_people)
            num_rooms = int(num_rooms)
            if num_people <= 0 or num_rooms <= 0:
                raise ValueError
        except ValueError:
            flash("Number of people and rooms must be positive numbers.", "danger")
            return redirect(url_for('book_services', place_id=place.id))
        
        # Calculate pricing
        hotel_total = 0.0
        transport_total = 0.0
        hotel = None
        transport = None
        
        if hotel_id:
            hotel = Hotel.query.get(hotel_id)
            if not hotel:
                flash("Selected hotel not found.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
            hotel_total = hotel.price_per_night * num_days * num_rooms
        
        if transport_id:
            transport = Transport.query.get(transport_id)
            if not transport:
                flash("Selected transport service not found.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
            transport_total = transport.price * num_people
        
        total_amount = hotel_total + transport_total
        
        # Check for existing hotel bookings (date conflict)
        if hotel_id and check_in_date and check_out_date:
            existing_hotel_booking = ServiceBooking.query.filter(
                ServiceBooking.hotel_id == hotel_id,
                ServiceBooking.check_in_date <= check_out_date,
                ServiceBooking.check_out_date >= check_in_date,
                ServiceBooking.status.in_(['Pending', 'Confirmed'])
            ).first()
            
            if existing_hotel_booking:
                flash("Sorry, the selected hotel is not available for the chosen dates. Please select different dates or another hotel.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
        
        # Check for duplicate service bookings (same user, same service, same date)
        if hotel_id and check_in_date:
            # Check if user already has a booking for the same hotel on the same dates
            duplicate_hotel_booking = ServiceBooking.query.filter(
                ServiceBooking.customer_email == customer_email,
                ServiceBooking.hotel_id == hotel_id,
                ServiceBooking.check_in_date == check_in_date,
                ServiceBooking.status.in_(['Pending', 'Confirmed'])
            ).first()
            
            if duplicate_hotel_booking:
                flash(f"You already have a booking for this hotel on {check_in_str}. Please choose a different date or contact us to modify your existing booking.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
        
        if transport_id:
            # For transport, check if user already has a booking for the same transport service
            # Since transport doesn't have dates in the same way, we'll check for same day bookings
            duplicate_transport_booking = ServiceBooking.query.filter(
                ServiceBooking.customer_email == customer_email,
                ServiceBooking.transport_id == transport_id,
                ServiceBooking.created_at >= datetime.now().date(),
                ServiceBooking.status.in_(['Pending', 'Confirmed'])
            ).first()
            
            if duplicate_transport_booking:
                flash("You already have a booking for this transport service today. Please contact us for multiple bookings.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
        
        # Check if user has any service booking for the same place on the same dates
        if check_in_date:
            existing_place_service_booking = ServiceBooking.query.filter(
                ServiceBooking.customer_email == customer_email,
                ServiceBooking.place_id == place_id,
                ServiceBooking.check_in_date == check_in_date,
                ServiceBooking.status.in_(['Pending', 'Confirmed'])
            ).first()
            
            if existing_place_service_booking:
                flash(f"You already have a service booking for {place.name} on {check_in_str}. Please choose a different date or contact us to modify your existing booking.", "danger")
                return redirect(url_for('book_services', place_id=place.id))
        
        # Create service booking
        service_booking = ServiceBooking(
            place_id=place.id,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            hotel_id=hotel.id if hotel else None,
            transport_id=transport.id if transport else None,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            num_people=num_people,
            num_rooms=num_rooms,
            num_days=num_days,
            special_requests=special_requests,
            hotel_total=hotel_total,
            transport_total=transport_total,
            total_amount=total_amount
        )
        
        db.session.add(service_booking)
        db.session.commit()
        
        flash("Your service booking has been submitted successfully! We will contact you shortly to confirm.", "success")
        return redirect(url_for('service_booking_success', booking_id=service_booking.id))
    
    # GET request - show available services
    hotels = Hotel.query.filter_by(place_id=place_id).all()
    transports = Transport.query.filter_by(place_id=place_id).all()
    
    # Calculate dates for form min values
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    return render_template('book_services.html', 
                         place=place, 
                         hotels=hotels, 
                         transports=transports,
                         today=today.isoformat(),
                         tomorrow=tomorrow.isoformat())

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin_bookings.html', bookings=bookings)


@app.route('/admin/bookings/<int:booking_id>/status', methods=['POST'])
@login_required
def admin_update_booking_status(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Confirmed', 'Rejected']:
        booking.status = new_status
        db.session.commit()
        flash("Booking status updated.", "success")
    else:
        flash("Invalid status.", "danger")
    return redirect(url_for('admin_bookings'))
@app.route('/service-booking-success/<int:booking_id>')
def service_booking_success(booking_id):
    booking = ServiceBooking.query.get_or_404(booking_id)
    return render_template('service_booking_success.html', booking=booking)

# Add admin route to manage service bookings
@app.route('/admin/service-bookings')
@login_required
def admin_service_bookings():
    service_bookings = ServiceBooking.query.order_by(ServiceBooking.created_at.desc()).all()
    return render_template('admin_service_bookings.html', service_bookings=service_bookings)

@app.route('/admin/service-bookings/<int:booking_id>/status', methods=['POST'])
@login_required
def admin_update_service_booking_status(booking_id):
    booking = ServiceBooking.query.get_or_404(booking_id)
    new_status = request.form.get('status')
    if new_status in ['Pending', 'Confirmed', 'Cancelled']:
        booking.status = new_status
        db.session.commit()
        flash("Service booking status updated.", "success")
    else:
        flash("Invalid status.", "danger")
    return redirect(url_for('admin_service_bookings'))


# ------------ INIT ------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
