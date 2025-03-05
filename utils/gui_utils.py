from dash import Dash
from flask import Flask

server = Flask(__name__)
app = Dash(server=server)
