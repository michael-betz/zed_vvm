#!/usr/bin/python3
from os import putenv
from socket import gethostname
from datetime import datetime
from random import randint, choice, random
import pygame as pg
from pygame.draw import ellipse, rect
from glob import glob


W = (0xFF, 0xFF, 0xFF)
B = (0, 0, 0)


def rCol():
    ''' return a random color '''
    return (randint(0, 0xFF),) * 3


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


class Widget:
    def __init__(self, s=None):
        if s is None:
            s = getRandO()
        self.s = s
        self.pos = pg.Rect((0, 0), (s.get_width(), s.get_height()))

    def draw(self):
        return self.s


class TextWidget(Widget):
    def __init__(self, txt='-125.4', fnt=None):
        if fnt is None:
            fnt = pg.font.Font('fonts/UbuntuMono-Regular.ttf', 24)
        self.fnt = fnt
        self.txt = txt
        s = fnt.render(self.txt, True, W)
        super().__init__(s)

    def draw(self):
        return self.fnt.render('{:>6.1f}'.format(
            (random() - 0.5) * 360
        ), True, W)


class DoubleTextWidget(TextWidget):
    def __init__(self):
        super().__init__()
        self.pos.h *= 2
        self.s = pg.Surface((self.pos.w, self.pos.h))

    def draw(self):
        self.s.fill(B)
        l1 = self.fnt.render('{:>6.1f}'.format(
            (random() - 0.5) * 360
        ), True, W)
        l2 = self.fnt.render('❗', True, W)
        self.s.blit(l1, (0, 0))
        self.s.blit(l2, (0, self.pos.h // 2))
        return self.s


class Line:
    ''' Horizontal line of widgets '''
    def __init__(self, xmax):
        self.xmax = xmax
        self.ymax = 0
        self.widgets = []

    def add(self, widget):
        self.widgets.append(widget)

        if widget.pos.height > self.ymax:
            self.ymax = widget.pos.height

        wSize = 0
        for w in self.widgets:
            wSize += w.pos.width
        self.padding = max((self.xmax - wSize) / (len(self.widgets) + 1), 0)
        self.reposition()

    def reposition(self):
        curLeft = 0
        for w in self.widgets:
            w.pos.left = curLeft + self.padding
            curLeft = w.pos.right
            w.pos.centery = self.ymax // 2

    def draw(self):
        s = pg.Surface((self.xmax, self.ymax))
        s.fill(B)
        for i, w in enumerate(self.widgets):
            s.blit(w.draw(), w.pos)
        return s


class Draw:
    ''' manage all movable objects '''
    def __init__(self, d):
        ''' d is the display surface '''
        self.d = d
        self.xmax, self.ymax = d.get_size()
        self.line = Line(256)
        self.line.add(TextWidget())
        self.line.add(Widget())
        self.line.add(DoubleTextWidget())

    def upd(self, i, d):
        d.fill(B)
        d.blit(self.line.draw(), (0, 0))


pg.display.init()
pg.font.init()
pg.mouse.set_visible(False)
d = pg.display.set_mode((256, 64))  # returns the display surface

fntNames = glob('fonts/*.ttf')
fntSizes = (16, 28)
fnts = [pg.font.Font(n, s) for n, s in zip(fntNames, fntSizes)]

draw = Draw(d)

i = 0
while True:
    pg.event.pump()
    for event in pg.event.get():
        if event.type == pg.QUIT:
            pg.quit()

    draw.upd(i, d)
    pg.display.update()

    i += 1
    pg.time.delay(30)
