#!/usr/bin/python3
from os import putenv
from socket import gethostname
from datetime import datetime
from random import randint
import pygame as pg
from pygame.draw import *
from evdev import InputDevice, categorize, ecodes

W = (0xFF, 0xFF, 0xFF)
B = (0, 0, 0)


class Obj:
    ''' one movable object '''

    def __init__(self, s):
        self.pos = pg.Rect((randint(-64, xmax), randint(-16, ymax)), (1, 1))
        self.new_s(s)
        self.vx, self.vy = 1, 1

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
        if self.pos.right > xmax:
            self.vx = -1 * abs(self.vx)
        if self.pos.top < 0:
            self.vy = abs(self.vy)
        if self.pos.bottom > ymax:
            self.vy = -1 * abs(self.vy)


class Draw:
    ''' manage all moveable objects '''

    def __init__(self):
        self.objs = [Obj(getRandO()) for i in range(2)]

    def upd(self, i, d):
        d.fill(B)
        for o in self.objs:
            o.move()
            d.blit(o.s, o.pos)
        if i % 300 == 0:
            if randint(0, 1):
                self.objs.insert(0, Obj(getRandO()))
            if len(self.objs) > 2 and (randint(0, 1) or len(self.objs) > 5):
                self.objs.pop(0)
#            for i in range(len(self.objs) - 2):
#                self.objs[i].new_s(getRandO())
            self.objs[-2].new_s(getTxt(datetime.now().strftime("%H:%M")))
            self.objs[-1].new_s(getTxt(gethostname(), 22))

def rCol():
    return (randint(0, 0xFF),) * 3

def getRandO():
    s = pg.Surface((randint(5, 40), randint(5, 30)))
    s.set_colorkey(B)
    if randint(0, 1):
        f = ellipse
    else:
        f = rect
    f(s, rCol(), s.get_rect(), randint(0, 2))
    return s


def getTxt(txt, H=None):
    if H is None:
        H = randint(16, 60)
    return pg.font.Font(None, H).render(txt, False, rCol())


putenv('SDL_NOMOUSE', '')
putenv('SDL_FBDEV', '/dev/fb1')
putenv('SDL_FBACCEL', '0')
putenv('SDL_VIDEODRIVER', 'fbcon')

dev_rot = InputDevice('/dev/input/event0')
dev_push = InputDevice('/dev/input/event1')

pg.display.init()
pg.font.init()
pg.mouse.set_visible(False)
d = pg.display.set_mode()
xmax, ymax = d.get_size()

draw = Draw()

i = 0
pos = 0
while True:
    pg.event.pump()
    for event in pg.event.get():
        if event.type == QUIT:
            pg.quit()
            sys.exit()

    try:
        for evt in dev_rot.read():
            if evt.type == 2:
                pos += evt.value
                print(pos)
                if evt.value > 0:
                    draw.objs.insert(0, Obj(getRandO()))
                elif evt.value < 0 and len(draw.objs) > 2:
                    draw.objs.pop(0)
    except:
        pass

    draw.upd(i, d)
    pg.display.update()

    i += 1
    pg.time.delay(30)
