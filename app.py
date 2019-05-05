import os

from flask_caching import Cache
from flask import Flask
from flask import render_template
import requests


app = Flask(__name__)
app.config.from_mapping({
    "DEBUG": False,
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 300
})
cache = Cache(app)

CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']


@app.route("/")
@cache.cached(timeout=3600)
def index():
    token_response = requests.post(
        'https://api.petfinder.com/v2/oauth2/token',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={'grant_type': 'client_credentials',
              'client_id': CLIENT_ID,
              'client_secret': CLIENT_SECRET})
    token = token_response.json()['access_token']
    response = requests.get(
        'https://api.petfinder.com/v2/animals'
        '?organization=PA16&status=adoptable',
        headers={'Authorization': f'Bearer {token}'})
    animals = response.json()['animals']
    return render_template('index.html', animals=animals)
