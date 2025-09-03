from flask import Flask, render_template, request, make_response
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, DateField, TextAreaField
from wtforms.validators import DataRequired, Optional
from flask_sqlalchemy import SQLAlchemy
from datetime import date
from decimal import Decimal
import pdfkit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invoices.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------- DB Model ----------
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(50), unique=True)
    invoice_date = db.Column(db.Date)
    client_name = db.Column(db.String(255))
    client_address = db.Column(db.Text)
    client_gstin = db.Column(db.String(20))
    subscription_period = db.Column(db.String(50))
    amount = db.Column(db.Numeric(10,2))
    gst_percentage = db.Column(db.Numeric(5,2), default=18)
    razorpay_txn_id = db.Column(db.String(100))

# -------- Form ----------
class InvoiceForm(FlaskForm):
    invoice_no = StringField('Invoice No', validators=[Optional()])
    invoice_date = DateField('Invoice Date', format='%Y-%m-%d', default=date.today, validators=[DataRequired()])
    client_name = StringField('Client Name', validators=[DataRequired()])
    client_address = TextAreaField('Client Address', validators=[DataRequired()])
    client_gstin = StringField('Client GSTIN', validators=[Optional()])
    subscription_period = StringField('Subscription Period', validators=[DataRequired()])
    amount = DecimalField('Amount (INR)', validators=[DataRequired()])
    gst_percentage = DecimalField('GST %', default=18, validators=[DataRequired()])
    razorpay_txn_id = StringField('Razorpay TXN ID', validators=[Optional()])

# -------- wkhtmltopdf configuration ----------
path_wkhtmltopdf = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
pdf_config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

# -------- Routes ----------
@app.route('/', methods=['GET', 'POST'])
def create_invoice():
    form = InvoiceForm()
    if form.validate_on_submit():
        inv_no = form.invoice_no.data.strip() if form.invoice_no.data else f'INV{Invoice.query.count()+1:04d}'

        inv = Invoice(
            invoice_no=inv_no,
            invoice_date=form.invoice_date.data,
            client_name=form.client_name.data,
            client_address=form.client_address.data,
            client_gstin=form.client_gstin.data or 'Unregistered',
            subscription_period=form.subscription_period.data,
            amount=Decimal(str(form.amount.data)),
            gst_percentage=Decimal(str(form.gst_percentage.data)),
            razorpay_txn_id=form.razorpay_txn_id.data or ''
        )
        db.session.add(inv)
        db.session.commit()

        # Calculations
        amount = float(inv.amount)
        gst_amount = amount * float(inv.gst_percentage) / 100
        total_amount = amount + gst_amount
        cgst = sgst = gst_amount / 2

        # Render HTML
        html = render_template(
            'invoice_template.html',
            invoice=inv,
            gst_amount=gst_amount,
            total_amount=total_amount,
            cgst=cgst,
            sgst=sgst
        )

        # Generate PDF
        pdf_bytes = pdfkit.from_string(html, False, configuration=pdf_config)

        # Return PDF response
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=Invoice-{inv.invoice_no}.pdf'
        return response

    return render_template('create_invoice.html', form=form)

@app.route('/invoices')
def list_invoices():
    invoices = Invoice.query.order_by(Invoice.id.desc()).all()
    return render_template('list_invoices.html', invoices=invoices)

@app.route('/invoice/<int:id>')
def show_invoice(id):
    inv = Invoice.query.get_or_404(id)
    amount = float(inv.amount)
    gst_amount = amount * float(inv.gst_percentage) / 100
    total_amount = amount + gst_amount
    cgst = sgst = gst_amount / 2

    html = render_template(
        'invoice_template.html',
        invoice=inv,
        gst_amount=gst_amount,
        total_amount=total_amount,
        cgst=cgst,
        sgst=sgst
    )

    pdf_bytes = pdfkit.from_string(html, False, configuration=pdf_config)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice-{inv.invoice_no}.pdf'
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
