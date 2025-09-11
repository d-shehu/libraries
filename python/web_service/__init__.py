import os

# Local packages
from core import install

install.InstallDependencies(os.path.abspath(os.path.dirname(__file__)))

from .src           import context, processor, requests, router, service, user_auth, user_mgr, user
from .src.routers   import users_router
