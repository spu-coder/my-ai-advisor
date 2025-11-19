"""
Security Middleware Module
==========================
This module implements OWASP security best practices including:
- Rate limiting
- Security headers
- Input validation and sanitization
- Request size limits
- SQL injection prevention helpers

وحدة أمان الوسطاء
==================
هذه الوحدة تطبق أفضل ممارسات أمان OWASP بما في ذلك:
- تحديد معدل الطلبات
- رؤوس الأمان
- التحقق من المدخلات وتنظيفها
- حدود حجم الطلب
- مساعدات منع حقن SQL
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
import time
from collections import defaultdict
from typing import Dict, Tuple
import re
import logging

logger = logging.getLogger("SECURITY_MIDDLEWARE")

# ------------------------------------------------------------
# Rate Limiting Configuration
# إعدادات تحديد معدل الطلبات
# ------------------------------------------------------------
RATE_LIMIT_WINDOW = 60  # seconds / ثواني
RATE_LIMIT_MAX_REQUESTS = 100  # requests per window / طلبات لكل نافذة
RATE_LIMIT_AUTH_MAX = 10  # login attempts per window / محاولات تسجيل دخول لكل نافذة

# Store request counts per IP
# تخزين عدد الطلبات لكل عنوان IP
request_counts: Dict[str, list] = defaultdict(list)
auth_attempts: Dict[str, list] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    / وسطاء تحديد معدل الطلبات لمنع إساءة الاستخدام.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        # Check rate limit for authentication endpoints
        # التحقق من حد المعدل لمسارات المصادقة
        if path in ["/token", "/token/json", "/register/student", "/register/admin"]:
            if not self._check_auth_rate_limit(client_ip):
                logger.warning(f"Rate limit exceeded for auth endpoint from IP: {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many authentication attempts. Please try again later.",
                        "error_ar": "عدد كبير جداً من محاولات المصادقة. يرجى المحاولة لاحقاً."
                    }
                )
        
        # Check general rate limit
        # التحقق من حد المعدل العام
        if not self._check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded from IP: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "error_ar": "عدد كبير جداً من الطلبات. يرجى المحاولة لاحقاً."
                }
            )
        
        response = await call_next(request)
        return response
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """Check if client has exceeded rate limit."""
        current_time = time.time()
        # Remove old requests outside the window
        request_counts[client_ip] = [
            req_time for req_time in request_counts[client_ip]
            if current_time - req_time < RATE_LIMIT_WINDOW
        ]
        
        # Check if limit exceeded
        if len(request_counts[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        
        # Add current request
        request_counts[client_ip].append(current_time)
        return True
    
    def _check_auth_rate_limit(self, client_ip: str) -> bool:
        """Check if client has exceeded authentication rate limit."""
        current_time = time.time()
        # Remove old attempts outside the window
        auth_attempts[client_ip] = [
            attempt_time for attempt_time in auth_attempts[client_ip]
            if current_time - attempt_time < RATE_LIMIT_WINDOW
        ]
        
        # Check if limit exceeded
        if len(auth_attempts[client_ip]) >= RATE_LIMIT_AUTH_MAX:
            return False
        
        # Add current attempt
        auth_attempts[client_ip].append(current_time)
        return True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses (OWASP best practices).
    / إضافة رؤوس الأمان لجميع الاستجابات (أفضل ممارسات OWASP).
    """
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # OWASP recommended security headers
        # رؤوس الأمان الموصى بها من OWASP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        return response


# ------------------------------------------------------------
# Input Validation and Sanitization
# التحقق من المدخلات وتنظيفها
# ------------------------------------------------------------

def sanitize_string(input_str: str, max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent injection attacks.
    / تنظيف إدخال النص لمنع هجمات الحقن.
    
    Args:
        input_str: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(input_str, str):
        raise ValueError("Input must be a string")
    
    # Remove null bytes
    input_str = input_str.replace('\x00', '')
    
    # Limit length
    if len(input_str) > max_length:
        input_str = input_str[:max_length]
    
    # Remove potentially dangerous characters (basic)
    # Note: This is basic sanitization. For production, use proper escaping
    # ملاحظة: هذا تنظيف أساسي. للإنتاج، استخدم التهريب المناسب
    dangerous_chars = ['<', '>', '"', "'", '&']
    for char in dangerous_chars:
        input_str = input_str.replace(char, '')
    
    return input_str.strip()


def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID format (alphanumeric and underscores only).
    / التحقق من تنسيق معرف المستخدم (أرقام وحروف وشرطة سفلية فقط).
    """
    if not user_id or len(user_id) > 50:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', user_id))


def validate_email(email: str) -> bool:
    """
    Validate email format.
    / التحقق من تنسيق البريد الإلكتروني.
    """
    if not email or len(email) > 255:
        return False
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    / التحقق من قوة كلمة المرور.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"
    
    # Check for common weak passwords
    # التحقق من كلمات المرور الضعيفة الشائعة
    weak_passwords = ['password', '123456', 'admin', 'qwerty']
    if password.lower() in weak_passwords:
        return False, "Password is too weak. Please choose a stronger password."
    
    return True, ""


def sanitize_sql_input(input_str: str) -> str:
    """
    Basic SQL injection prevention (use parameterized queries instead).
    / منع حقن SQL الأساسي (استخدم استعلامات معاملات بدلاً من ذلك).
    
    WARNING: This is a basic check. Always use parameterized queries!
    / تحذير: هذا فحص أساسي. استخدم دائماً استعلامات معاملات!
    """
    if not isinstance(input_str, str):
        return ""
    
    # Remove SQL keywords that could be used in injection
    # إزالة كلمات SQL الرئيسية التي يمكن استخدامها في الحقن
    sql_keywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'EXEC', 'EXECUTE', 'UNION']
    sanitized = input_str
    for keyword in sql_keywords:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        sanitized = pattern.sub('', sanitized)
    
    return sanitized.strip()


# ------------------------------------------------------------
# Request Size Limiting
# تحديد حجم الطلب
# ------------------------------------------------------------

MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10 MB


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """
    Limit request body size to prevent DoS attacks.
    / تحديد حجم جسم الطلب لمنع هجمات DoS.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Check request size before processing."""
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > MAX_REQUEST_SIZE:
                        logger.warning(f"Request size {size} exceeds limit {MAX_REQUEST_SIZE}")
                        return JSONResponse(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            content={
                                "detail": f"Request too large. Maximum size is {MAX_REQUEST_SIZE / 1024 / 1024} MB",
                                "error_ar": f"الطلب كبير جداً. الحد الأقصى للحجم هو {MAX_REQUEST_SIZE / 1024 / 1024} ميجابايت"
                            }
                        )
                except ValueError:
                    pass
        
        response = await call_next(request)
        return response

