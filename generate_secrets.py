#!/usr/bin/env python3
"""
Generate secure secrets for your TL;DW application
"""

import secrets
import string

def generate_session_secret(length=64):
    """Generate a secure session secret"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_simple_secret(length=32):
    """Generate a simpler secret using URL-safe characters"""
    return secrets.token_urlsafe(length)

if __name__ == "__main__":
    print("🔐 TL;DW Security Secrets Generator")
    print("=" * 50)
    
    print("\n1. SESSION_SECRET (for Flask sessions):")
    session_secret = generate_session_secret()
    print(f"SESSION_SECRET={session_secret}")
    
    print("\n2. Alternative SESSION_SECRET (URL-safe):")
    alt_secret = generate_simple_secret()
    print(f"SESSION_SECRET={alt_secret}")
    
    print("\n✅ Copy one of these SESSION_SECRET values to your Vercel environment variables")
    print("\n🔗 For other API keys, follow these links:")
    print("   • Google OAuth: https://console.cloud.google.com/")
    print("   • OpenAI API: https://platform.openai.com/api-keys")
    print("   • Database: Use Vercel Postgres or external provider")