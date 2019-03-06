import os
import getopt
import random
import re
import sys
import paho.mqtt.client as paho
import urlparse
import argparse
import pyDes
import base64
import urllib
import urllib2
import hmac
import hashlib
import json
import datetime
import pprint
import collections
from time import time

# Load Heroku Config Variables (https://devcenter.heroku.com/articles/config-vars)
SIMYO_USER = os.environ['SIMYO_USER']
SIMYO_PASS = os.environ['SIMYO_PASS']
SIMYO_NUMB = os.environ['SIMYO_NUMB']
BASE_URL = os.getenv('BASE_URL', 'https://api.simyo.es/simyo-api/')
VERBOSE = os.getenv('DEBUG', False) == "True"

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
url = urlparse.urlparse(url_str)

# Connect
mqttc.username_pw_set(url.username, url.password)
mqttc.connect(url.hostname, url.port)

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def getApiSig(url):
        dig = hmac.new(b'f25a2s1m10', msg='f25a2s1m10' + url.lower(), digestmod=hashlib.sha256).digest()
        return url + "&apiSig=" + dig.encode('hex')

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def simyopass():
        k = pyDes.triple_des("25d1d4cb0a08403e2acbcbe0", pyDes.ECB, "\0\0\0\0\0\0\0\0", pad=None, padmode=pyDes.PAD_PKCS5)
        d = urllib.quote(base64.b64encode(k.encrypt(SIMYO_PASS)) + '\n')
        #print "Encrypted: %r" % d
        #print "Decrypted: %r" % k.decrypt(base64.b64decode(urllib.unquote(d)))
        return d

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def writeFile(filename, content):
        in_file = open(filename,"wb")
        in_file.write(content)
        in_file.close()

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def convert(data):
        # http://stackoverflow.com/q/1254454/
        if isinstance(data, basestring):
                return str(data)
        elif isinstance(data, collections.Mapping):
                return dict(map(convert, data.iteritems()))
        elif isinstance(data, collections.Iterable):
                return type(data)(map(convert, data))
        else:
                return data

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def epoch2date(timestamp, format='%d/%m/%Y'):
        timestamp = str(timestamp)[0:10]
        return datetime.datetime.fromtimestamp(int(timestamp)).strftime(format)

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def api_request(url, data="", check=True):
        kPublicKey="a654fb77dc654a17f65f979ba8794c34"

        if url[-1:] == "?":
                url=url + "publicKey=" + kPublicKey
        else:
                url=url + "&publicKey=" + kPublicKey

        url=getApiSig(url)

        if VERBOSE:
                print "URL: " + url

        if data=="":
                req = urllib2.Request(url)
        else:
                req = urllib2.Request(url,data)

        try:
                result = urllib2.urlopen(req).read()
        except urllib2.HTTPError as e:
                print e
                sys.exit(1)
        except urllib2.URLError as e:
                print e
                sys.exit(1)
        except:
                print "Unexpected error :("
                raise

        if check==True:
                data = json.loads(result)['header']
                if int(data['code']) != 100:
                        print "ERROR in request:\n" + str(url) + "\n"
                        data = convert(data)
                        pp = pprint.PrettyPrinter(indent=0)
                        pp.pprint(data)
                        sys.exit(1)

        return result

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def api_logout():
        URL=BASE_URL+"/logout?sessionId=" + str(sessionId)
        result = api_request(URL,"",False)
        if VERBOSE: print result + "\n"

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def api_login():
        global sessionId, customerId

        SIMYOPASS = simyopass()
        URL=BASE_URL+"/login?"
        data = "user=" + SIMYO_USER + "&password=" + SIMYOPASS + "&apiSig=null"
        result = api_request(URL,data)
        if VERBOSE: print result + "\n"

        sessionId = json.loads(result)['response']['sessionId']
        customerId = json.loads(result)['response']['customerId']

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def subscriptions():
        global registerDate, mainProductId, billCycleType, msisdn, subscriberId, payType

        URL=BASE_URL+"/subscriptions/" + str(customerId) + "?sessionId=" + str(sessionId)
        result = api_request(URL)
        if VERBOSE: print result + "\n"

        data = json.loads(result)
        for subscription in reversed(data['response']['subcriptions']):
                registerDate = subscription['registerDate']
                mainProductId = subscription['mainProductId']
                billCycleType = subscription['billCycleType']
                msisdn = subscription['msisdn']
                subscriberId = subscription['subscriberId']
                payType = subscription['subscriberId']

                # retrieve consumption for this number
                data=consumptionByCycle()
                # Publish a message
                mqttc.publish("simyo/"+msisdn+"/consumptionsByCycle", json.dumps(data, separators=(',',':')), retain=True)

# source: https://github.com/poliva/random-scripts/tree/master/simyo
def consumptionByCycle(billCycleCount=1):
        URL=BASE_URL+"/consumptionByCycle/" + str(customerId) + "?sessionId=" + str(sessionId) + "&msisdn=" + str(msisdn) + "&billCycleType=" + str(billCycleType) + "&registerDate=" + str(registerDate) + "&billCycle=" + str(billCycle) + "&billCycleCount=" + str(billCycleCount) + "&payType=" + str(payType)
        result = api_request(URL)
        data = json.loads(result)['response']['consumptionsByCycle'][0]
        return data

def main(argv):
    global billCycle
    billCycle=1

    api_login()
    subscriptions()
    api_logout()

    sys.exit(0)

if __name__ == "__main__":
    main(sys.argv[1:])
