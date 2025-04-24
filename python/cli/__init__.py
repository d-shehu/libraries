import os

# Local packages
from core import install

install.InstallDependencies(os.path.abspath(os.path.dirname(__file__)))

# This package's source
from .src import cli_app, cli_program, cli_program_mode

