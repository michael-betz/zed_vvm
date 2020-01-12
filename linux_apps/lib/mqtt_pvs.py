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

        if WRITE_TO_HW is True, write the FPGA CSR register of same NAME

        example:
            {
                'fps':          [20.0, 1e-6, 120],
                'vvm_iir':      [None, 0, 13, True],
            }
    '''
    def __init__(self, args, prefix, pvs, c=None):
        self.c = c
        self.prefix = prefix
        self.pvs = pvs

        self.mq = mqtt.Client('vvm_daemon', True)
        self.mq.enable_logger(log)
        self.mq.on_connect = self.on_connect
        self.mq.connect_async(args.mqtt_server, args.mqtt_port, 60)
        self.mq.loop_start()

        for k, v in self.pvs.items():
            if v[0] is None:
                v[0] = getattr(args, k)
            setattr(self, k, v[0])
            # Write initial settings to FPGA register
            if c is not None and len(v) >= 4 and v[3]:
                c.write_reg(k, v[0])
            self.mq.message_callback_add(self.prefix + k, self.on_pv_msg)

    def on_connect(self, client, userdata, flags, rc):
        log.info('MQTT connected %s %s', flags, rc)
        # Publish all current PV values (which are defaults at startup)
        for k in self.pvs:
            client.publish(self.prefix + k, getattr(self, k))
        client.subscribe(self.prefix + '#')

    def on_pv_msg(self, client, user, m):
        ''' make some members of this class PV settable '''
        k = m.topic.split('/')[-1]
        if k not in self.pvs:
            return
        pv = self.pvs[k]
        t = type(pv[0])
        if t in (float, int):
            try:
                val = t(m.payload)
                if not pv[1] <= val <= pv[2]:
                    raise ValueError("out of range")
            except ValueError:
                log.warning("%s cannot be set to %s", k, m.payload)
                return
            setattr(self, k, val)
            # Write value to FPGA register
            reg_write = False
            if self.c is not None and len(pv) >= 4 and pv[3] and t is int:
                self.c.write_reg(k, val)
                reg_write = True
            log.info("%s = %s (FPGA: %s)", k, val, reg_write)
