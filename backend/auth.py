"""
Authentication module for AutoVision backend
Handles Supabase authentication and user management
"""

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Union, Dict, Any
import jwt
import os
from loguru import logger

from supabase import create_client

# Import our custom SupabaseClient
from backend.autovision_client import SupabaseClient, supabase_client


class AuthUser(BaseModel):
    """Authenticated user model"""
    id: str
    email: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request model"""
    email: str
    password: str


class SignupRequest(BaseModel):
    """Signup request model"""
    email: str
    password: str
    full_name: Optional[str] = None


class AuthResponse(BaseModel):
    """Authentication response model"""
    access_token: str
    refresh_token: str
    user: AuthUser
    expires_in: int


# Security scheme
security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthUser:
    """Get current authenticated user from JWT token with database validation"""
    
    try:
        # Get token from credentials
        token = credentials.credentials
        
        # Verify token with Supabase
        client = supabase_client.get_client()
        
        # Get user from token
        user_response = client.auth.get_user(token)
        
        if not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = user_response.user
        
        # IMPORTANT: Validate user exists in database and is verified
        # Use admin client to check user profile existence
        admin_client = supabase_client.get_admin_client()
        
        # Check if user exists in user_profiles and is verified
        profile_check = admin_client.rpc('get_verified_user_profile', {'user_uuid': user.id}).execute()
        
        if not profile_check.data:
            logger.warning(f"User {user.email} ({user.id}) not found in verified user profiles")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or not verified",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        profile_data = profile_check.data[0]
        
        return AuthUser(
            id=user.id,
            email=profile_data.get("email", user.email),
            full_name=profile_data.get("full_name"),
            avatar_url=profile_data.get("avatar_url")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[AuthUser]:
    """Get current user if authenticated, otherwise return None"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


class AuthService:
    """Authentication service for user management"""
    
    def __init__(self):
        self.supabase_client = SupabaseClient()
        self.client = self.supabase_client.get_client()
    
    async def signup(self, signup_data: SignupRequest) -> Union[AuthResponse, Dict[str, Any]]:
        """Register a new user"""
        try:
            # Sign up user with Supabase
            auth_response = self.client.auth.sign_up({
                "email": signup_data.email,
                "password": signup_data.password,
                "options": {
                    "data": {
                        "full_name": signup_data.full_name
                    }
                }            })
            
            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user account. Please check your email format and ensure your password meets the requirements (minimum 6 characters)."
                )
            
            user = auth_response.user
            session = auth_response.session
            
            if not session:
                # User created but needs email verification - this is actually a success case
                logger.info(f"User {user.email} created successfully, email verification required")
                return {
                    "message": "Account created successfully! Please check your email for a verification link, then sign in.",
                    "email": user.email,
                    "verification_required": True
                }
            
            # Create user profile
            try:
                await supabase_client.create_user_profile(
                    user_id=user.id,
                    email=user.email,
                    full_name=signup_data.full_name
                )
                logger.info(f"User profile creation initiated for {user.email}")
            except Exception as profile_error:
                logger.error(f"Failed to create user profile for {user.email}: {profile_error}")
                # Return success message since account was created - user can still log in
                return {
                    "message": "Account created successfully! Please sign in to continue.",
                    "email": user.email,
                    "verification_required": False,
                    "profile_setup_pending": True
                }
            
            # Verify the profile was created successfully by checking with the RPC function
            admin_client = supabase_client.get_admin_client()
            profile_check = admin_client.rpc('get_verified_user_profile', {'user_uuid': user.id}).execute()
            
            if not profile_check.data:
                logger.error(f"Failed to create verified user profile for {user.email} ({user.id})")
                # Return success message since account was created - user can still log in
                return {
                    "message": "Account created successfully! Please sign in to continue.",
                    "email": user.email,
                    "verification_required": False,
                    "profile_setup_pending": True
                }
            
            profile_data = profile_check.data[0]
            
            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=AuthUser(
                    id=user.id,
                    email=profile_data.get("email", user.email),
                    full_name=profile_data.get("full_name"),
                    avatar_url=profile_data.get("avatar_url")
                ),
                expires_in=session.expires_in
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Signup error: {e}")
            logger.error(f"Signup error type: {type(e).__name__}")
            logger.error(f"Signup error details: {str(e)}")
            
            # Provide specific error messages based on the error
            error_message = str(e).lower()
            
            # Check for Supabase-specific errors
            if hasattr(e, 'message'):
                error_message = str(e.message).lower()
                logger.error(f"Supabase error message: {e.message}")
            
            if "email" in error_message and ("already" in error_message or "exists" in error_message or "registered" in error_message):
                detail = "An account with this email already exists. Please sign in instead."
            elif "password" in error_message and ("weak" in error_message or "short" in error_message or "length" in error_message):
                detail = "Password does not meet requirements. Please use at least 6 characters."
            elif "email" in error_message and "invalid" in error_message:
                detail = "Please provide a valid email address."
            elif "user" in error_message and ("already" in error_message or "exists" in error_message):
                detail = "An account with this email already exists. Please sign in instead."
            else:
                # Return the actual error for debugging
                detail = f"Registration failed: {str(e)}"
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=detail
            )
    
    async def login(self, login_data: LoginRequest) -> AuthResponse:
        """Authenticate user and return tokens"""
        try:
            # Sign in with Supabase
            auth_response = self.client.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })
            
            if not auth_response.user or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password. Please check your credentials and try again."
                )
            
            user = auth_response.user
            session = auth_response.session
            
            # IMPORTANT: Validate user exists in database and is verified
            # Use admin client to check user profile existence - same as get_current_user
            admin_client = supabase_client.get_admin_client()
            
            # Check if user exists in user_profiles and is verified
            profile_check = admin_client.rpc('get_verified_user_profile', {'user_uuid': user.id}).execute()
            
            if not profile_check.data:
                logger.warning(f"User {user.email} ({user.id}) not found in verified user profiles during login")
                # Sign out the user since they shouldn't be allowed to login
                try:
                    self.client.auth.sign_out()
                except:
                    pass
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Account not verified or does not exist in our system. Please contact support if you believe this is an error."
                )
            
            profile_data = profile_check.data[0]
            
            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=AuthUser(
                    id=user.id,
                    email=profile_data.get("email", user.email),
                    full_name=profile_data.get("full_name"),
                    avatar_url=profile_data.get("avatar_url")
                ),
                expires_in=session.expires_in
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error: {e}")
            # Provide specific error messages based on the error
            error_message = str(e).lower()
            if "invalid" in error_message and ("password" in error_message or "credentials" in error_message):
                detail = "Invalid email or password. Please check your credentials and try again."
            elif "email" in error_message and "not" in error_message and "confirmed" in error_message:
                detail = "Please check your email and click the verification link before signing in."
            elif "too many" in error_message:
                detail = "Too many login attempts. Please wait a moment and try again."
            else:
                detail = "Login failed. Please check your credentials and try again."
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=detail
            )

    async def refresh_token(self, refresh_token: str) -> AuthResponse:
        """Refresh access token"""
        try:
            auth_response = self.client.auth.refresh_session(refresh_token)
            
            if not auth_response.user or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            user = auth_response.user
            session = auth_response.session
            
            # IMPORTANT: Validate user still exists in database and is verified
            # Use admin client to check user profile existence
            admin_client = supabase_client.get_admin_client()
            
            # Check if user exists in user_profiles and is verified
            profile_check = admin_client.rpc('get_verified_user_profile', {'user_uuid': user.id}).execute()
            
            if not profile_check.data:
                logger.warning(f"User {user.email} ({user.id}) not found in verified user profiles during token refresh")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account not found or not verified"
                )
            
            profile_data = profile_check.data[0]
            
            return AuthResponse(
                access_token=session.access_token,
                refresh_token=session.refresh_token,
                user=AuthUser(
                    id=user.id,
                    email=profile_data.get("email", user.email),
                    full_name=profile_data.get("full_name"),
                    avatar_url=profile_data.get("avatar_url")
                ),
                expires_in=session.expires_in
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to refresh token"
            )
    
    async def logout(self, access_token: str) -> bool:
        """Logout user and invalidate token"""
        try:
            self.client.auth.sign_out()
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False
    
    async def update_profile(self, user_id: str, full_name: Optional[str] = None,
                           avatar_url: Optional[str] = None) -> AuthUser:
        """Update user profile"""
        try:
            # Update user profile in database
            data = {}
            if full_name is not None:
                data["full_name"] = full_name
            if avatar_url is not None:
                data["avatar_url"] = avatar_url
            
            if data:
                result = (supabase_client.get_client()
                         .table("user_profiles")
                         .update(data)
                         .eq("id", user_id)
                         .execute())
                
                if result.data:
                    profile = result.data[0]
                    return AuthUser(
                        id=profile["id"],
                        email=profile["email"],
                        full_name=profile.get("full_name"),
                        avatar_url=profile.get("avatar_url")
                    )
            
            # Return current profile if no updates
            profile = supabase_client.get_user_profile(user_id)
            return AuthUser(
                id=user_id,
                email=profile["email"],
                full_name=profile.get("full_name"),
                avatar_url=profile.get("avatar_url")
            )
            
        except Exception as e:
            logger.error(f"Profile update error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )


# Global auth service instance
auth_service = AuthService()
