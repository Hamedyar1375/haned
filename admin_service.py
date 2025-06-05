from sqlalchemy.orm import Session
from app.db.models.admin import Admin
from app.schemas.admin import AdminCreate
from app.utils.security import create_password_hash

def create_admin_user(db: Session, admin: AdminCreate) -> Admin:
    """
    Creates a new admin user in the database.
    """
    hashed_password = create_password_hash(admin.password)
    db_admin = Admin(
        username=admin.username,
        password_hash=hashed_password
        # email can be added here if it were part of AdminCreate and Admin model
    )
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin

def get_admin_by_username(db: Session, username: str) -> Admin | None:
    """
    Retrieves an admin user by username.
    """
    return db.query(Admin).filter(Admin.username == username).first()

def create_initial_admin(db: Session):
    """
    Creates an initial admin user if one doesn't exist.
    This is useful for bootstrapping the application.
    Call this function carefully, perhaps once on startup.
    """
    # Check if an admin user already exists
    existing_admin = get_admin_by_username(db, "admin") # Default username "admin"
    if not existing_admin:
        initial_admin_data = AdminCreate(username="admin", password="changeme") # Default password
        print(f"Creating initial admin user: {initial_admin_data.username}")
        create_admin_user(db, initial_admin_data)
        print("Initial admin user created. PLEASE CHANGE THE DEFAULT PASSWORD!")
    else:
        print("Admin user 'admin' already exists.")
