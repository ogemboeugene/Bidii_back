import bcrypt
from flask import Flask
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
from app.models import User
from .extensions import db, ma, jwt, mail
from .config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)
    Migrate(app, db)


    with app.app_context():
        from .routes import auth, transaction, performance, notification, advance, history
        app.register_blueprint(auth.bp)
        app.register_blueprint(transaction.bp)
        app.register_blueprint(performance.bp)
        app.register_blueprint(notification.bp)
        app.register_blueprint(advance.bp)
        app.register_blueprint(history.bp)
        
        # Create the database tables if they don't exist
        with app.app_context():
            db.create_all()
            create_superuser(app)

    return app

def create_superuser(app):
    with app.app_context():
        superuser = User.query.filter_by(username='admin').first()
        if not superuser:
            # Create a superuser
            password = 'adminpassword'
            hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            superuser = User(
                username='admin',
                email='admin@gmail.com',
                password_hash=hashed_password.decode(),  # Store as a string
                role='admin',
                is_admin=True
            )
            db.session.add(superuser)
            db.session.commit()