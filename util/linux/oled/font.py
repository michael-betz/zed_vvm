'''
Angelfont (.fnt) rendering for pygame
Taken from https://github.com/sseemayer/PyHiero
'''

import re
import os.path
import pygame


class HieroFont(object):
    """Class for a Hiero-generated bitmap font"""

    # quote-aware splitting and unquoting using RE_SPLIT.findall
    RE_SPLIT = re.compile(r"\S+='.*?'|\S+=\".*?\"|\S+")
    RE_UNQUOTE = re.compile(r"'(.*?)'|\"(.*?)\"|(\S+)")

    def __init__(self, font_file):
        self.info = {}
        self.common = {}

        self.pages = {}
        self.chars = {}

        self.filename = font_file
        self.basedir = os.path.dirname(font_file)

        charProps = [
            "id", "x", "y", "width", "height", "xadvance", "xoffset", "yoffset"
        ]

        with open(font_file) as f:
            for line in f:
                # quote-aware split of line, then unquote all matches
                ll = ["".join(m) for m in HieroFont.RE_SPLIT.findall(line)]
                command = ll[0]
                ll = ll[1:]
                vals = {k: ["".join(m) for m in HieroFont.RE_UNQUOTE.findall(v)][0] for k, v in (elem.split("=") for elem in ll)}
                if command == "info":
                    self.info = vals
                elif command == "common":
                    self.common = vals
                elif command == "page":
                    self.pages[vals['id']] = self._get_page(
                        vals['id'], vals['file']
                    )
                elif command == "chars":
                    pass
                elif command == "char":
                    for k in charProps:
                        vals[k] = int(vals[k])

                    self.chars[chr(vals['id'])] = vals
                else:
                    raise Exception("Unknown command: {0}".format(command))

    def _get_page(self, id, file, basedir):
        return file

    def get_alphabet(self):
        return sorted(self.chars.keys())


class PyGameHieroFont(HieroFont):
    def _get_page(self, id, file):
        return pygame.transform.flip(
            pygame.image.load(os.path.join(self.basedir, file)),
            False,
            True
        )

    def render(self, text, antialias=True, color=(255, 255, 255), background=None):
        if not text:
            return None

        ci = [self.chars[character] for character in text]

        width = sum(c['xadvance'] for c in ci) + ci[-1]['xoffset']
        height = max(c['height'] + c['yoffset'] for c in ci)

        surf = pygame.Surface((width, height), flags=pygame.SRCALPHA)

        x = 0

        for c in ci:
            page = self.pages[c['page']]
            w, h = c['width'], c['height']
            sx, sy = c['x'], c['y']
            xofs = c['xoffset']
            yofs = c['yoffset']

            surf.blit(page, (x + xofs, yofs, w, h), (sx, sy, w, h))

            x = x + c['xadvance']

        surf.fill(color, special_flags=pygame.BLEND_RGBA_MULT)

        if(background):
            newsurf = pygame.Surface((width, height), flags=pygame.SRCALPHA)
            newsurf.fill(background)
            newsurf.blit(surf, (0, 0))
            surf = newsurf

        return surf
