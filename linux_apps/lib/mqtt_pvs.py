import logging
import paho.mqtt.client as mqtt

log = logging.getLogger('mqtt_pvs')


class MqttPvs:
    '''
    Helper class for implementing `process variables` over MQTT
    basically settings which have defaults, are user settable
    and which are sanity checked
    values appear as members of this class

    args:
        is a ArgumentParser result and is used to get default settings

    prefix:
        is what the mqtt topic of a setting must start with

    pvs:
        dictionary defining the PVs and their properties

        key is NAME of PV

        value is a list like this:
            [DEFAULT_VALUE, MIN_VALUE, MAX_VALUE, WRITE_TO_HW]

        if DEFAULT_VALUE is None, it is taken from `args.NAME`

        if WRITE_TO_HW is True, write the FPGA CSR register of NAME

        WRITE_TO_HW can also be a conversion function, taking the value as its
        single argument and returning the converted value

        example:
            {
                'fps':          [20.0, 1e-6, 120],
                'vvm_iir':      [None, 0, 13, True],
                'vvm_bla':      [None, 0, 13, lambda x: int(x / 123.4)]
            }
    '''
    def __init__(self, args, prefix, pvs, c=None):
        self.isInit = False
        self.c = c
        self.prefix = prefix
        self.pvs = pvs

        self.mq = mqtt.Client('vvm_daemon', True)
        self.mq.enable_logger(log)

        for k, v in self.pvs.items():
            val = v[0]
            if val is None:
                val = getattr(args, k)

            # Write initial value to local parameter and FPGA register
            self.set_par(k, val)

            # Subscribe to the mqtt topic of <prefix>/<parameter name>
            self.mq.message_callback_add(self.prefix + k, self.on_pv_msg)

        self.mq.on_connect = self.on_connect
        self.mq.connect_async(args.mqtt_server, args.mqtt_port, 60)
        self.mq.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        log.info('MQTT connected %s %s', flags, rc)
        # Publish all current PV values (the startup defaults)
        if self.isInit is False:
            for k in self.pvs:
                client.publish(self.prefix + k, getattr(self, k), 0, True)
            self.isInit = True
        # We need the wildcard subscribe to be able to
        # use message_callback_add() more freely
        client.subscribe(self.prefix + '#')

    def on_pv_msg(self, client, user, m):
        ''' make some members of this class PV settable '''
        k = m.topic.split('/')[-1]
        try:
            val = float(m.payload)
        except ValueError:
            log.warning("%s cannot be set to %s", k, m.payload)
            return
        self.set_par(k, val)

    def set_par(self, par_name, val):
        # Find name in pv dict
        if par_name not in self.pvs:
            log.warning("%s is not a known parameter", par_name)
            return
        pv = self.pvs[par_name]

        # Range check
        if not pv[1] <= val <= pv[2]:
            log.warning("%s cannot be set to %s: out of range", par_name, val)
            return

        # Write value to local member
        setattr(self, par_name, val)

        # Write value to FPGA register
        if self.c is not None and len(pv) >= 4 and pv[3]:

            # convert to raw value if needed
            if callable(pv[3]):
                rawval = pv[3](val)
            else:
                rawval = int(val)

            # Write to hardware
            self.c.write_reg(par_name, rawval)

            log.info("%s = %s (FPGA: %s)", par_name, val, rawval)
            return
        log.info("%s = %s", par_name, val)
