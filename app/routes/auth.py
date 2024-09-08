from datetime import timedelta
import logging
import secrets
import bcrypt
from flask import Blueprint, current_app, request, jsonify, url_for
from flask_cors import cross_origin
from itsdangerous import URLSafeTimedSerializer
from app.models import User
from flask_mail import Message, Mail
from app.extensions import mail, db
from app.schemas import UserSchema
from app.services.auth_service import AuthService
from sqlalchemy.exc import IntegrityError, NoResultFound
from app.services.auth_service import admin_required
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, set_access_cookies, unset_jwt_cookies

from app.utils.helpers import hash_password

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
bp = Blueprint('auth', __name__)
s = URLSafeTimedSerializer(secret_key=secrets.token_hex(32))


@bp.route('/signup', methods=['POST'])
@jwt_required()
@cross_origin()
@admin_required
def signup():
    try:
        data = request.get_json()

        # Debug statement for incoming data
        # logger.debug(f"Received data: {data}")
        user = AuthService.create_user(data)
        user_schema = UserSchema()
        result = user_schema.dump(user)
        if user:
            return jsonify(result), 201
        return jsonify({'message': 'Failed to create user.'}), 400
    except IntegrityError as e:
        db.session.rollback()  # Rollback the session to prevent partially committed data
        return jsonify({'message': 'Username or email already exists', 'error': str(e)}), 400
    except Exception as e:
        return jsonify({'message': 'Failed to create user', 'error': str(e)}), 500

@bp.route('/signin', methods=['POST'])
@cross_origin()
def signin():
    try:
        data = request.get_json()
        user, token = AuthService.authenticate_user(data)
        if user:
            return jsonify({'user': UserSchema().dump(user), 'token': token}), 200
        else:
            return jsonify({'message': 'Invalid credentials'}), 401
    except NoResultFound:
        return jsonify({'message': 'User not found'}), 401
    except ValueError as e:
        return jsonify({'message': str(e)}), 401
    except Exception as e:
        return jsonify({'message': 'Failed to sign in', 'error': str(e)}), 500

@bp.route('/set_remember_me', methods=['POST'])
@jwt_required()
@cross_origin()
def set_remember_me():
    try:
        data = request.get_json()
        remember_me = data.get('remember_me', False)  # Get "remember me" option, default to False
        
        # Retrieve the current user from the JWT token
        current_user_identity = get_jwt_identity()
        user_id = current_user_identity.get('id')
        
        # Determine the expiration time based on the "Remember Me" option
        expires_delta = timedelta(days=30) if remember_me else timedelta(hours=1)
        
        # Create a new access token with the updated expiration
        new_token = create_access_token(identity={'id': user_id}, expires_delta=expires_delta)
        
        response = jsonify({'message': 'Token expiration updated', 'token': new_token})
        set_access_cookies(response, new_token)  # Set JWT token as cookie
        
        return response, 200
    except Exception as e:
        logger.error(f"Error in set_remember_me endpoint: {e}")
        return jsonify({'message': 'Failed to update token expiration', 'error': str(e)}), 500

@bp.route('/forgot_password', methods=['POST'])
@cross_origin()
def forgot_password():
    data = request.get_json()
    identifier = data.get('identifier')  # Email or username
    frontend_base_url = data.get('frontend_base_url')  # Get the frontend base URL from the request

    if not identifier or not frontend_base_url:
        return jsonify({'error': 'Email or username and frontend base URL are required'}), 400

    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()

    if not user:
        return jsonify({'error': 'No account found with that email or username'}), 404

    # Generate token
    token = s.dumps(user.email, salt='password-reset-salt')

    # Create the reset link using the frontend base URL
    reset_link = f"{frontend_base_url}/reset_password/{token}"  # Ensure the path matches your React route

    # Send email
    msg = Message('Password Reset Request', recipients=[user.email])
    msg.body = f'Please click the following link to reset your password: {reset_link}'
    try:
        mail.send(msg)
        return jsonify({'message': 'Password reset link has been sent to your email'}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to send email', 'details': str(e)}), 500
    
@bp.route('/reset_password/<token>', methods=['POST'])
@cross_origin()
def reset_password(token):
    data = request.get_json()
    password = data.get('password')

    if not password:
        return jsonify({'error': 'Password is required'}), 400

    try:
        # Verify and decode the token
        email = s.loads(token, salt='password-reset-salt', max_age=3600)  # Adjust max_age as needed
    except Exception as e:
        return jsonify({'error': 'Invalid or expired token'}), 400

    # Find the user by email
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Hash the new password using bcrypt (as per your reference code)
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()  # Convert hash to string

    # Update the user's password
    user.password_hash = hashed_password  # Assign the hashed password
    db.session.commit()  # Commit changes to the database

    return jsonify({'message': 'Password has been reset successfully'}), 200

@bp.route('/user_info', methods=['GET'])
@jwt_required()
@cross_origin()
def get_user_info():
    try:
        # Retrieve the user identity from the JWT token
        current_user_identity = get_jwt_identity()
        
        # Fetch the user from the database using the user ID or another identifier
        user_id = current_user_identity.get('id')
        user = db.session.get(User, user_id)
        
        if user:
            user_schema = UserSchema()  # Adjust this if you have a specific schema for user data
            result = user_schema.dump(user)
            return jsonify(result), 200
        else:
            return jsonify({'message': 'User not found.'}), 404

    except Exception as e:
        return jsonify({'message': 'Failed to retrieve user information', 'error': str(e)}), 500

    
# @bp.route('/reset_password_request', methods=['POST'])
# def reset_password_request():
#     data = request.get_json()
#     email = data.get('email')

#     user = User.query.filter_by(email=email).first()
#     if not user:
#         return jsonify({'message': 'Email address not found'}), 404

#     try:
#         token = AuthService.generate_password_reset_token(email)
#         reset_url = url_for('auth.reset_password', token=token, _external=True)
        
#         msg = Message('Password Reset Request',
#                       recipients=[email],
#                       body=f'Please use the following link to reset your password: {reset_url}')
#         mail.send(msg)
#     except Exception as e:
#         print(f"Error sending email: {e}")
#         return jsonify({'message': 'Failed to request password reset', 'error': str(e)}), 500

#     return jsonify({'message': 'Password reset email sent', 'token': token}), 200

# @bp.route('/reset_password/<token>', methods=['POST'])
# def reset_password(token):
#     try:
#         data = request.get_json()
#         new_password = data.get('new_password')

#         email = AuthService.verify_password_reset_token(token)
#         if email:
#             user = User.query.filter_by(email=email).first()
#             if user:
#                 user.password_hash = hash_password(new_password)
#                 db.session.commit()
#                 return jsonify({'message': 'Password has been reset successfully.'}), 200
#             else:
#                 return jsonify({'message': 'User not found.'}), 404
#         else:
#             return jsonify({'message': 'Invalid or expired token.'}), 400
#     except Exception as e:
#         return jsonify({'message': 'Failed to reset password', 'error': str(e)}), 500
    
@bp.route('/logout', methods=['POST'])
@jwt_required()
@cross_origin()
def logout():
    try:
        response = jsonify({"message": "Successfully logged out"})
        unset_jwt_cookies(response)  # This function unsets the JWT cookies
        return response, 200
    except Exception as e:
        logger.error(f"Error during logout: {e}")
        return jsonify({"message": "Failed to log out", "error": str(e)}), 500