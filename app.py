# import eventlet
import json
import bcrypt
import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from flask_mqtt import Mqtt
from flask_pymongo import PyMongo

from middleware.auth import auth, guest

# eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET'] = 'my secret key'
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'
app.config['TEMPLATES_AUTO_RELOAD'] = True

app.config['MQTT_BROKER_URL'] = 'raspberrypi'
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_USERNAME'] = ''
app.config['MQTT_PASSWORD'] = ''
app.config['MQTT_KEEPALIVE'] = 5
app.config['MQTT_TLS_ENABLED'] = False
app.config['MQTT_CLEAN_SESSION'] = True

app.config["MONGO_URI"] = "mongodb://localhost:27017/technocrats"

# Parameters for SSL enabled
# app.config['MQTT_BROKER_PORT'] = 8883
# app.config['MQTT_TLS_ENABLED'] = True
# app.config['MQTT_TLS_INSECURE'] = True
# app.config['MQTT_TLS_CA_CERTS'] = 'ca.crt'


mqtt = Mqtt(app)
# socketio = SocketIO(app)
mongo = PyMongo(app)

@mqtt.on_connect()
def handle_connect(client, userdata, flags, rc):
    print("Connected to mqtt")
    mqtt.subscribe("technocrat/temp")
    mqtt.subscribe("technocrat/humid")

@mqtt.on_message()
def handle_mqtt_message(client, userdata, message):
    # print("Receiving data")
    _, topic = message.topic.split("/")
    data = dict(
        date=datetime.datetime.utcnow(),
        value=message.payload.decode()
    )
    update_records(topic, data)


@mqtt.on_log()
def handle_logging(client, userdata, level, buf):
   # print(level, buf)
   pass


def update_records(topic, data):
    if topic == 'temp':
        mongo.db.temps.insert_one(data)
    elif topic == 'humid':
        mongo.db.humids.insert_one(data)
    else:
        print("No valid topic")



@app.route('/')
@auth
def home():
    return render_template('pages/index.html')


@app.route('/login', methods=['GET', 'POST'])
@guest
def login():
    if request.method == 'POST':
        username = request.form.get('t_username')
        password = request.form.get('t_password')
        user = mongo.db.users.find_one({"username": username})
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
            session['logged_in'] = True
            session['username'] = username
            session['name'] = user['name']

            return redirect(url_for('home'))
        flash("Invalid username or password", "danger")
        return redirect(url_for("login", old={'username': username}))

    return render_template('pages/auth/login.html', message="Hello, Programmers")


@app.route('/logout', methods=['POST'])
@auth
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    session.pop('name', None)

    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
@guest
def register():
    if request.method == 'POST':
        name = request.form.get('t_name')
        username = request.form.get('t_username')
        password = request.form.get('t_password')

        if mongo.db.users.find_one({'username': username}) is not None:
            flash("Username already taken", "danger")
            return redirect(url_for('register'), 302)
        mongo.db.users.insert({
            'name': name,
            'username': username,
            'password': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        })
        session['logged_in'] = True
        session['username'] = username
        session['name'] = name
        if request.args.get('next'):
            return redirect(request.args.get('next'))
        return redirect(url_for('home'))

    return render_template('pages/auth/register.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, use_reloader=True, debug=True)
