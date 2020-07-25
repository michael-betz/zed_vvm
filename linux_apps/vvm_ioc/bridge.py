import time
import paho.mqtt.client as mqtt
from epics import caput, caget

LOOP_DT = 1000
PV_PREFIX = 'GTL:VVM1:'
N_AVG = 5


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
            caput(PV_PREFIX + 'mag{:}'.format(s), val)

    if msg.topic == 'vvm/results/phases':
        vals = getVals(msg.payload)
        for val, s in zip(vals, ('A', 'B', 'C')):
            caput(PV_PREFIX + 'phase{:}'.format(s), val)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("vvm0.dhcp")
client.loop_start()

meas = []
phase_sp = 0
int_err = 0
while True:
    isEnabled = caget(PV_PREFIX + 'phaseLock')

    meas.append(caget(PV_PREFIX + 'phaseA'))
    if len(meas) > N_AVG:
        meas.pop(0)
    avg_meas = sum(meas) / len(meas)

    if isEnabled:
        err = avg_meas - phase_sp
        int_err += err
        if int_err > 10:
            int_err = 10
        if int_err < -10:
            int_err = -10
        print(phase_sp, avg_meas, err, int_err)
    else:
        phase_sp = avg_meas

    time.sleep(LOOP_DT - time.time() % LOOP_DT)
