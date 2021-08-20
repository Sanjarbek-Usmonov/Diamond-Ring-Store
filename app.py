from flask import Flask, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, HiddenField, SelectField
from flask_wtf.file import FileField, FileAllowed
import random
# from flask_ngrok import run_with_ngrok

app = Flask(__name__)

# run_with_ngrok(app)

photos = UploadSet('photos', IMAGES)

app.config['UPLOADED_PHOTOS_DEST'] = 'images'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trendy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'mysecret'

configure_uploads(app, photos)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    price = db.Column(db.Integer) # in cents
    stock = db.Column(db.Integer)
    description = db.Column(db.String(500))
    image = db.Column(db.String(100))

    orders = db.relationship('Order_Item', backref='product', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(5))
    first_name = db.Column(db.String(20))
    last_name = db.Column(db.String(20))
    phone_number = db.Column(db.Integer)
    email = db.Column(db.String(50))
    address = db.Column(db.String(100))
    city = db.Column(db.String(100))
    region = db.Column(db.String(50))
    country = db.Column(db.String(40))
    status = db.Column(db.String(15))
    payment_type = db.Column(db.String(20))
    items = db.relationship('Order_Item', backref='order', lazy=True)

    def order_total(self):
        return db.session.query(
            db.func.sum(Order_Item.quantity * Product.price)
        ).join(Product).filter(Order_Item.order_id == self.id).scalar() + 1000

    def quantity_total(self):
        return db.session.query(db.func.sum(Order_Item.quantity)).filter(Order_Item.order_id == self.id).scalar()

class Order_Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)

class AddProduct(FlaskForm):
    name = StringField('Name')
    price = IntegerField('Price')
    stock = IntegerField('Stock')
    description = TextAreaField('Description')
    image = FileField('Image', validators=[FileAllowed(IMAGES, 'Only images are accepted.')])

class AddToCart(FlaskForm):
    quantity = IntegerField('Quantity')
    id = HiddenField('ID')

class Checkout(FlaskForm):
    first_name = StringField('First Name')
    last_name = StringField('Last Name')
    phone_number = StringField('Phone Number')
    email = StringField('Email')
    address = StringField('Address')
    city = StringField('City')
    region = SelectField('Region', choices=[('Toshkent', 'Toshkent'), ('Andijon', 'Andijon'), ('Namangan', 'Namangen'), ('Farg\'ona', 'Farg\'ona'),
                                            ('Sirdaryo', 'Sirdaryo'), ('Jizzax', 'Jizzax'), ('Samarqand', 'Samarqand'), ('Qashqadaryo', 'Qashqadaryo'),
                                            ('Surxondaryo', 'Surxondaryo'), ('Buxoro', 'Buxoro'), ('Navoiy', 'Navoiy'), ('Xorazm', 'Xorazm'),
                                            ('Qoraqalpog\'iston', 'Qoraqalpog\'iston')])
    country = SelectField('Country', choices=[('UZ', 'O\'zbekiston')])
    payment_type = SelectField('Payment Type', choices=[('PayByCheck', 'Pay By Check'), ('WireTransfer', 'Pay By Bank Wire Transfer')])

def handle_cart():
    products = []
    grand_total = 0
    index = 0
    quantity_total = 0

    for item in session['savat']:
        product = Product.query.filter_by(id=item['id']).first()
        quantity = int(item['quantity'])
        total = quantity * product.price
        quantity_total += quantity
        grand_total += total
        products.append({'id': product.id,
                         'name': product.name,
                         'price': product.price,
                         'image': product.image,
                         'quantity': quantity,
                         'total': total,
                         'index': index}
                        )
        index += 1

    grand_total_plus_shipping = grand_total + 1000
    return products, grand_total, grand_total_plus_shipping, quantity_total


@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)


@app.route('/product/<id>')
def product(id):
    product = Product.query.filter_by(id=id).first()
    form = AddToCart()
    return render_template('view-product.html', product=product, form=form)


@app.route('/cart')
def cart():
    products, grand_total, grand_total_plus_shipping, quantity_total = handle_cart()
    return render_template('cart.html', products=products,
                           grand_total=grand_total, grand_total_plus_shipping=grand_total_plus_shipping,
                           quantity_total=quantity_total
                           )


@app.route('/remove-from-cart/<index>')
def remove_from_cart(index):
    del session['savat'][int(index)]
    session.modified = True
    return redirect(url_for('cart'))


@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'savat' not in session:
        session['savat'] = []

    form = AddToCart()

    if form.validate_on_submit():
        session['savat'].append({'id': form.id.data, 'quantity': form.quantity.data})
        session.modified = True

    return redirect(url_for('index'))


@app.route('/quick-add/<id>')
def quick_add(id):
    if 'savat' not in session:
        session['savat'] = []

    session['savat'].append({'id': id, 'quantity': 1})
    session.modified = True

    return redirect(url_for('index'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    latters = 'QWERTYUIOPASDFGHJKLZXCVBNM'
    form = Checkout()
    products, grand_total, grand_total_plus_shipping, quantity_total = handle_cart()
    if form.validate_on_submit():
        order = Order()
        form.populate_obj(order)
        order.reference = ''.join([random.choice(latters) for _ in range(5)])
        order.status = 'KUTILMOQDA'
        for product in products:
            order_item = Order_Item(quantity=product['quantity'], product_id=product['id'])
            order.items.append(order_item)
            product = Product.query.filter_by(id=product['id']).update({'stock': Product.stock - product['quantity']})
        db.session.add(order)
        db.session.commit()
        session['savat'] = []
        session.modified = True
        return redirect(url_for('index'))
    return render_template('checkout.html', form=form, products=products, grand_total=grand_total,
                           grand_total_plus_shipping=grand_total_plus_shipping, quantity_total=quantity_total)


@app.route('/admin')
def admin():
    products = Product.query.all()
    products_in_stock = Product.query.filter(Product.stock > 0).count()
    orders = Order.query.all()

    return render_template('admin/index.html', admin=True, products=products,
                           products_in_stock=products_in_stock, orders=orders
                           )


@app.route('/admin/add', methods=['GET', 'POST'])
def add():
    form = AddProduct()

    if form.validate_on_submit():
        #print(form.name.data)
        #print(form.price.data)
        #print(form.stock.data)
        #print(form.description.data)
        #print(form.image.data)

        image_url = photos.url(photos.save(form.image.data))

        new_product = Product(name=form.name.data,
                              price=form.price.data,
                              stock=form.stock.data,
                              description=form.description.data,
                              image=image_url
                              )

        db.session.add(new_product)
        db.session.commit()

        return redirect(url_for('admin'))

    return render_template('admin/add-product.html', admin=True, form=form)


@app.route('/admin/order/<order_id>')
def order(order_id):
    order = Order.query.filter_by(id=int(order_id)).first()
    return render_template('admin/view-order.html', order=order, admin=True)

if __name__ == '__main__':
    manager.run()