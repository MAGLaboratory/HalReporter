#!/usr/bin/env python3
import time, json, subprocess, urllib, hmac, hashlib, http, traceback, os
import paho.mqtt.client as mqtt

# store checkups to post as one block of checkups
checkups = {}
session = ''.encode('utf-8')
version = 2020
secret_path = "/home/brandon/haldor/.open-sesame"
secret = ''

data_sources = ['haldor']
checkups = {}

subtopics = ["event", "checkup", "bootup"]

topics = []

boot_check_list = {
    'uptime':["uptime"],
    'uname':["uname", "-a"],
    'ifconfig_eth0':["/sbin/ifconfig", "eth0"],
    'my_ip':["/usr/bin/curl", "-s", "http://whatismyip.akamai.com/"],
    'local_ip':["/home/brandon/haldor/local_ip.sh"]
}

def on_log(client, userdata, level, buff):
    if level != mqtt.MQTT_LOG_DEBUG:
        print (level)
        print(buff)
    if level == mqtt.MQTT_LOG_ERR:
        print ("error handler")
        traceback.print_exc()
        os._exit(1)

def on_connect(client, userdata, flags, rc):
    global topics
    print("MQTT Connected: " + str(rc))
    for data_source in data_sources:
        for subtopic in subtopics:
            topic = data_source + '/' + subtopic
            topics += topic
            client.subscribe(topic)
            print ("Subscribed to " + topic)

def on_message(client, userdata, msg):
    print("Message received: " + msg.topic)
    for source in data_sources:
        if msg.topic == source + '/' + "checkup":
            print(msg.payload.decode())
            checkups[source] = json.loads(msg.payload.decode())
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
   
    for bc_name, bc_cmd in boot_check_list.items():
        boot_checks[bc_name] = subprocess.check_output(bc_cmd)

    resp = notify('bootup', boot_checks)
    session = resp.read()
    print("Bootup Complete: {0}".format(session.decode('utf-8')))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_log = on_log
client.connect("daisy")

client.loop_start()

notify_bootup()

while True:
    checkups = {}
    client.publish("reporter/checkup_req")
    print("Notify Requested.")
    time.sleep(10)
    notify_checkup = {}
    for checkup in checkups.values():
        print (checkup)
        notify_checkup.update(checkup)
    resp = notify('checkup', notify_checkup)
    print ("Response: " + resp.read().decode('utf-8'))
    time.sleep(30)
