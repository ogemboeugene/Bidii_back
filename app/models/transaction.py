import uuid
from enum import Enum as PyEnum
from app.extensions import db

class DescriptionType(PyEnum):
    ADVANCE_PAYMENT = "advance payment"
    LOAN_PAYMENT = "loan payment"
    AMOUNT_CONTRIBUTED = "amount contributed"
    ADVANCE_GIVEN_OUT = "advance given out"

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Enum(DescriptionType), nullable=False)  # Use Enum for description
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

    # Relationship with MonthlyPerformance
    group_id = db.Column(db.Integer, db.ForeignKey('monthly_performance.id'), nullable=False)
    group = db.relationship('MonthlyPerformance', backref=db.backref('transactions', lazy=True))

    # Relationship with GroupMonthlyPerformance
    group_monthly_performance_id = db.Column(db.Integer, db.ForeignKey('group_monthly_performance.id',  ondelete='SET NULL'), nullable=True)
    group_monthly_performance = db.relationship('GroupMonthlyPerformance', back_populates='transactions')

    # Relationship with Advance
    advance_id = db.Column(db.Integer, db.ForeignKey('advance.id'), nullable=True)
    advance = db.relationship('Advance', backref=db.backref('transactions', lazy=True))

    is_flagged = db.Column(db.Boolean, default=False)
    transaction_ref = db.Column(db.String(20), unique=True, nullable=False, default='')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction_ref = self.generate_transaction_ref()

    def generate_transaction_ref(self):
        # Generate a unique transaction reference (e.g., 'TX1234ABCD')
        return f"TX{uuid.uuid4().hex[:8].upper()}"

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'description': self.description.value,  # Return the string value of the Enum
            'timestamp': self.timestamp.isoformat(),
            'user_id': self.user_id,
            'group_id': self.group_id,  # Include group_id in the dictionary representation
            'group_monthly_performance_id': self.group_monthly_performance_id,
            'advance_id': self.advance_id,
            'is_flagged': self.is_flagged,
            'transaction_ref': self.transaction_ref
        }
