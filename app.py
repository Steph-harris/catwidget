import os

from html import unescape
from flask_caching import Cache
from flask import Flask
from flask_cors import CORS
from flask import render_template, request, url_for
import requests
import yarl


app = Flask(__name__)
app.config.from_mapping({
    "DEBUG": False,
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "PREFERRED_URL_SCHEME": "https"
})
CORS(app, resources={r"/": {"origins": "*"}})
SERVER_NAME = os.environ.get('SERVER_ NAME', 'localhost')
cache = Cache(app)

BASE_URL = yarl.URL(
    'https://api.petfinder.com/v2/animals').with_query(
    {'organization': 'PA16', 'status': 'adoptable'})
CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']
STYLES = ('bulletin', 'tabs')


@app.route("/")
def index():
    page = request.args.get('page', '')
    if page:
        url = BASE_URL.join(yarl.URL(page))
    else:
        url = BASE_URL
    token_response = requests.post(
        'https://api.petfinder.com/v2/oauth2/token',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={'grant_type': 'client_credentials',
              'client_id': CLIENT_ID,
              'client_secret': CLIENT_SECRET},
        timeout=(3.05, 3))

    if token_response.status_code != 200:
        return render_template('index.html', fallback=True)
    else:
        token = token_response.json()['access_token']
        app.logger.info('Getting url %s', url)
        response = requests.get(url,
                                headers={'Authorization': f'Bearer {token}'},
                                timeout=(3.05, 3))
        if response.status_code != 200:
            return render_template('index.html', fallback=True)
    body = response.json()
    animals = [{k: unescape(str(v))
               if k in ('name', 'description') else v
               for k, v in item.items()}
               for item in body['animals']]
    pagination = body.get('pagination', {}).get('_links', {})
    prv = pagination.get('previous', {}).get('href', '')
    nxt = pagination.get('next', {}).get('href', '')

    prev_link = url_for(
        'index', page=prv, _external=True, _scheme='https') if prv else None
    next_link = url_for(
        'index', page=nxt, _external=True, _scheme='https') if nxt else None
    embed = request.args.get('embed')

    if embed:
        prv_link = yarl.URL(str(prev_link)).update_query(
            embed='True') if prv else None
        nxt_link = yarl.URL(str(next_link)).update_query(
            embed='True') if nxt else None
        return render_template('embed.html',
                               animals=animals,
                               next_link=nxt_link,
                               prev_link=prv_link)

    return render_template('index.html',
                           animals=animals,
                           next_link=next_link,
                           prev_link=prev_link,
                           long=True if not request.args.get(
                               'short') else False)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
