# app/routes/advance_routes.py

from flask import Blueprint, jsonify, request, current_app
from flask_cors import cross_origin
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from app.schemas.advance import MonthlyAdvanceCreditSchema
from app.schemas import AdvanceSchema
from app.services.advance_service import AdvanceService
from app.models import MonthlyAdvanceCredit, GroupMonthlyPerformance, MonthlyPerformance
from app.extensions import db

bp = Blueprint('advances', __name__)

@bp.route('/advances', methods=['POST'])
@cross_origin()
@jwt_required()
def create_advance():
    try:
        current_user = get_jwt_identity()
        # print(current_user)
        data = request.get_json()
        # print(data)
        data['user_id'] = current_user['id']
        
        # Validate and create the advance
        advance = AdvanceService.create_advance(data)
        serialized_advance = AdvanceSchema().dump(advance)
        return jsonify(serialized_advance), 201

    except ValidationError as e:
        # Log validation errors
        current_app.logger.warning(f"Validation Error: {str(e)}")
        return str(e), 400  # Return error message as plain text

    except ValueError as e:
        # Log value errors with detailed message
        current_app.logger.warning(f"Value Error: {str(e)}")
        return str(e), 400  # Return error message as plain text

    except SQLAlchemyError as e:
        # Log database-related errors
        current_app.logger.error(f"Database Error: {str(e)}")
        return 'A database error occurred. Please try again later.', 500  # Return plain text error message

    except Exception as e:
        # Log any other unexpected errors
        current_app.logger.error(f"Unexpected Error: {str(e)}")
        return 'An unexpected error occurred. Please try again later.', 500 
    
@bp.route('/member_details', methods=['GET'])
@cross_origin()
@jwt_required()
def get_member_details():
    try:
        # Query all member details
        results = GroupMonthlyPerformance.query.with_entities(GroupMonthlyPerformance.member_details).all()
        
        # Extract member details
        member_details = [result.member_details for result in results]
        
        return jsonify(member_details), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500
    
@bp.route('/advances/<int:advance_id>/payment', methods=['POST'])
@cross_origin()
@jwt_required()
def make_payment(advance_id):
    try:
        data = request.get_json()
        payment_amount = data.get('payment_amount')

        if not payment_amount:
            return jsonify({'error': 'Payment amount is required'}), 400

        current_user = get_jwt_identity()
        user_id = current_user['id']

        # Make payment and update advance
        advance = AdvanceService.make_payment(advance_id, payment_amount, user_id)
        serialized_advance = AdvanceSchema().dump(advance)
        return jsonify(serialized_advance), 200

    except ValidationError as e:
        # current_app.logger.warning(f"Validation Error: {str(e)}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/advances/<int:advance_id>', methods=['GET'])
@cross_origin()
@jwt_required()
def get_advance(advance_id):
    try:
        # Retrieve advance details
        advance = AdvanceService.get_advance(advance_id)
        serialized_advance = AdvanceSchema().dump(advance)
        return jsonify(serialized_advance), 200

    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/advances/<int:advance_id>', methods=['PATCH'])
@cross_origin()
@jwt_required()
def update_advance(advance_id):
    try:
        data = request.get_json()
        # Ensure only 'paid_amount' is allowed in the request
        if not ('paid_amount' in data and len(data) == 1):
            raise ValueError("Request data must contain only 'paid_amount'")

        # Update advance details
        advance = AdvanceService.update_advance(advance_id, data)
        serialized_advance = AdvanceSchema().dump(advance)
        return jsonify(serialized_advance), 200

    except ValueError as e:
        # current_app.logger.warning(f"Value Error: {str(e)}")
        return jsonify({'error': str(e)}), 400

    except ValidationError as e:
        # current_app.logger.warning(f"Validation Error: {str(e)}")
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@bp.route('/advances/<int:advance_id>/balance', methods=['GET'])
@cross_origin()
@jwt_required()
def get_remaining_balance(advance_id):
    try:
        # Calculate remaining balance
        remaining_balance = AdvanceService.calculate_remaining_balance(advance_id)
        return jsonify({'remaining_balance': remaining_balance}), 200

    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/advances', methods=['GET'])
@cross_origin()
@jwt_required()
def list_advances():
    group_id = request.args.get('group_id')
    
    if not group_id:
        return jsonify({"error": "Group ID is required"}), 400
    
    try:
        # Get the advances and group name
        result = AdvanceService.list_advances_by_group_id(group_id)
        
        if not result:
            return jsonify({"error": "Group not found"}), 404
        
        # Extract group name and advances from the result
        group_name = result['group_name']
        advances = result['advances']
        
        # Serialize the advances
        serialized_advances = AdvanceSchema(many=True).dump(advances)
        
        # Include the group name in the response
        return jsonify({
            'group_name': group_name,
            'advances': serialized_advances
        }), 200
    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500



@bp.route('/advances/search', methods=['GET'])
@cross_origin()
@jwt_required()
def search_advances():
    try:
        current_user = get_jwt_identity()
        query = request.args.get('query', '')
        advances = AdvanceService.search_advances(current_user['id'], query)
        serialized_advances = AdvanceSchema(many=True).dump(advances)
        return jsonify(serialized_advances), 200
    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/advances/<int:advance_id>/payments', methods=['GET'])
@cross_origin()
@jwt_required()
def get_payment_history(advance_id):
    try:
        payments = AdvanceService.get_payment_history(advance_id)
        return jsonify(payments), 200
    except Exception as e:
        # current_app.logger.error(f"Internal Server Error: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# MonthlyAdvanceCredit
@bp.route('/monthly_advance_credits', methods=['GET'])
@jwt_required() 
@cross_origin()
def get_monthly_advance_credits():
    credits = MonthlyAdvanceCredit.query.all()
    result = [credit.to_dict() for credit in credits]  # Use to_dict to convert models to dicts
    return jsonify(result)

@bp.route('/monthly_advance_credits', methods=['POST'])
@jwt_required()
@cross_origin()
def create_monthly_advance_credit():
    schema = MonthlyAdvanceCreditSchema()

    try:
        # Load and validate the data
        validated_data = schema.load(request.json, session=db.session)

        # Extract group_name from validated_data
        group_name = validated_data.get('group_name') if isinstance(validated_data, dict) else validated_data.group_name

        # Check if the group_name exists in the monthly_performance table
        group = MonthlyPerformance.query.filter_by(group_name=group_name).first()
        if not group:
            return jsonify({"message": f"The group name '{group_name}' is not found in the monthly performance records. Please ensure it is correct or add it to the records before proceeding."}), 404

        # Ensure that the group_name is unique
        existing_credit = MonthlyAdvanceCredit.query.filter_by(group_name=group_name).first()
        if existing_credit:
            return jsonify({"message": f"A record with the group name '{group_name}' already exists. To avoid duplication, use a different group name or update the existing record instead of adding a new one."}), 409

        # Prepare data for creating MonthlyAdvanceCredit instance
        new_credit_data = {
            'group_id': group.id,  # Assign the group_id from the existing group
            'group_name': group_name,
            'date': validated_data.get('date') if isinstance(validated_data, dict) else validated_data.date,
            'total_advance_amount': validated_data.get('total_advance_amount', 0) if isinstance(validated_data, dict) else validated_data.total_advance_amount,
            'deductions': validated_data.get('deductions', 0) if isinstance(validated_data, dict) else validated_data.deductions
        }

        # Create a new instance of MonthlyAdvanceCredit with the prepared data
        new_credit = MonthlyAdvanceCredit(**new_credit_data)

        # Add to session and commit
        db.session.add(new_credit)
        db.session.commit()

        # Return success response
        result = schema.dump(new_credit)
        return jsonify(result), 201

    except ValidationError as err:
        # Log validation errors
        # current_app.logger.error(f"Validation error: {err.messages}")
        return jsonify({"message": "Validation error", "errors": err.messages}), 400

    except ValueError as e:
        # Log value errors
        # current_app.logger.error(f"Value Error: {str(e)}")
        return jsonify({"message": "Value error", "error": str(e)}), 400

    except SQLAlchemyError as e:
        # Log database errors
        # current_app.logger.error(f"Database error occurred: {str(e)}")
        return jsonify({"message": "Database error occurred", "error": str(e)}), 500

    except Exception as e:
        # Log unexpected errors
        # current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"message": "An unexpected error occurred", "error": str(e)}), 500

@bp.route('/monthly_performance/filter', methods=['GET'])
@cross_origin()
def get_all_group_names():
    try:
        # Query all unique group names and their corresponding IDs
        group_data = db.session.query(
            MonthlyPerformance.id, 
            MonthlyPerformance.group_name
        ).distinct().all()

        # Convert the result to a list of dictionaries with 'id' and 'group_name'
        unique_groups = [{'id': id, 'group_name': group_name} for id, group_name in group_data]
        
        # Return the list of unique groups as JSON
        return jsonify(unique_groups), 200
    
    except Exception as e:
        # Log the error for debugging
        # current_app.logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"message": "An error occurred while fetching group names", "error": str(e)}), 500
