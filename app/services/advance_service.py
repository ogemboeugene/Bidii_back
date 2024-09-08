# app/services/advance_service.py

import logging
import traceback

from flask import current_app
from app.extensions import db
from app.models import Advance, Transaction, GroupMonthlyPerformance, MonthlyPerformance
from app.models.transaction import DescriptionType
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class AdvanceService:

    @staticmethod
    def create_advance(data):
        try:
            # Ensure data is converted correctly
            initial_amount = float(data['initial_amount'])
            interest_rate = 10  # 10% interest rate for new advances
            payment_amount = interest_rate / 100 * initial_amount
            total_amount_due = initial_amount + payment_amount
            is_paid = False  # Advance is not paid at creation
            status = 'pending'  # Status at creation

            # Check if an advance with the same member_name already exists with status 'pending' and is_paid False
            existing_advance = Advance.query.filter_by(
                member_name=data['member_name'],
                status='pending',
                is_paid=False
            ).first()

            if existing_advance:
                raise ValueError(f"An advance for member {data['member_name']} is already pending and not paid.")

            # Validate group_id
            group_id = data.get('group_id')
            group_performance = GroupMonthlyPerformance.query.filter_by(group_id=group_id).first()
            if not group_performance:
                raise ValueError(f"Invalid group ID: {group_id}. Please verify the group and try again.")

            # Check if the member_name exists in the group
            if data['member_name'] not in group_performance.member_details:
                raise ValueError(f"Member {data['member_name']} is not part of this group. Please verify the member details.")

            # Create an Advance instance
            advance = Advance(
                member_name=data['member_name'],
                initial_amount=initial_amount,
                payment_amount=payment_amount,
                is_paid=is_paid,
                user_id=data['user_id'],
                status=status,
                interest_rate=interest_rate,
                paid_amount=0.0,  # No payment made at creation
                total_amount_due=total_amount_due,
                group_id=group_id
            )
            db.session.add(advance)
            db.session.commit()

            # Create a Transaction record for the new advance
            transaction = Transaction(
                amount=initial_amount,
                description=DescriptionType.ADVANCE_GIVEN_OUT,
                user_id=data['user_id'],
                group_id=group_id,  # Link to MonthlyPerformance
                advance_id=advance.id
            )

            db.session.add(transaction)
            db.session.commit()

            return advance

        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception("Database error occurred. Please contact support if the problem persists.")
        except ValueError as e:
            raise ValueError(str(e))
        except Exception as e:
            # Log the exception for debugging purposes
            current_app.logger.error(f"Unexpected error: {str(e)}")
            raise Exception("An unexpected error occurred. Please try again later.")

        
    @staticmethod
    def make_payment(advance_id, payment_amount, user_id):
        try:
            # Retrieve the advance
            advance = Advance.query.get(advance_id)
            if not advance:
                raise ValueError("Advance not found")

            if advance.is_paid:
                raise ValueError("Advance already paid")

            if payment_amount <= 0:
                raise ValueError("Payment amount must be greater than zero")

            # Update the advance details
            advance.paid_amount += payment_amount

            if advance.paid_amount >= advance.amount:
                advance.is_paid = True
                advance.paid_amount = advance.amount
                advance.status = 'paid'

            # Create and add the transaction
            transaction = Transaction(
                amount=payment_amount,
                description=f"Payment of {payment_amount} towards advance {advance_id}",
                user_id=user_id
            )
            db.session.add(transaction)

            # Commit changes to both Advance and Transaction tables
            db.session.commit()
            return advance

        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception(f"Database error occurred: {str(e)}")
        except ValueError as e:
            raise ValueError(str(e))


    @staticmethod
    def get_advance(advance_id):
        try:
            advance = Advance.query.get(advance_id)
            if not advance:
                raise ValueError("Advance not found")
            return advance
        except SQLAlchemyError as e:
            raise Exception(f"Database error occurred: {str(e)}")
        except ValueError as e:
            raise ValueError(str(e))

    @staticmethod
    def update_advance(advance_id, data):
        try:
            # Fetch the advance record
            advance = Advance.query.get(advance_id)
            if not advance:
                raise ValueError("Advance not found")

            # logging.info(f"Advance record before update: {advance.paid_amount}, {advance.updated_at}, {advance.status}, {advance.is_paid}")

            # Check if 'paid_amount' is in the request data
            if 'paid_amount' in data:
                paid_amount = data['paid_amount']
                
                # Ensure paid_amount is converted to float and non-negative
                try:
                    paid_amount = float(paid_amount)
                except ValueError:
                    raise ValueError("Invalid paid_amount value")
                
                if paid_amount < 0:
                    raise ValueError("Paid amount cannot be negative")
                
                # Add paid_amount to the existing paid_amount
                advance.paid_amount += paid_amount
                logging.info(f"Updated paid_amount: {advance.paid_amount}")

                # Update updated_at timestamp
                advance.updated_at = datetime.utcnow()
                logging.info(f"Updated timestamp: {advance.updated_at}")

                # Ensure total_amount_due is a float for comparison
                try:
                    total_amount_due = float(advance.total_amount_due)
                except ValueError:
                    raise ValueError("Invalid total_amount_due value")
                
                # Check if paid_amount equals or exceeds total_amount_due
                if advance.paid_amount >= total_amount_due:
                    advance.status = 'completed'
                    advance.is_paid = True
                    logging.info(f"Advance status updated to completed and is_paid set to True")

                
                # Create a Transaction record for the payment
                transaction = Transaction(
                    amount=paid_amount,
                    description=DescriptionType.ADVANCE_PAYMENT,
                    user_id=data.get('user_id', advance.user_id),  # Use user_id from data or existing advance
                    group_id=advance.group_id,  # Link to MonthlyPerformance
                    advance_id=advance.id
                )

                db.session.add(transaction)

            # Commit the changes
            db.session.commit()
            # logging.info("Database commit successful")
            return advance

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Database error occurred: {str(e)}")
            raise Exception(f"Database error occurred: {str(e)}")
        except ValueError as e:
            logging.error(f"Value Error: {str(e)}")
            raise ValueError(str(e))
    
    @staticmethod
    def calculate_remaining_balance(advance_id):
        try:
            advance = Advance.query.get(advance_id)
            if not advance:
                raise ValueError("Advance not found")

            if advance.is_paid:
                return 0

            remaining_balance = advance.amount - advance.paid_amount
            return remaining_balance
        except SQLAlchemyError as e:
            raise Exception(f"Database error occurred: {str(e)}")
        except ValueError as e:
            raise ValueError(str(e))
        
    @staticmethod
    def list_advances(user_id):
        return Advance.query.filter_by(user_id=user_id).all()
    
    @staticmethod
    def list_advances_by_group_id(group_id):
        # Query to get the group name from the MonthlyPerformance table
        performance_record = MonthlyPerformance.query.filter_by(id=group_id).first()
        if not performance_record:
            # current_app.logger.error(f"Group not found for ID: {group_id}")
            return None  # Handle this as per your logic
        group_name = performance_record.group_name

        # Now, list the advances for the given group_id with status "pending"
        advances = Advance.query.filter_by(group_id=group_id, status="pending").all()
        
        # Optional: You can include the group name in the return if needed
        return {
            'group_name': group_name,
            'advances': advances
        }

    
    @staticmethod
    def delete_advance(advance_id):
        advance = Advance.query.get(advance_id)
        if advance:
            db.session.delete(advance)
            db.session.commit()
            return True
        return False

    @staticmethod
    def search_advances(user_id, query):
        return Advance.query.filter(Advance.user_id == user_id, Advance.status.ilike(f'%{query}%')).all()

    @staticmethod
    def update_advance_status(advance_id, status):
        advance = Advance.query.get(advance_id)
        if advance:
            advance.status = status
            db.session.commit()
            return advance
        return None

    @staticmethod
    def get_payment_history(transaction_id):
        try:
            # Retrieve the specific transaction by its ID
            transaction = Transaction.query.get(transaction_id)
            if not transaction:
                raise ValueError("Transaction not found")
            return transaction.to_dict()
        except SQLAlchemyError as e:
            raise Exception(f"Database error occurred: {str(e)}")
        except ValueError as e:
            raise ValueError(str(e))