import os

# Local packages
from core import install

install.InstallDependencies(os.path.abspath(os.path.dirname(__file__)))

from .src import job_search