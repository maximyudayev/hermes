from dash import Dash
from flask import Flask

server = Flask()
app = Dash(server=server)
