
from collections import namedtuple
import math
import numpy as np

SvgElemement = namedtuple("SvgElement", ['name', 'attr'])

default_palette = "blue red green purple orange limegreen magenta cyan brown black"


class SvgImage():
    def __init__(self, width, height):
        """
        Simple SVG image implementation.
        SVG-Path:
        ---------
          M = moveto
          L = lineto
          H = horizontal lineto
          V = vertical lineto
          C = curveto
          S = smooth curveto
          Q = quadratic Bézier curve
          T = smooth quadratic Bézier curveto
          A = elliptical Arc
          Z = closepath
        """
        self.width = width
        self.height = height
        self.elements = []

    def clear(self):
        self.elements = []

    def add(self, name, **kwargs):
        if 'd' in kwargs:
            d = kwargs['d']
            if type(d) != str:
                d = map(str, d)
                d = " ".join(d)
            kwargs['d'] = d
        self.elements.append(SvgElemement(name, kwargs))

    def render(self):
        first = '<svg width="%s" height="%s">' % (self.width, self.height)
        last = "</svg>"
        middle = []

        for name, attr in self.elements:
            attr = [
                f'{k.replace("_", "-")}="{v}"'
                for k, v in attr.items()
            ]
            line = ['<' + name, *attr, '/>']
            middle.append(" ".join(line))

        lines = [first, *middle, last]

        return "\n".join(lines)

    def save(self, name):
        svg_code = self.render()
        with open(name, 'w') as f:
            f.write(svg_code)

    def _repr_html_(self):
        return self.render()



from itertools import repeat, chain


# Draw LOGO

img_size = 500
img = SvgImage(img_size, img_size)

center = img_size / 2
stroke_width = 50 
outer_radius = img_size / 2
inner_radius = img_size / 4 

img.add("rect", width=img_size, height=img_size)

outer_points = tuple(map(
    lambda α : (outer_radius*math.sin(α) + center, outer_radius*math.cos(α) + center),
    np.linspace(0, 2*math.pi, 6, endpoint=False) - 2*math.pi/12,
))

inner_points = tuple(map(
    lambda α : (inner_radius*math.sin(α) + center, inner_radius*math.cos(α) + center),
    np.linspace(0, 2*math.pi, 6, endpoint=False),
))

host_points = inner_points[::2]
router_points = inner_points[1::2]

# draw outer
#for (x1, y1), (x2, y2) in zip(outer_points, (*outer_points[1:], outer_points[0])):
#    img.add("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke="white")

# draw inner
#for (x1, y1), (x2, y2) in zip(inner_points, (*inner_points[1:], inner_points[0])):
#    img.add("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke="white")

# draw net to host
for x1, y1 in host_points:
    img.add("line", x1=center, y1=center, x2=x1, y2=y1, stroke="white", stroke_width=stroke_width)

# draw host to server
for (x1, y1), (x2, y2) in zip(chain(*map(lambda p: repeat(p, 2), host_points)), outer_points):
    img.add("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke="white", stroke_width=stroke_width)
    

# conncet routers
#for (x1, y1), (x2, y2) in zip(router_points, (*router_points[1:], router_points[0])):
#    img.add("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke="white", stroke_width=stroke_width)

outer_points = tuple(map(
    lambda α : (outer_radius*math.sin(α) + center, outer_radius*math.cos(α) + center),
    np.linspace(0, 2*math.pi, 6, endpoint=False) + 2*math.pi/12,
))

#router to server
#for (x1, y1), (x2, y2) in zip(chain(*map(lambda p: repeat(p, 2), router_points)), outer_points):
#    img.add("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke="white", stroke_width=stroke_width)


#img.add("circle", cx=center, cy=center, fill="black", r=50)

for x, y in outer_points:
    img.add("circle", cx=x, cy=y, fill="black", r=50)

#for x, y in host_points:
#    img.add("circle", cx=x, cy=y, fill="black", r=25)

for x, y in router_points:
    img.add("circle", cx=x, cy=y, fill="black", r=50)

img.save("logo.svg")
