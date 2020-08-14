#!/usr/bin/env python3
import time, json, subprocess, urllib, hmac, hashlib, http
import paho.mqtt.client as mqtt

# store checkups to post as one block of checkups
checkups = {}
session = ''.encode('utf-8')
version = 2020
secret_path = "/home/brandon/haldor/.open-sesame"
secret = ''

topics = ["topic/haldor/event", "topic/haldor/checkup", "topic/haldor/bootup"]
def on_log(client, userdata, level, buff):
    print(buff)

def on_connect(client, userdata, flags, rc):
    print("MQTT Connected: " + str(rc))
    for topic in topics:
        client.subscribe(topic)
        print ("Subscribed to " + topic)

def on_message(client, userdata, msg):
    print("Message received: " + msg.topic)
    if msg.topic == "topic/haldor/checkup":
        print(msg.payload.decode())
        resp = notify('checkup', json.loads(msg.payload.decode()))
        print ("Response: " + resp.read().decode('utf-8'))
        return
    if msg.topic in topics:
        print(msg.topic + ":" + msg.payload.decode())
        return

def get_secret():
    global secret_path
    global secret
    if len(secret) <= 0:
        file = open(secret_path, 'rb')
        secret = file.read()
        file.close
  
    return secret

def notify_hash(body):
    global session
    hasher = hmac.new(get_secret(), body, hashlib.sha256)
    hasher.update(session)
    return hasher.hexdigest()

def notify(path, params):
    global session
    # TODO: Check https certificate
    params['time'] = time.time()
    body = urllib.parse.urlencode(params).encode('utf-8')

    headers = {"Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/plain",
        "X-Haldor": version,
        "X-Session": session,
        "X-Checksum": notify_hash(body)
        }

    conn = http.client.HTTPConnection("frank", None, timeout=60)
    conn.request("POST", "/haldor/{0}".format(path), body, headers)
    print("Notifying {0}: ".format(path), end = '')
    return conn.getresponse()

def notify_bootup():
    global session
    boot_checks = {}

    print("Bootup:")
    
    try:
        boot_checks['uptime'] = subprocess.check_output("uptime")
        boot_checks['uname'] = subprocess.check_output(["uname", "-a"])
    except:
        print("\tuptime/uname read error")
    
    try:
        boot_checks['ifconfig_eth0'] = subprocess.check_output(["/sbin/ifconfig", "eth0"])
    except:
        print("\teth0 read error")
    
    try:
        boot_checks['my_ip'] = subprocess.check_output(["/usr/bin/curl", "-s", "http://whatismyip.akamai.com/"])
    except:
        print("\tmy ip read error")
    
    try:
        boot_checks['local_ip'] = subprocess.check_output(["/home/brandon/haldor/local_ip.sh"])
    except:
        print("\tlocal ip read error")

    resp = notify('bootup', boot_checks)
    session = resp.read()
    print("Bootup Complete: {0}".format(session))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_log = on_log
client.connect("daisy")

client.loop_start()

notify_bootup()

while True:
    time.sleep(3)
    print("Notify Requested.")
    checkups = {}
    client.publish("topic/checkup_req")
