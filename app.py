from logging.config import dictConfig
import json
import os
import socket

from html import unescape
from flask_caching import Cache
from flask import Flask
from flask_cors import CORS, cross_origin
from flask import render_template, request, url_for
import requests
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import yarl


version = '1.0.6'
app = Flask(__name__)
dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})
app.config.from_mapping({
    "DEBUG": False,
    "CACHE_TYPE": "simple",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "PREFERRED_URL_SCHEME": "https"
})
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[FlaskIntegration()]
    )
TRUSTED_ORIGINS = os.environ.get(
    'TRUSTED_ORIGINS', 'localhost 127.0.0.1')
CORS(app, resources={r"/": {"origins": TRUSTED_ORIGINS},
                     r"/sponsor": {"origins": TRUSTED_ORIGINS}})
SERVER_NAME = os.environ.get('SERVER_NAME', 'localhost')
cache = Cache(app)

BASE_PETFINDER_URL = yarl.URL(
    'https://api.petfinder.com/v2/animals').with_query(
    {'organization': 'PA16', 'status': 'adoptable'})
BASE_SPONSOR_URL = yarl.URL(
    os.environ.get('BASE_SPONSOR_URL', 'https://sponsor-cat.herokuapp.com'))
CLIENT_ID = os.environ['PETFINDER_CLIENT_ID']
CLIENT_SECRET = os.environ['PETFINDER_CLIENT_SECRET']
PAYPAL_CLIENT_ID = os.environ['PAYPAL_CLIENT_ID']
SCHEME = os.environ.get('SCHEME', 'https')


@app.route("/", methods=['GET'])
def index():
    page = request.args.get('page', '')
    if page:
        url = BASE_PETFINDER_URL.join(yarl.URL(page))
    else:
        url = BASE_PETFINDER_URL
    body = make_petfinder_request(url)
    if not body:
        return render_template('index.html', fallback=True)
    animals = [{k: unescape(str(v))
               if k in ('name', 'description') else v
               for k, v in item.items()}
               for item in body['animals']]
    cat_ids = {cat['id'] for cat in animals}
    sponsored_cats = []
    try:
        sponsored_cats = make_sponsor_request({'cat_ids': list(cat_ids)})
    except:
        pass
    if sponsored_cats:
        for animal in animals:
            if animal['id'] in sponsored_cats:
                animal['is_sponsored'] = True
    pagination = body.get('pagination', {}).get('_links', {})
    prv = pagination.get('previous', {}).get('href', '')
    nxt = pagination.get('next', {}).get('href', '')

    kwargs = {'_external': True, '_scheme': SCHEME}
    prev_link = url_for(
        'index', page=prv, **kwargs) if prv else None
    next_link = url_for(
        'index', page=nxt, **kwargs) if nxt else None
    header = request.args.get('header', False)

    return render_template('index.html',
                           animals=animals,
                           scheme=SCHEME,
                           next_link=next_link,
                           prev_link=prev_link,
                           header=header)


def make_petfinder_request(url):
    try:
        token_response = requests.post(
            'https://api.petfinder.com/v2/oauth2/token',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data={'grant_type': 'client_credentials',
                  'client_id': CLIENT_ID,
                  'client_secret': CLIENT_SECRET},
            timeout=(3.05, 3))
    except (OSError, socket.error, requests.exceptions.RequestException) as e:
        app.logger.warning('Error making request to url:%r error:%r', url, e)
        return

    if token_response.status_code != 200:
        app.logger.warning('Error retrieving new token: %r',
                           token_response.content)
        return
    else:
        token = token_response.json()['access_token']
        app.logger.info('token %s', token)
        app.logger.info('Getting url %s', url)
        response = requests.get(url,
                                headers={'Authorization': f'Bearer {token}'},
                                timeout=(3.05, 3))
        if not response.ok:
            app.logger.warning('Error making request to url:%r '
                               'code:%r error:%r',
                               url,
                               response.status_code,
                               response.content)
            return
    app.logger.debug(response.json())
    return response.json()


def make_sponsor_request(body):
    url = BASE_SPONSOR_URL / 'sponsored'
    app.logger.info('Posting to url %s', url)
    try:
        response = requests.post(url,
                                 data=json.dumps(body),
                                 headers={'User-Agent': f'catwidget/{version}',
                                          'Content-Type': 'application/json',
                                          'Accept': 'application/json'},
                                 timeout=(6.05, 10),
                                 )
    except (OSError, socket.error, requests.exceptions.RequestException) as e:
        app.logger.warning('Error making request to url:%r error:%r', url, e)
        return
    app.logger.info('Request: %r', response.request.headers)
    if response.status_code != 200:
        app.logger.warning('Error making request to url:%r error:%r',
                           url,
                           response.content)
        return
    app.logger.debug(response.json())
    return response.json().get('cat_ids')


@app.route("/sponsor/<cat_id>", methods=['GET'])
@cross_origin(origins=TRUSTED_ORIGINS, allow_headers=['Content-Type'])
def sponsor(cat_id):
    sponsor_body = make_sponsor_request(body={'cat_ids': [cat_id]})

    petfinder_url = BASE_PETFINDER_URL.with_query({}) / cat_id
    body = make_petfinder_request(petfinder_url)
    if not body:
        return render_template('index.html', fallback=True)
    prices = {'baby': 105, 'young': 95, 'adult': 95, 'senior': 95}
    sponsor_amount = prices[body['animal']['age'].lower()]
    cat_ids = sponsor_body if sponsor_body else []
    header = request.args.get('header', False)

    if len(cat_ids) > 0 and str(cat_ids.pop(0)) == str(cat_id):
        return render_template('already-sponsor.html',
                               cat_id=cat_id,
                               cat=body['animal'],
                               scheme=SCHEME,
                               header=header)
    animal = {k: unescape(str(v))
              if k in ('name', 'description') else v
              for k, v in body['animal'].items()}
    return render_template(
        'sponsor.html',
        cat_id=cat_id,
        cat=animal,
        scheme=SCHEME,
        order_intent_url=os.environ.get('ORDER_INTENT_URL',
                                        'http://localhost/intent'),
        order_callback_url=os.environ.get('ORDER_CALLBACK_URL',
                                          'http://localhost/sponsor'),
        sponsor_amount=sponsor_amount,
        paypal_client_id=PAYPAL_CLIENT_ID,
        header=header)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
