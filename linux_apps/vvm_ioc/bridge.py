
import paho.mqtt.client as mqtt
from epics import caput


def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe("vvm/results/mags")
    client.subscribe("vvm/results/phases")


def getVals(raw):
    return [float(x) for x in raw.split(b',')]


def on_message(client, userdata, msg):
    # print(msg.topic+" "+str(msg.payload))
    if msg.topic == 'vvm/results/mags':
        vals = getVals(msg.payload)
        for val, s in zip(vals, ('Ref', 'A', 'B', 'C')):
            caput('iocvvm:mag{:}'.format(s), val)
            # print('iocvvm:mag{:}'.format(s), val)

    if msg.topic == 'vvm/results/phases':
        vals = getVals(msg.payload)
        for val, s in zip(vals, ('A', 'B', 'C')):
            caput('iocvvm:phase{:}'.format(s), val)
            # print('iocvvm:phase{:}'.format(s), val)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("vvm0.dhcp")

client.loop_forever()
