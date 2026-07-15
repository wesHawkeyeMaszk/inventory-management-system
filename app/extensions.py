from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Module-level singleton bound to the app in create_app() via init_app().
# Kept separate from app/main.py so route modules (app/routes/products.py)
# can import it without a circular import back into app.main.
limiter = Limiter(key_func=get_remote_address)
