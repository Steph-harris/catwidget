import os

from flask_caching import Cache
from flask import Flask
from flask import render_template
from flask import request
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
STYLES = ('bulletin', 'tabs')


@app.route("/")
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

    style = request.args.get('style', '')
    if style in STYLES:
        return render_template('index.html', animals=animals, style=f'{style}.css')
    return render_template('index.html', animals=animals, style='bulletin.css')


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
