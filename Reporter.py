#!/usr/bin/env python3
import paho.mqtt.client as mqtt

topics = ["topic/haldor/event", "topic/haldor/checkup", "topic/haldor/bootup"]

def on_connect(client, userdata, flags, rc):
    print("MQTT Connected: " + str(rc))
    for topic in topics:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    if msg.topic in topics:
        print(msg.topic.decode() + ":" + msg.payload.decode())

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("daisy")

client.loop_start()

while True:
    time.sleep(3)
    print("Notify Requested.")
    clinet.publish("topic/checkup_req")
