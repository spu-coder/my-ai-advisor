import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# تحديد مسار قاعدة البيانات من متغير البيئة
DB_PATH = os.getenv("DB_PATH", "/app/app_data/")
USERS_DB_FILE = os.path.join(DB_PATH, "users.db")
PROGRESS_DB_FILE = os.path.join(DB_PATH, "progress.db")
NOTIFICATIONS_DB_FILE = os.path.join(DB_PATH, "notifications.db")

# التأكد من وجود المجلد
os.makedirs(DB_PATH, exist_ok=True)

# ------------------------------------------------------------
# قاعدة بيانات المستخدمين (Users DB)
# ------------------------------------------------------------
USERS_ENGINE = create_engine(f"sqlite:///{USERS_DB_FILE}")
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True) # معرف الطالب/المستخدم (الرقم الجامعي)
    full_name = Column(String)
    hashed_password = Column(String) # حقل كلمة المرور المشفرة (كلمة سر النظام الجامعي)
    role = Column(String, default="student") # طالب، إداري
    email = Column(String, unique=True, nullable=True) # أصبح اختياري
    university_password = Column(String, nullable=True) # كلمة سر النظام الجامعي (مشفرة)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_data_sync = Column(DateTime, nullable=True) # آخر مرة تم فيها جمع البيانات من النظام الجامعي

    # ملاحظة: لا يمكن استخدام relationship مع جداول في قواعد بيانات منفصلة

# ------------------------------------------------------------
# قاعدة بيانات تقدم الطلاب (Progress DB)
# ------------------------------------------------------------
PROGRESS_ENGINE = create_engine(f"sqlite:///{PROGRESS_DB_FILE}")
ProgressBase = declarative_base()

class ProgressRecord(ProgressBase):
    __tablename__ = "progress_records"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)  # لا يمكن استخدام ForeignKey عبر قواعد بيانات منفصلة
    course_code = Column(String)
    grade = Column(String)
    hours = Column(Integer)
    semester = Column(String)
    course_name = Column(String, nullable=True) # اسم المقرر
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ملاحظة: لا يمكن استخدام relationship عبر قواعد بيانات منفصلة

class StudentAcademicInfo(ProgressBase):
    """معلومات أكاديمية شاملة للطالب من النظام الجامعي"""
    __tablename__ = "student_academic_info"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, unique=True)  # الرقم الجامعي
    gpa = Column(Float, nullable=True)  # المعدل التراكمي
    total_hours = Column(Integer, nullable=True)  # إجمالي الساعات المطلوبة
    completed_hours = Column(Integer, nullable=True)  # الساعات المكتملة
    remaining_hours = Column(Integer, nullable=True)  # الساعات المتبقية
    academic_status = Column(String, nullable=True)  # الحالة الأكاديمية
    current_semester = Column(String, nullable=True)  # الفصل الحالي
    raw_data = Column(JSON, nullable=True)  # البيانات الخام من النظام الجامعي
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RemainingCourse(ProgressBase):
    """المقررات المتبقية للتسجيل"""
    __tablename__ = "remaining_courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    course_code = Column(String, index=True)
    course_name = Column(String, nullable=True)
    hours = Column(Integer, nullable=True)
    prerequisites = Column(String, nullable=True)  # المتطلبات السابقة
    semester = Column(String, nullable=True)  # الفصل المقترح
    raw_data = Column(JSON, nullable=True)  # البيانات الخام
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ------------------------------------------------------------
# قاعدة بيانات الإشعارات (Notifications DB)
# ------------------------------------------------------------
NOTIFICATIONS_ENGINE = create_engine(f"sqlite:///{NOTIFICATIONS_DB_FILE}")
NotificationBase = declarative_base()

class Notification(NotificationBase):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)  # لا يمكن استخدام ForeignKey عبر قواعد بيانات منفصلة
    message = Column(String)
    type = Column(String) # تنبيه، إشعار، توصية
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # ملاحظة: لا يمكن استخدام relationship عبر قواعد بيانات منفصلة

# ------------------------------------------------------------
# وظائف التهيئة
# ------------------------------------------------------------

def init_db():
    # إنشاء الجداول في قواعد البيانات المختلفة
    Base.metadata.create_all(bind=USERS_ENGINE)
    ProgressBase.metadata.create_all(bind=PROGRESS_ENGINE)
    NotificationBase.metadata.create_all(bind=NOTIFICATIONS_ENGINE)

def get_users_session():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=USERS_ENGINE)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_progress_session():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=PROGRESS_ENGINE)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_notifications_session():
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=NOTIFICATIONS_ENGINE)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# تهيئة قواعد البيانات عند استيراد الملف لأول مرة
init_db()
