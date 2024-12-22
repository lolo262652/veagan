from flask import Flask, render_template, request, redirect, url_for, flash, send_file, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from sqlalchemy import func, extract, text
from sqlalchemy import inspect
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from datetime import datetime
import pdfkit
import tempfile
from jinja2 import Environment
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DateField, FloatField
from wtforms.validators import DataRequired, Email, EqualTo
from sqlalchemy.exc import IntegrityError
from translations import translations

load_dotenv()

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DATABASE')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BABEL_DEFAULT_LOCALE'] = 'fr'
app.config['CURRENCY_SYMBOL'] = '€'

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128))

    def set_password(self, password):
        self.password = password

    def check_password(self, password):
        return self.password == password

class TaskCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tasks = db.relationship('Task', backref='task_category', lazy=True)

class ProductCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='product_category', lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='todo')  # todo, in_progress, done
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    category_id = db.Column(db.Integer, db.ForeignKey('task_category.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    estimated_hours = db.Column(db.Float)
    actual_hours = db.Column(db.Float)
    completion_date = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    user = db.relationship('User', foreign_keys=[user_id], backref='created_tasks')
    assignee = db.relationship('User', foreign_keys=[assigned_to], backref='assigned_tasks')
    creator = db.relationship('User', foreign_keys=[created_by], backref='tasks_created')

    @property
    def status_label(self):
        labels = {
            'todo': 'À faire',
            'in_progress': 'En cours',
            'done': 'Terminée'
        }
        return labels.get(self.status, self.status)

    @property
    def status_color(self):
        colors = {
            'todo': 'warning',
            'in_progress': 'info',
            'done': 'success'
        }
        return colors.get(self.status, 'secondary')

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    company_name = db.Column(db.String(100))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    tax_id = db.Column(db.String(50))
    payment_terms = db.Column(db.String(200))
    website = db.Column(db.String(200))
    product_categories = db.Column(db.String(500))
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='primary')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    stock = db.Column(db.Integer)
    category_id = db.Column(db.Integer, db.ForeignKey('product_category.id'))
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    supplier = db.relationship('Supplier', backref='products')

class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(120))
    tax_id = db.Column(db.String(50))
    logo_path = db.Column(db.String(200))
    currency = db.Column(db.String(3), default='USD')
    default_tax_rate = db.Column(db.Float, default=0.0)

    @staticmethod
    def get_settings():
        company = Company.query.first()
        if not company:
            company = Company(
                name='Your Company Name',
                email='your.email@example.com',
                currency='USD',
                default_tax_rate=0.0
            )
            db.session.add(company)
            db.session.commit()
        return company

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=False)
    tax_rate = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='draft')
    notes = db.Column(db.Text)

    # Relations
    client = db.relationship('Client', backref=db.backref('invoices', lazy=True))
    items = db.relationship('InvoiceItem', backref='invoice', lazy=True, cascade='all, delete-orphan')

    @property
    def total_amount(self):
        """Calcule le montant total de la facture, TVA incluse"""
        subtotal = sum(item.quantity * item.unit_price for item in self.items)
        tax = subtotal * (self.tax_rate / 100)
        return subtotal + tax

    @property
    def subtotal(self):
        """Calcule le sous-total hors TVA"""
        return sum(item.quantity * item.unit_price for item in self.items)

    @property
    def tax_amount(self):
        """Calcule le montant de la TVA"""
        return self.subtotal * (self.tax_rate / 100)

    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    description = db.Column(db.String(200))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)

    # Relationship
    product = db.relationship('Product', backref=db.backref('invoice_items', lazy=True))

    def calculate_total(self):
        self.total = self.quantity * self.unit_price

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class TaskForm(FlaskForm):
    title = StringField('Titre', validators=[DataRequired()])
    description = TextAreaField('Description')
    category_id = SelectField('Catégorie', coerce=int)
    priority = SelectField('Priorité', choices=[('low', 'Basse'), ('medium', 'Moyenne'), ('high', 'Haute')])
    assigned_to = SelectField('Assigné à', coerce=int)
    due_date = DateField('Date d\'échéance')
    estimated_hours = FloatField('Temps estimé (heures)')
    submit = SubmitField('Enregistrer')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def nl2br(value):
    return value.replace('\n', '<br>')

def _(text):
    return translations.get(text, text)

def format_currency(amount):
    return f"{amount:.2f} €"

app.jinja_env.filters['nl2br'] = nl2br
app.jinja_env.globals.update(_=_, format_currency=format_currency)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('tasks'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('tasks'))
        flash('Nom d\'utilisateur ou mot de passe incorrect', 'danger')
    return render_template('login.html', form=form, title='Connexion')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('tasks'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
            flash('Inscription réussie ! Vous pouvez maintenant vous connecter.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            db.session.rollback()
            flash('Ce nom d\'utilisateur ou email est déjà utilisé.', 'danger')
    
    return render_template('register.html', form=form, title='Inscription')

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('tasks'))
    
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Ici vous pouvez ajouter la logique d'envoi d'email
            flash('Vérifiez vos emails pour les instructions de réinitialisation', 'info')
            return redirect(url_for('login'))
        flash('Adresse email non trouvée', 'danger')
    return render_template('reset_password_request.html', form=form, title='Réinitialisation du mot de passe')

@app.route('/dashboard')
@login_required
def dashboard():
    # Statistiques clients
    total_clients = Client.query.filter_by(active=True).count()
    new_clients_this_month = Client.query.filter(
        Client.created_at >= datetime.utcnow().replace(day=1, hour=0, minute=0, second=0),
        Client.active == True
    ).count()

    # Statistiques fournisseurs
    total_suppliers = Supplier.query.filter_by(active=True).count()
    active_suppliers = Supplier.query.filter_by(active=True).count()

    # Statistiques factures
    total_invoices = Invoice.query.count()
    total_amount = db.session.query(func.sum(Invoice.total_amount)).scalar() or 0
    
    # Factures du mois en cours
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year
    invoices_this_month = Invoice.query.filter(
        extract('month', Invoice.date_created) == current_month,
        extract('year', Invoice.date_created) == current_year
    ).all()
    amount_this_month = sum(invoice.total_amount for invoice in invoices_this_month)

    # Factures impayées
    unpaid_invoices = Invoice.query.filter_by(status='pending').count()
    unpaid_amount = db.session.query(func.sum(Invoice.total_amount))\
        .filter(Invoice.status == 'pending').scalar() or 0

    # Top 5 clients par montant facturé
    top_clients = db.session.query(
        Client,
        func.sum(Invoice.total_amount).label('total_amount'),
        func.count(Invoice.id).label('invoice_count')
    ).join(Invoice)\
     .group_by(Client)\
     .order_by(text('total_amount DESC'))\
     .limit(5)\
     .all()

    return render_template('dashboard.html',
                         total_clients=total_clients,
                         new_clients_this_month=new_clients_this_month,
                         total_suppliers=total_suppliers,
                         active_suppliers=active_suppliers,
                         total_invoices=total_invoices,
                         total_amount=total_amount,
                         amount_this_month=amount_this_month,
                         unpaid_invoices=unpaid_invoices,
                         unpaid_amount=unpaid_amount,
                         top_clients=top_clients)

@app.route('/tasks')
@login_required
def tasks():
    tasks = Task.query.filter(
        db.or_(
            Task.user_id == current_user.id,
            Task.assigned_to == current_user.id
        )
    ).order_by(
        db.case(
            (Task.priority == 'high', 1),
            (Task.priority == 'medium', 2),
            else_=3
        ),
        Task.due_date.asc()
    ).all()
    
    categories = TaskCategory.query.all()
    users = User.query.all()
    return render_template('tasks.html', tasks=tasks, categories=categories, users=users)

@app.route('/tasks/<int:task_id>')
@login_required
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify({
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
        'category_id': task.category_id,
        'assigned_to': task.assigned_to,
        'estimated_hours': task.estimated_hours
    })

@app.route('/tasks/add', methods=['POST'])
@login_required
def add_task():
    try:
        data = request.get_json()
        
        # Validation des données
        if not data.get('title'):
            return jsonify({'status': 'error', 'message': 'Le titre est requis'}), 400
            
        # Création de la tâche
        task = Task(
            title=data['title'],
            description=data.get('description', ''),
            category_id=data.get('category_id'),
            priority=data.get('priority', 'medium'),
            assigned_to=data.get('assigned_to'),
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date() if data.get('due_date') else None,
            estimated_hours=float(data['estimated_hours']) if data.get('estimated_hours') else None,
            status='todo',
            created_by=current_user.id
        )
        
        db.session.add(task)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Tâche ajoutée avec succès'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    try:
        data = request.get_json()
        task = Task.query.get_or_404(task_id)
        
        if data.get('status') not in ['todo', 'in_progress', 'done']:
            return jsonify({'status': 'error', 'message': 'Statut invalide'}), 400
            
        task.status = data['status']
        db.session.commit()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    try:
        task = Task.query.get_or_404(task_id)
        db.session.delete(task)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/tasks/<int:task_id>/edit', methods=['PUT'])
@login_required
def edit_task(task_id):
    try:
        task = Task.query.get_or_404(task_id)
        data = request.get_json()
        
        if not data.get('title'):
            return jsonify({'status': 'error', 'message': 'Le titre est requis'}), 400
            
        task.title = data['title']
        task.description = data.get('description', '')
        task.category_id = data.get('category_id')
        task.priority = data.get('priority', 'medium')
        task.assigned_to = data.get('assigned_to')
        
        if data.get('due_date'):
            task.due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        else:
            task.due_date = None
            
        task.estimated_hours = data.get('estimated_hours')
        task.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Tâche mise à jour avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/clients')
@login_required
def clients():
    clients = Client.query.order_by(Client.created_at.desc()).all()
    return render_template('clients.html', clients=clients)

@app.route('/client/add', methods=['GET', 'POST'])
@login_required
def add_client():
    if request.method == 'POST':
        client = Client(
            name=request.form.get('name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            company_name=request.form.get('company_name'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            postal_code=request.form.get('postal_code'),
            country=request.form.get('country'),
            notes=request.form.get('notes'),
            active=True
        )
        db.session.add(client)
        db.session.commit()
        flash('Client added successfully')
        return redirect(url_for('clients'))
    return render_template('client_form.html')

@app.route('/client/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.name = request.form.get('name')
        client.email = request.form.get('email')
        client.phone = request.form.get('phone')
        client.company_name = request.form.get('company_name')
        client.address = request.form.get('address')
        client.city = request.form.get('city')
        client.postal_code = request.form.get('postal_code')
        client.country = request.form.get('country')
        client.notes = request.form.get('notes')
        client.active = True if request.form.get('active') else False
        db.session.commit()
        flash('Client updated successfully')
        return redirect(url_for('clients'))
    return render_template('client_form.html', client=client)

@app.route('/client/delete/<int:client_id>', methods=['POST'])
@login_required
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash('Client deleted successfully')
    return redirect(url_for('clients'))

@app.route('/suppliers')
@login_required
def suppliers():
    suppliers = Supplier.query.order_by(Supplier.created_at.desc()).all()
    return render_template('suppliers.html', suppliers=suppliers)

@app.route('/supplier/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    if request.method == 'POST':
        supplier = Supplier(
            company_name=request.form.get('company_name'),
            contact_name=request.form.get('contact_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            city=request.form.get('city'),
            postal_code=request.form.get('postal_code'),
            country=request.form.get('country'),
            tax_id=request.form.get('tax_id'),
            payment_terms=request.form.get('payment_terms'),
            website=request.form.get('website'),
            product_categories=request.form.get('product_categories'),
            notes=request.form.get('notes'),
            active=True if request.form.get('active') else False
        )
        db.session.add(supplier)
        db.session.commit()
        flash('Supplier added successfully')
        return redirect(url_for('suppliers'))
    return render_template('supplier_form.html')

@app.route('/supplier/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'POST':
        supplier.company_name = request.form.get('company_name')
        supplier.contact_name = request.form.get('contact_name')
        supplier.email = request.form.get('email')
        supplier.phone = request.form.get('phone')
        supplier.address = request.form.get('address')
        supplier.city = request.form.get('city')
        supplier.postal_code = request.form.get('postal_code')
        supplier.country = request.form.get('country')
        supplier.tax_id = request.form.get('tax_id')
        supplier.payment_terms = request.form.get('payment_terms')
        supplier.website = request.form.get('website')
        supplier.product_categories = request.form.get('product_categories')
        supplier.notes = request.form.get('notes')
        supplier.active = True if request.form.get('active') else False
        db.session.commit()
        flash('Supplier updated successfully')
        return redirect(url_for('suppliers'))
    return render_template('supplier_form.html', supplier=supplier)

@app.route('/supplier/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    db.session.delete(supplier)
    db.session.commit()
    flash('Supplier deleted successfully')
    return redirect(url_for('suppliers'))

@app.route('/categories')
@login_required
def categories():
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@app.route('/category/add', methods=['POST'])
@login_required
def add_category():
    try:
        name = request.form.get('name')
        description = request.form.get('description')
        
        category = Category(
            name=name,
            description=description
        )
        db.session.add(category)
        db.session.commit()
        flash('Catégorie ajoutée avec succès', 'success')
    except Exception as e:
        flash(f'Erreur lors de l\'ajout de la catégorie: {str(e)}', 'error')
    return redirect(url_for('categories'))

@app.route('/category/edit/<int:category_id>', methods=['GET', 'POST'])
@login_required
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == 'POST':
        category.name = request.form.get('name')
        category.description = request.form.get('description')
        db.session.commit()
        flash('Category updated successfully')
        return redirect(url_for('categories'))
    return render_template('category_form.html', category=category)

@app.route('/category/delete/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    if category.tasks:
        flash('Cannot delete category with tasks')
        return redirect(url_for('categories'))
    
    db.session.delete(category)
    db.session.commit()
    flash('Category deleted successfully')
    return redirect(url_for('categories'))

@app.route('/products')
@login_required
def products():
    products = Product.query.order_by(Product.name).all()
    return render_template('products.html', products=products)

@app.route('/product/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        try:
            # Handle image upload
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image_path = f'uploads/{filename}'  # Store relative path

            # Get form data with default values for numeric fields
            price = request.form.get('price', '0')
            stock = request.form.get('stock', '0')
            weight = request.form.get('weight', '0')
            
            # Convert to float/int, using 0 as default for empty strings
            price = float(price) if price.strip() else 0
            stock = int(stock) if stock.strip() else 0
            weight = float(weight) if weight.strip() else 0

            product = Product(
                name=request.form.get('name'),
                description=request.form.get('description'),
                price=price,
                stock=stock,
                sku=request.form.get('sku'),
                barcode=request.form.get('barcode'),
                weight=weight,
                unit=request.form.get('unit'),
                image_path=image_path,
                category_id=request.form.get('category_id'),
                supplier_id=request.form.get('supplier_id') or None,
                active=True if request.form.get('active') else False
            )
            db.session.add(product)
            db.session.commit()
            flash('Product added successfully')
            return redirect(url_for('products'))
        except ValueError as e:
            flash('Invalid numeric value provided. Please check your input.', 'error')
            categories = ProductCategory.query.all()
            suppliers = Supplier.query.filter_by(active=True).all()
            return render_template('product_form.html', categories=categories, suppliers=suppliers)

    categories = ProductCategory.query.all()
    suppliers = Supplier.query.filter_by(active=True).all()
    return render_template('product_form.html', categories=categories, suppliers=suppliers)

@app.route('/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        try:
            # Handle image upload
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    # Delete old image if it exists
                    if product.image_path:
                        old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(product.image_path))
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                    
                    # Save new image
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    product.image_path = f'uploads/{filename}'  # Store relative path

            # Get form data with default values for numeric fields
            price = request.form.get('price', '0')
            stock = request.form.get('stock', '0')
            weight = request.form.get('weight', '0')
            
            # Convert to float/int, using current values as defaults for empty strings
            product.price = float(price) if price.strip() else product.price
            product.stock = int(stock) if stock.strip() else product.stock
            product.weight = float(weight) if weight.strip() else product.weight

            product.name = request.form.get('name')
            product.description = request.form.get('description')
            product.sku = request.form.get('sku')
            product.barcode = request.form.get('barcode')
            product.unit = request.form.get('unit')
            product.category_id = request.form.get('category_id')
            product.supplier_id = request.form.get('supplier_id') or None
            product.active = True if request.form.get('active') else False
            
            db.session.commit()
            flash('Product updated successfully')
            return redirect(url_for('products'))
        except ValueError as e:
            flash('Invalid numeric value provided. Please check your input.', 'error')
            categories = ProductCategory.query.all()
            suppliers = Supplier.query.filter_by(active=True).all()
            return render_template('product_form.html', product=product, categories=categories, suppliers=suppliers)

    categories = ProductCategory.query.all()
    suppliers = Supplier.query.filter_by(active=True).all()
    return render_template('product_form.html', product=product, categories=categories, suppliers=suppliers)

@app.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    # Delete product image if it exists
    if product.image_path:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], os.path.basename(product.image_path))
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted successfully')
    return redirect(url_for('products'))

@app.route('/invoices')
@login_required
def invoices():
    invoices = Invoice.query.order_by(Invoice.date_created.desc()).all()
    return render_template('invoices.html', invoices=invoices)

@app.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            client_id = request.form.get('client_id')
            date_created = datetime.strptime(request.form.get('date_created'), '%Y-%m-%d')
            due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d')
            tax_rate = float(request.form.get('tax_rate', 0))
            notes = request.form.get('notes', '')

            if not client_id:
                raise ValueError("Le client est requis")

            # Créer la facture
            invoice = Invoice(
                invoice_number=generate_invoice_number(),
                client_id=client_id,
                date_created=date_created,
                due_date=due_date,
                tax_rate=tax_rate,
                notes=notes,
                status='draft'
            )
            db.session.add(invoice)
            db.session.flush()  # Pour obtenir l'ID de la facture

            # Traiter les articles
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            prices = request.form.getlist('price[]')
            descriptions = request.form.getlist('description[]')

            if not product_ids:
                raise ValueError("Au moins un article est requis")

            for i in range(len(product_ids)):
                if product_ids[i]:  # Ignorer les lignes vides
                    item = InvoiceItem(
                        invoice_id=invoice.id,
                        product_id=int(product_ids[i]),
                        quantity=int(quantities[i]),
                        unit_price=float(prices[i]),
                        description=descriptions[i]
                    )
                    item.total = item.quantity * item.unit_price
                    db.session.add(item)

            db.session.commit()
            flash('Facture créée avec succès', 'success')
            return redirect(url_for('invoices'))

        except ValueError as e:
            db.session.rollback()
            flash(f'Erreur de validation : {str(e)}', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la création de la facture : {str(e)}', 'error')
        return redirect(url_for('create_invoice'))

    # GET request
    clients = Client.query.filter_by(active=True).all()
    products = Product.query.filter_by(active=True).all()
    company = Company.query.first()
    return render_template('invoice_form.html', 
                         invoice=None, 
                         clients=clients, 
                         products=products,
                         company=company)

@app.route('/invoices/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('invoice_view.html', invoice=invoice)

@app.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    
    if request.method == 'POST':
        try:
            # Mettre à jour les informations de base
            invoice.client_id = request.form['client_id']
            invoice.date_created = datetime.strptime(request.form['date_created'], '%Y-%m-%d')
            invoice.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d')
            invoice.tax_rate = float(request.form['tax_rate'])
            invoice.notes = request.form.get('notes', '')
            if 'status' in request.form:
                invoice.status = request.form['status']

            # Supprimer les anciens articles
            InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()

            # Ajouter les nouveaux articles
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            prices = request.form.getlist('price[]')
            descriptions = request.form.getlist('description[]')

            for i in range(len(product_ids)):
                if product_ids[i]:  # Ignorer les lignes vides
                    item = InvoiceItem(
                        invoice_id=invoice.id,
                        product_id=product_ids[i],
                        quantity=int(quantities[i]),
                        unit_price=float(prices[i]),
                        description=descriptions[i]
                    )
                    db.session.add(item)

            db.session.commit()
            flash('Facture mise à jour avec succès', 'success')
            return redirect(url_for('invoices'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erreur lors de la mise à jour de la facture : {str(e)}', 'error')
            return redirect(url_for('edit_invoice', invoice_id=invoice_id))

    # GET request
    clients = Client.query.filter_by(active=True).all()
    products = Product.query.filter_by(active=True).all()
    company = Company.query.first()
    return render_template('invoice_form.html', 
                         invoice=invoice, 
                         clients=clients, 
                         products=products,
                         company=company)

@app.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    try:
        db.session.delete(invoice)
        db.session.commit()
        flash('Facture supprimée avec succès', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression de la facture : {str(e)}', 'error')
    return redirect(url_for('invoices'))

@app.route('/invoices/<int:invoice_id>/preview')
@login_required
def preview_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    company = Company.query.first()
    
    # Calculer les totaux
    total_ht = sum(item.quantity * item.unit_price for item in invoice.items)
    total_tax = total_ht * (invoice.tax_rate / 100)
    total_ttc = total_ht + total_tax
    
    invoice.total_ht = total_ht
    invoice.total_tax = total_tax
    invoice.total_ttc = total_ttc
    
    return render_template('invoice_pdf.html', 
                         invoice=invoice, 
                         company=company)

@app.route('/invoices/<int:invoice_id>/pdf')
@login_required
def download_invoice_pdf(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    company = Company.query.first()
    
    # Calculer les totaux
    total_ht = sum(item.quantity * item.unit_price for item in invoice.items)
    total_tax = total_ht * (invoice.tax_rate / 100)
    total_ttc = total_ht + total_tax
    
    invoice.total_ht = total_ht
    invoice.total_tax = total_tax
    invoice.total_ttc = total_ttc
    
    # Générer le HTML
    html_content = render_template('invoice_pdf.html',
                                 invoice=invoice,
                                 company=company)
    
    # Configuration de pdfkit
    config = pdfkit.configuration(wkhtmltopdf=r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe')
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'encoding': "UTF-8",
        'no-outline': None
    }
    
    # Créer un fichier temporaire pour le PDF
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
        # Générer le PDF
        pdfkit.from_string(html_content, temp_file.name, options=options, configuration=config)
        
        # Préparer la réponse
        response = make_response(send_file(temp_file.name,
                                         mimetype='application/pdf',
                                         as_attachment=True,
                                         download_name=f'facture_{invoice.invoice_number}.pdf'))
        
        # Nettoyer le fichier temporaire après l'envoi
        @response.call_on_close
        def cleanup():
            os.unlink(temp_file.name)
            
        return response

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    company = Company.query.first()
    if not company:
        company = Company(
            name='Mon Entreprise',
            currency='EUR',
            default_tax_rate=20.0
        )
        db.session.add(company)
        db.session.commit()

    if request.method == 'POST':
        try:
            # Mise à jour des informations de l'entreprise
            company.name = request.form.get('name')
            company.address = request.form.get('address')
            company.phone = request.form.get('phone')
            company.email = request.form.get('email')
            company.website = request.form.get('website')
            company.tax_id = request.form.get('tax_id')
            company.currency = request.form.get('currency')
            company.default_tax_rate = float(request.form.get('default_tax_rate', 0))

            # Gestion du logo
            if 'logo' in request.files:
                logo = request.files['logo']
                if logo and logo.filename != '':
                    # Sécurisation du nom de fichier
                    filename = secure_filename(logo.filename)
                    # Création du chemin pour sauvegarder le logo
                    logo_path = os.path.join('uploads', filename)
                    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    # Sauvegarde du fichier
                    logo.save(full_path)
                    company.logo_path = logo_path

            db.session.commit()
            flash('Paramètres mis à jour avec succès', 'success')
        except Exception as e:
            flash(f'Erreur lors de la mise à jour des paramètres : {str(e)}', 'error')
            db.session.rollback()

    return render_template('settings.html', company=company)

@app.route('/product-categories')
@login_required
def product_categories():
    categories = ProductCategory.query.all()
    return render_template('product_categories.html', categories=categories)

@app.route('/product-categories/add', methods=['POST'])
@login_required
def add_product_category():
    try:
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Le nom est requis'}), 400
            
        category = ProductCategory(
            name=data['name'],
            description=data.get('description', '')
        )
        db.session.add(category)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Catégorie ajoutée avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/product-categories/<int:category_id>')
@login_required
def get_product_category(category_id):
    try:
        category = ProductCategory.query.get_or_404(category_id)
        return jsonify({
            'id': category.id,
            'name': category.name,
            'description': category.description
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/product-categories/<int:category_id>/edit', methods=['PUT'])
@login_required
def edit_product_category(category_id):
    try:
        category = ProductCategory.query.get_or_404(category_id)
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Le nom est requis'}), 400
            
        category.name = data['name']
        category.description = data.get('description', '')
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Catégorie mise à jour avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/product-categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_product_category(category_id):
    try:
        category = ProductCategory.query.get_or_404(category_id)
        if category.products:
            return jsonify({
                'status': 'error', 
                'message': 'Impossible de supprimer une catégorie qui contient des produits'
            }), 400
            
        db.session.delete(category)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Catégorie supprimée avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/task-categories')
@login_required
def task_categories():
    categories = TaskCategory.query.all()
    return render_template('task_categories.html', categories=categories)

@app.route('/task-categories/add', methods=['POST'])
@login_required
def add_task_category():
    try:
        data = request.get_json()
        if not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Le nom est requis'}), 400
            
        category = TaskCategory(
            name=data['name'],
            description=data.get('description', '')
        )
        db.session.add(category)
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Type de tâche ajouté avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/task-categories/<int:category_id>')
@login_required
def get_task_category(category_id):
    try:
        category = TaskCategory.query.get_or_404(category_id)
        return jsonify({
            'id': category.id,
            'name': category.name,
            'description': category.description
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/task-categories/<int:category_id>/edit', methods=['PUT'])
@login_required
def edit_task_category(category_id):
    try:
        category = TaskCategory.query.get_or_404(category_id)
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'status': 'error', 'message': 'Le nom est requis'}), 400
            
        category.name = data['name']
        category.description = data.get('description', '')
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Type de tâche mis à jour avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/task-categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_task_category(category_id):
    try:
        category = TaskCategory.query.get_or_404(category_id)
        if category.tasks:
            return jsonify({
                'status': 'error', 
                'message': 'Impossible de supprimer un type de tâche qui contient des tâches'
            }), 400
            
        db.session.delete(category)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Type de tâche supprimé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

def generate_invoice_number():
    year = datetime.now().year
    # Trouver la dernière facture de l'année
    last_invoice = Invoice.query.filter(
        extract('year', Invoice.date_created) == year
    ).order_by(Invoice.invoice_number.desc()).first()

    if last_invoice:
        # Extraire le numéro de la dernière facture
        last_number = int(last_invoice.invoice_number.split('-')[-1])
        new_number = last_number + 1
    else:
        new_number = 1

    return f'INV-{year}-{new_number:04d}'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

def init_db():
    with app.app_context():
        # Suppression des tables existantes
        db.drop_all()
        
        # Création des tables
        db.create_all()
        
        # Création des catégories par défaut
        default_categories = [
            {'name': 'Urgent', 'color': 'danger'},
            {'name': 'Important', 'color': 'warning'},
            {'name': 'Normal', 'color': 'primary'},
            {'name': 'Faible priorité', 'color': 'info'}
        ]
        
        for cat_data in default_categories:
            category = Category(name=cat_data['name'], color=cat_data['color'])
            db.session.add(category)
        
        try:
            db.session.commit()
            print("Base de données initialisée avec succès!")
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de l'initialisation de la base de données : {str(e)}")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
