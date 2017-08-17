import os
import getopt
import random
import re
import sys
import paho.mqtt.client as paho
from urllib.parse import urlparse

# Load Heroku Config Variables (https://devcenter.heroku.com/articles/config-vars)
SIMYO_USER = os.environ['SIMYO_USER']
SIMYO_PASS = os.environ['SIMYO_PASS']
SIMYO_NUMB = os.environ['SIMYO_NUMB']
DEBUG = os.getenv('DEBUG', False) == "True"

# Define event callbacks
def on_connect(mosq, obj, rc):
    print("rc: " + str(rc))

def on_message(mosq, obj, msg):
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))

def on_publish(mosq, obj, mid):
    print("mid: " + str(mid))

def on_subscribe(mosq, obj, mid, granted_qos):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))

def on_log(mosq, obj, level, string):
    print(string)

mqttc = paho.Client()
# Assign event callbacks
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

# Parse CLOUDMQTT_URL (or fallback to localhost)
url_str = os.environ.get('CLOUDMQTT_URL', 'mqtt://localhost:1883')
url = urlparse(url_str)

# Connect
mqttc.username_pw_set(url.username, url.password)
mqttc.connect(url.hostname, url.port)

def main(argv):
    # Publish a message
    mqttc.publish("hello/world", "my message")

if __name__ == "__main__":
    main(sys.argv[1:])
