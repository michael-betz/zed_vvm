#!/usr/bin/python3
from os import putenv
from socket import gethostname
from datetime import datetime
from random import randint
import pygame as pg
from pygame.draw import ellipse, rect
from evdev import InputDevice

W = (0xFF, 0xFF, 0xFF)
B = (0, 0, 0)


class Obj:
    ''' container for one movable object '''
    def __init__(self, xmax, ymax, s=None):
        ''' s = surface with image data '''
        self.xmax, self.ymax = xmax, ymax
        self.pos = pg.Rect((randint(-64, xmax), randint(-16, ymax)), (1, 1))
        if s is None:
            s = Obj.getRandO()
        self.new_s(s)
        self.vx, self.vy = 1, 1

    def getRandO():
        ''' return a surface with a random object '''
        s = pg.Surface((randint(5, 40), randint(5, 30)))
        s.set_colorkey(B)
        if randint(0, 1):
            f = ellipse
        else:
            f = rect
        f(s, rCol(), s.get_rect(), randint(0, 2))
        return s

    def new_s(self, s):
        ''' add a new surface at the same position '''
        self.s = s
        self.pos.width = s.get_width()
        self.pos.height = s.get_height()

    def move(self):
        ''' move by one pixel '''
        self.pos.move_ip(self.vx, self.vy)
        if self.pos.left < 0:
            self.vx = abs(self.vx)
        if self.pos.right > self.xmax:
            self.vx = -1 * abs(self.vx)
        if self.pos.top < 0:
            self.vy = abs(self.vy)
        if self.pos.bottom > self.ymax:
            self.vy = -1 * abs(self.vy)


class Draw:
    ''' manage all movable objects '''
    def __init__(self, d):
        ''' d is the display surface '''
        self.d = d
        self.objs = []
        self.xmax, self.ymax = d.get_size()
        for i in range(2):
            self.addObj()

    def addObj(self):
        self.objs.insert(0, Obj(self.xmax, self.ymax))

    def removeObj(self):
        if len(self.objs) > 2:
            self.objs.pop(0)

    def upd(self, i, d):
        d.fill(B)
        for o in self.objs:
            o.move()
            d.blit(o.s, o.pos)
        if i % 300 == 0:
            if randint(0, 1):
                self.addObj()
            if randint(0, 1) or len(self.objs) > 5:
                self.removeObj()
            self.objs[-2].new_s(getTxt(datetime.now().strftime("%H:%M")))
            self.objs[-1].new_s(getTxt(gethostname(), 22))


def rCol():
    ''' return a random color '''
    return (randint(0, 0xFF),) * 3


def getTxt(txt, H=None):
    ''' return a surface with some text on it '''
    if H is None:
        H = randint(16, 60)
    return pg.font.Font(None, H).render(txt, False, rCol())


def getEncoderDelta():
    ''' returns encoder steps and button pushes '''
    rot = 0
    btn = False
    try:
        for evt in dev_rot.read():
            if evt.type == 2:
                rot += evt.value
    except BlockingIOError:
        pass
    try:
        for evt in dev_push.read():
            btn = evt.value
    except BlockingIOError:
        pass
    return rot, btn


putenv('SDL_NOMOUSE', '')
putenv('SDL_FBDEV', '/dev/fb1')
putenv('SDL_FBACCEL', '0')
putenv('SDL_VIDEODRIVER', 'fbcon')

dev_rot = InputDevice('/dev/input/event0')
dev_push = InputDevice('/dev/input/event1')

pg.display.init()
pg.font.init()
pg.mouse.set_visible(False)
d = pg.display.set_mode()  # returns the display surface

draw = Draw(d)

i = 0
while True:
    pg.event.pump()
    for event in pg.event.get():
        if event.type == pg.QUIT:
            pg.quit()

    rot, btn = getEncoderDelta()
    if rot > 0:
        draw.addObj()
    elif rot < 0:
        draw.removeObj()

    draw.upd(i, d)
    pg.display.update()

    i += 1
    pg.time.delay(30)
