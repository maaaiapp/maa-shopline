import base64, os, pytest
from app.config import Settings

KEY = base64.b64encode(b"k" * 32).decode()

@pytest.fixture
def settings():
    return Settings(env="test", supabase_ref="a" * 20, shopline_app_key="appkey", shopline_app_secret="s3cret",
                    shopline_redirect_uri="https://api.example.test/auth/shopline/callback",
                    shopline_scopes="read_orders", token_encryption_key=KEY)
