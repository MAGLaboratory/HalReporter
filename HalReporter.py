#!/usr/bin/env python3
import time, json, subprocess, urllib, hmac, hashlib, http, traceback, os
import paho.mqtt.client as mqtt
from daemon import Daemon
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from typing import *

# store checkups to post as one block of checkups
class HRDaemon(Daemon):
    def run(self):
        h_reporter = HR()
        my_path = os.path.dirname(os.path.abspath(__file__))
        config = open(my_path + "/hr_config.json", "r")
        h_reporter.data = HR.data.from_json(config.read())
        config.close()

        h_reporter.run()

class HR(mqtt.Client):

    @dataclass_json
    @dataclass
    class data:
        pidfile: str
        secret_path: str
        data_sources: List[str]
        subtopics: List[str]
        boot_check_list: Dict[str, List[str]]

    checkups = {}
    session = ''.encode('utf-8')
    version = 2020
    secret = ''
    topics = []
    
    def on_log(self, client, userdata, level, buff):
        if level != mqtt.MQTT_LOG_DEBUG:
            print (level)
            print(buff)
        if level == mqtt.MQTT_LOG_ERR:
            print ("error handler")
            traceback.print_exc()
            os._exit(1)
    
    def on_connect(self, client, userdata, flags, rc):
        print("MQTT Connected: " + str(rc))
        for data_source in self.data.data_sources:
            for subtopic in self.data.subtopics:
                topic = data_source + '/' + subtopic
                self.topics += topic
                client.subscribe(topic)
                print ("Subscribed to " + topic)
    
    def on_message(self, client, userdata, msg):
        print("Message received: " + msg.topic)
        for source in self.data.data_sources:
            if msg.topic == source + '/' + "checkup":
                self.checkups[source] = json.loads(msg.payload.decode())
                return
        if msg.topic in self.topics:
            print(msg.topic + ":" + msg.payload.decode())
            return
    
    def get_secret(self):
        if len(self.secret) <= 0:
            my_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), self.data.secret_path))
            file = open(my_path, 'rb')
            self.secret = file.read()
            file.close
      
        return self.secret
    
    def notify_hash(self, body):
        hasher = hmac.new(self.get_secret(), body, hashlib.sha256)
        hasher.update(self.session)
        return hasher.hexdigest()
    
    def notify(self, path, params):
        # TODO: Check https certificate
        print (params)
        params['time'] = time.time()
        body = urllib.parse.urlencode(params).encode('utf-8')
    
        headers = {"Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/plain",
            "X-Haldor": self.version,
            "X-Session": self.session,
            "X-Checksum": self.notify_hash(body)
            }
    
        conn = http.client.HTTPConnection("frank", None, timeout=60)
        conn.request("POST", "/haldor/{0}".format(path), body, headers)
        print("Notifying {0}: ".format(path), end = '')
        return conn.getresponse()
    
    def notify_bootup(self):
        boot_checks = {}
    
        print("Bootup:")
       
        for bc_name, bc_cmd in self.data.boot_check_list.items():
            boot_checks[bc_name] = subprocess.check_output(bc_cmd, shell=True)
    
        resp = self.notify('bootup', boot_checks)
        self.session = resp.read()
        print("Bootup Complete: {0}".format(self.session.decode('utf-8')))

    def run(self):
        self.connect("daisy")
        
        self.loop_start()
        
        self.notify_bootup()
        
        while True:
            self.checkups = {}
            self.publish("reporter/checkup_req")
            print("Notify Requested.")
            time.sleep(10)
            self.notify_checkup = {}
            for checkup in self.checkups.values():
                print (checkup)
                self.notify_checkup.update(checkup)
            resp = self.notify('checkup', self.notify_checkup)
            print ("Response: " + resp.read().decode('utf-8'))
            time.sleep(30)
