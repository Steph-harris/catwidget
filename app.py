import os

from html import unescape
from flask_caching import Cache
from flask import Flask
from flask_cors import CORS, cross_origin
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
CORS(app, resources={r"/": {"origins": os.environ.get(
    'TRUSTED_ORIGINS', 'localhost 127.0.0.1')}})
SERVER_NAME = os.environ.get('SERVER_ NAME', 'localhost')
cache = Cache(app)

BASE_URL = yarl.URL(
    'https://api.petfinder.com/v2/animals').with_query(
    {'organization': 'PA16', 'status': 'adoptable'})
CLIENT_ID = os.environ['CLIENT_ID']
CLIENT_SECRET = os.environ['CLIENT_SECRET']
SCHEME = os.environ.get('SCHEME', 'https')


@app.route("/", methods=['GET'])
def index():
    page = request.args.get('page', '')
    if page:
        url = BASE_URL.join(yarl.URL(page))
    else:
        url = BASE_URL
    body = make_petfinder_request(url)
    if not body:
        return render_template('index.html', fallback=True)
    animals = [{k: unescape(str(v))
               if k in ('name', 'description') else v
               for k, v in item.items()}
               for item in body['animals']]
    pagination = body.get('pagination', {}).get('_links', {})
    prv = pagination.get('previous', {}).get('href', '')
    nxt = pagination.get('next', {}).get('href', '')

    prev_link = url_for(
        'index', page=prv, _external=True, _scheme=SCHEME) if prv else None
    next_link = url_for(
        'index', page=nxt, _external=True, _scheme=SCHEME) if nxt else None
    show_sponsor = request.args.get('sponsor', None)

    return render_template('index.html',
                           animals=animals,
                           scheme=SCHEME,
                           sponsor_on=show_sponsor,
                           next_link=next_link,
                           prev_link=prev_link)


def make_petfinder_request(url):
    token_response = requests.post(
        'https://api.petfinder.com/v2/oauth2/token',
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        data={'grant_type': 'client_credentials',
              'client_id': CLIENT_ID,
              'client_secret': CLIENT_SECRET},
        timeout=(3.05, 3))

    if token_response.status_code != 200:
        app.logger.warning('Error retrieving new token: %r',
                           token_response.content)
        return
    else:
        token = token_response.json()['access_token']
        app.logger.info('Getting url %s', url)
        response = requests.get(url,
                                headers={'Authorization': f'Bearer {token}'},
                                timeout=(3.05, 3))
        if response.status_code != 200:
            app.logger.warning('Error making request to url:%r error:%r',
                               url,
                               token_response.content)
            return
    app.logger.debug(response.json())
    return response.json()


@cross_origin(allow_headers=['Content-Type'])
@app.route("/sponsor/<cat_id>", methods=['GET'])
def sponsor(cat_id):
    url = BASE_URL.with_query({}) / cat_id
    body = make_petfinder_request(url)
    if not body:
        return render_template('index.html', fallback=True)
    prices = {'baby': 105, 'young': 95, 'adult': 95, 'senior': 95}
    sponsor_amount = prices[body['animal']['age'].lower()]
    return render_template(
        'sponsor.html',
        cat_id=cat_id,
        cat=body['animal'],
        scheme=SCHEME,
        order_callback_url=os.environ.get('ORDER_CALLBACK_URL',
                                          'http://localhost/sponsor'),
        sponsor_amount=sponsor_amount)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
