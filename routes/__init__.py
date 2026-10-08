from .auth import auth_bp
from .dashboard import dashboard_bp
from .members import members_bp
from .trainers import trainers_bp
from .memberships import memberships_bp
from .attendance import attendance_bp
from .payments import payments_bp
from .reports import reports_bp
from .notifications import notifications_bp
from .settings import settings_bp
from .member import member_bp
from .trainer import trainer_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(trainers_bp)
    app.register_blueprint(memberships_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(member_bp)
    app.register_blueprint(trainer_bp)
