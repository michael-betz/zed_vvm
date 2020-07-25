import time
import paho.mqtt.client as mqtt
from epics import caput, caget

PV_PREFIX = 'GTL:VVM1:'

# drift compensation loop
LOOP_DT = 1.5  # loop period [s]
N_AVG = 30  # running average over the last N meas.
E_MAX = 0.25  # maximum error delta per step
I_GAIN = -0.01  # integral loop gain, keep below 0.1
PV_MEAS = PV_PREFIX + 'phaseB'
PV_SET = 'GTL_____SHB2_PHAC00'


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
while True:
    isEnabled = caget(PV_PREFIX + 'phaseLock')

    meas.append(caget(PV_MEAS))
    if len(meas) > N_AVG:
        meas.pop(0)
    avg_meas = sum(meas) / len(meas)

    if isEnabled:
        err_val = avg_meas - phase_sp
        if err_val > E_MAX:
            err_val = E_MAX
        if err_val < -E_MAX:
            err_val = -E_MAX

        c_val = caget(PV_SET)
        c_val -= I_GAIN * err_val
        caput(PV_SET, c_val)

        print(
            '{:9.3f} {:9.3f} {:9.3f}'.format(
                phase_sp, err_val, c_val
            )
        )
    else:
        phase_sp = avg_meas

    time.sleep(LOOP_DT - time.time() % LOOP_DT)

