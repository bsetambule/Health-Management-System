from app.extensions import db
from datetime import datetime, date, timezone

class Center(db.Model):
    __tablename__ = "centers"
    centerID = db.Column(db.Integer, primary_key=True)
    centerName = db.Column(db.String(40), nullable=False)
    centerType = db.Column(db.String(30), nullable=False) # hospital or clinic
    centerLocation = db.Column(db.String(20), nullable=False)

    centerManager = db.Column(db.String(40), nullable=True)
    isActive = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc) , nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc) , onupdate=datetime.now(timezone.utc) )
    deactivated_at = db.Column(db.DateTime, nullable=True)

    
    users = db.relationship("User", back_populates="center")
    appointments = db.relationship("Appointment", back_populates="center")
    

    def deactivate(self):
        self.isActive = False
        self.deactivated_at = datetime.now(timezone.utc) 

    def soft_delete(self):
        self.isDeleted = True
        self.deleted_at = datetime.now(timezone.utc)   