import math
import random
import time
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QBrush, QPen, QPainter, QPainterPath, QLinearGradient, QRadialGradient

# (day top, day bottom, night top, night bottom)
SKY = {
    "clear":    ((250, 190, 60), (226, 98, 30),   (10, 14, 40),  (32, 28, 80)),
    "partly":   ((62, 128, 210), (124, 172, 228), (18, 26, 58),  (42, 48, 92)),
    "overcast": ((112, 120, 132), (72, 78, 90),   (40, 44, 54),  (22, 25, 33)),
    "fog":      ((152, 160, 168), (112, 120, 128), (50, 56, 64), (30, 34, 40)),
    "drizzle":  ((86, 100, 118), (52, 62, 78),    (30, 38, 54),  (16, 20, 30)),
    "rain":     ((70, 84, 102),  (38, 48, 64),    (26, 32, 46),  (12, 16, 26)),
    "snow":     ((142, 162, 188), (96, 116, 146), (40, 52, 78),  (22, 30, 50)),
    "storm":    ((40, 38, 64),   (16, 16, 30),    (30, 28, 52),  (10, 10, 22)),
}

# (cloud count, cloud alpha, day tint, night tint, drift speed)
CLOUDS = {
    "clear":    (0, 0.0, (255, 255, 255), (150, 160, 200), 0.0),
    "partly":   (4, 0.55, (255, 255, 255), (120, 130, 170), 0.012),
    "overcast": (7, 0.60, (176, 181, 191), (92, 98, 114), 0.010),
    "fog":      (3, 0.25, (210, 214, 220), (110, 116, 126), 0.008),
    "drizzle":  (6, 0.55, (126, 134, 148), (70, 76, 92), 0.014),
    "rain":     (7, 0.65, (98, 106, 122), (56, 62, 80), 0.016),
    "snow":     (6, 0.50, (196, 206, 220), (110, 122, 150), 0.008),
    "storm":    (8, 0.78, (60, 56, 82), (46, 44, 68), 0.022),
}

RAIN_INTENSITY = {51: 0.3, 53: 0.4, 55: 0.55, 56: 0.4, 57: 0.55, 61: 0.5, 80: 0.5, 63: 0.8, 81: 0.8, 66: 0.8,
                  65: 1.0, 82: 1.0, 67: 1.0, 95: 0.9, 96: 1.0, 99: 1.0}


def classify(code):
    if code in (0, 1): return "clear"
    if code == 2: return "partly"
    if code in (45, 48): return "fog"
    if code in (51, 53, 55, 56, 57): return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "rain"
    if code in (71, 73, 75, 77, 85, 86): return "snow"
    if code in (95, 96, 99): return "storm"
    return "overcast"


def _mix(a, b, k):
    return QColor(int(a.red() + (b.red() - a.red()) * k), int(a.green() + (b.green() - a.green()) * k),
                  int(a.blue() + (b.blue() - a.blue()) * k))


def _rgb(t, a=255):
    return QColor(t[0], t[1], t[2], a)


class WeatherScene:
    def __init__(self):
        self.kind = None
        self.is_day = True
        self.intensity = 0.7
        self.top = QColor(20, 40, 100)
        self.bottom = QColor(10, 20, 60)
        self.t = 0.0
        self.last = time.perf_counter()
        self.clouds = []
        self.rain = []
        self.snow = []
        self.splashes = []
        self.stars = [(random.random(), random.random() * 0.8, random.random() * 6.28, 0.5 + random.random()) for _ in range(46)]
        self.bolt = None
        self.bolt_age = 0.0
        self.next_bolt = 2.0
        self.shooting = None
        self.next_shoot = 5.0

    def set_condition(self, code, is_day):
        kind = classify(code)
        self.intensity = RAIN_INTENSITY.get(code, 0.7)
        first = self.kind is None
        self.kind, self.is_day = kind, bool(is_day)
        sky = SKY[kind]
        tt, tb = (sky[0], sky[1]) if self.is_day else (sky[2], sky[3])
        self.target_top, self.target_bottom = _rgb(tt), _rgb(tb)
        if first:
            self.top, self.bottom = QColor(self.target_top), QColor(self.target_bottom)
        n_cl = CLOUDS[kind][0]
        while len(self.clouds) < n_cl: self.clouds.append(self._new_cloud(True))
        del self.clouds[n_cl:]
        n_rain = int(34 + 110 * self.intensity) if kind in ("rain", "drizzle", "storm") else 0
        while len(self.rain) < n_rain: self.rain.append(self._new_drop(True))
        del self.rain[n_rain:]
        n_snow = 70 if kind == "snow" else 0
        while len(self.snow) < n_snow: self.snow.append([random.random(), random.random(), 0.05 + random.random() * 0.12,
                                                         0.8 + random.random() * 1.8, random.random() * 6.28])
        del self.snow[n_snow:]
        self.next_bolt = 1.2

    def _new_cloud(self, anywhere):
        lobes = [(random.uniform(-1.3, 1.3), random.uniform(-0.25, 0.2), random.uniform(0.55, 1.0)) for _ in range(5)]
        return {"x": random.uniform(-0.3, 1.2) if anywhere else -0.5, "y": random.uniform(0.0, 0.55),
                "s": random.uniform(0.55, 1.1), "a": random.uniform(0.6, 1.0), "v": random.uniform(0.6, 1.4), "lobes": lobes}

    def _new_drop(self, anywhere):
        return [random.random(), random.random() if anywhere else -random.random() * 0.3,
                random.uniform(1.3, 2.3), random.uniform(0.07, 0.16), random.uniform(0.35, 1.0)]

    def _make_bolt(self):
        x, y = random.uniform(0.2, 0.8), 0.12
        pts = [(x, y)]
        while y < 0.78:
            y += random.uniform(0.06, 0.13)
            x += random.uniform(-0.07, 0.07)
            pts.append((x, y))
        bi = random.randint(1, max(1, len(pts) - 3))
        bx, by = pts[bi]
        branch = [(bx, by)]
        for _ in range(3):
            by += random.uniform(0.05, 0.1)
            bx += random.uniform(0.02, 0.09) * random.choice((-1, 1))
            branch.append((bx, by))
        self.bolt = (pts, branch)
        self.bolt_age = 0.0

    def _flash(self):
        if self.bolt is None: return 0.0
        a = self.bolt_age
        first = math.exp(-a * 9.0)
        second = 0.8 * math.exp(-(a - 0.14) * 7.0) if a > 0.14 else 0.0
        return max(first, second)

    def _step(self, dt, rect):
        self.t += dt
        k = min(1.0, dt * 2.5)
        self.top = _mix(self.top, self.target_top, k)
        self.bottom = _mix(self.bottom, self.target_bottom, k)
        speed = CLOUDS[self.kind][4]
        for c in self.clouds:
            c["x"] += speed * c["v"] * dt
            if c["x"] > 1.5: c.update(self._new_cloud(False))
        h_over_w = rect.height() / max(1, rect.width())
        for d in self.rain:
            d[1] += d[2] * dt
            d[0] -= 0.22 * d[2] * dt * h_over_w
            if d[1] > 1.0:
                if len(self.splashes) < 28 and random.random() < 0.45: self.splashes.append([d[0], 0.0])
                d[:] = self._new_drop(False)
                d[1] = -random.random() * 0.1
            if d[0] < -0.05: d[0] += 1.1
        for s in self.splashes: s[1] += dt * 3.2
        self.splashes = [s for s in self.splashes if s[1] < 1.0]
        for f in self.snow:
            f[1] += f[2] * dt
            f[4] += dt * 1.4
            if f[1] > 1.05: f[1] = -0.05; f[0] = random.random()
        if self.kind == "storm":
            if self.bolt is not None:
                self.bolt_age += dt
                if self.bolt_age > 0.7: self.bolt = None
            self.next_bolt -= dt
            if self.next_bolt <= 0:
                self._make_bolt()
                self.next_bolt = random.uniform(1.8, 4.5) if self.intensity >= 1.0 else random.uniform(3.0, 6.5)
        if self.kind == "clear" and not self.is_day:
            if self.shooting is not None:
                self.shooting[2] += dt * 1.6
                if self.shooting[2] > 1.0: self.shooting = None
            self.next_shoot -= dt
            if self.next_shoot <= 0:
                self.shooting = [random.uniform(0.3, 0.9), random.uniform(0.05, 0.3), 0.0]
                self.next_shoot = random.uniform(6.0, 14.0)

    def paint(self, painter, rect, clip_path, opacity):
        now = time.perf_counter()
        dt = min(0.05, now - self.last); self.last = now
        self._step(dt, rect)
        x0, y0, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        kind, day, t = self.kind, self.is_day, self.t
        flash = self._flash() if kind == "storm" else 0.0

        painter.save()
        painter.setOpacity(opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        grad = QLinearGradient(x0, y0, x0, y0 + h)
        grad.setColorAt(0, self.top); grad.setColorAt(1, self.bottom)
        painter.fillPath(clip_path, QBrush(grad))
        painter.setClipPath(clip_path)

        if kind in ("clear", "partly") and day: self._sun(painter, x0, y0, w, h, kind)
        if kind in ("clear", "partly") and not day: self._night(painter, x0, y0, w, h, kind)
        self._clouds(painter, x0, y0, w, h)
        if kind == "fog": self._fog(painter, x0, y0, w, h)
        if self.rain: self._rain(painter, x0, y0, w, h)
        if self.snow: self._snow(painter, x0, y0, w, h)
        if kind == "storm" and self.bolt is not None: self._lightning(painter, x0, y0, w, h, flash)
        if kind == "clear" and day: self._sun_bloom(painter, x0, y0, w, h)

        vig = QRadialGradient(QPointF(x0 + w / 2, y0 + h / 2), w * 0.62)
        vig.setColorAt(0.55, QColor(0, 0, 0, 0)); vig.setColorAt(1, QColor(0, 0, 0, 70))
        painter.setBrush(QBrush(vig)); painter.drawRect(QRectF(x0, y0, w, h))
        painter.restore()

    def _sun(self, p, x0, y0, w, h, kind):
        cx, cy = x0 + w * 0.82, y0 + h * 0.3
        pulse = 1.0 + 0.04 * math.sin(self.t * 1.3)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        glow = QRadialGradient(QPointF(cx, cy), h * 1.15 * pulse)
        warm = QColor(255, 236, 150, 210 if kind == "clear" else 150)
        glow.setColorAt(0, warm); glow.setColorAt(0.25, QColor(255, 190, 80, 110 if kind == "clear" else 70)); glow.setColorAt(1, QColor(255, 150, 40, 0))
        p.setBrush(QBrush(glow)); p.drawRect(QRectF(x0, y0, w, h))
        ang = self.t * 0.18
        for i in range(14):
            a = ang + i * (2 * math.pi / 14)
            r0, r1 = h * 0.22, h * (0.95 if i % 2 else 0.7)
            ray = QLinearGradient(QPointF(cx + math.cos(a) * r0, cy + math.sin(a) * r0), QPointF(cx + math.cos(a) * r1, cy + math.sin(a) * r1))
            ray.setColorAt(0, QColor(255, 244, 190, 70 if kind == "clear" else 40)); ray.setColorAt(1, QColor(255, 220, 120, 0))
            p.setPen(QPen(QBrush(ray), 4.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(cx + math.cos(a) * r0, cy + math.sin(a) * r0), QPointF(cx + math.cos(a) * r1, cy + math.sin(a) * r1))
        p.setPen(Qt.PenStyle.NoPen)
        core = QRadialGradient(QPointF(cx, cy), h * 0.2)
        core.setColorAt(0, QColor(255, 255, 240, 255)); core.setColorAt(0.7, QColor(255, 236, 160, 235)); core.setColorAt(1, QColor(255, 210, 110, 0))
        p.setBrush(QBrush(core)); p.drawEllipse(QPointF(cx, cy), h * 0.2, h * 0.2)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def _sun_bloom(self, p, x0, y0, w, h):
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for i in range(3):
            a = self.t * 0.25 + i * 2.1
            bx, by = x0 + w * (0.5 + 0.38 * math.sin(a)), y0 + h * (0.55 + 0.3 * math.cos(a * 0.8))
            g = QRadialGradient(QPointF(bx, by), w * 0.28)
            g.setColorAt(0, QColor(255, 170, 60, 38)); g.setColorAt(1, QColor(255, 140, 40, 0))
            p.setBrush(QBrush(g)); p.drawRect(QRectF(x0, y0, w, h))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    def _night(self, p, x0, y0, w, h, kind):
        mult = 1.0 if kind == "clear" else 0.5
        for sx, sy, ph, sz in self.stars:
            a = int(255 * mult * (0.35 + 0.65 * (0.5 + 0.5 * math.sin(self.t * 1.7 + ph))))
            p.setBrush(QColor(255, 255, 255, a)); r = 0.6 + sz * 0.6
            p.drawEllipse(QPointF(x0 + sx * w, y0 + sy * h), r, r)
        if self.shooting is not None:
            sx, sy, k = self.shooting
            hx, hy = x0 + (sx - k * 0.35) * w, y0 + (sy + k * 0.35) * h
            tail = QLinearGradient(QPointF(hx, hy), QPointF(hx + w * 0.14, hy - h * 0.14))
            fade = math.sin(k * math.pi)
            tail.setColorAt(0, QColor(255, 255, 255, int(230 * fade))); tail.setColorAt(1, QColor(255, 255, 255, 0))
            p.setPen(QPen(QBrush(tail), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(hx, hy), QPointF(hx + w * 0.14, hy - h * 0.14)); p.setPen(Qt.PenStyle.NoPen)
        cx, cy, r = x0 + w * 0.84, y0 + h * 0.3, h * 0.17
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        halo = QRadialGradient(QPointF(cx, cy), h * 0.85)
        halo.setColorAt(0, QColor(170, 190, 255, int(90 * mult + 20))); halo.setColorAt(1, QColor(120, 140, 220, 0))
        p.setBrush(QBrush(halo)); p.drawRect(QRectF(x0, y0, w, h))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        moon = QPainterPath(); moon.addEllipse(QPointF(cx, cy), r, r)
        cut = QPainterPath(); cut.addEllipse(QPointF(cx + r * 0.5, cy - r * 0.25), r * 0.88, r * 0.88)
        p.setBrush(QColor(236, 240, 255, 245)); p.drawPath(moon.subtracted(cut))

    def _clouds(self, p, x0, y0, w, h):
        n, alpha, dtint, ntint, _ = CLOUDS[self.kind]
        if not self.clouds: return
        tint = dtint if self.is_day else ntint
        for c in self.clouds:
            base = h * 0.42 * c["s"]
            for lx, ly, lr in c["lobes"]:
                cx = x0 + (c["x"] * w) + lx * base
                cy = y0 + c["y"] * h + h * 0.08 + ly * base + math.sin(self.t * 0.4 + lx) * 1.5
                r = base * lr
                g = QRadialGradient(QPointF(cx, cy), r)
                a = int(255 * alpha * c["a"])
                g.setColorAt(0, QColor(tint[0], tint[1], tint[2], a))
                g.setColorAt(0.55, QColor(tint[0], tint[1], tint[2], int(a * 0.55)))
                g.setColorAt(1, QColor(tint[0], tint[1], tint[2], 0))
                p.setBrush(QBrush(g)); p.drawEllipse(QPointF(cx, cy), r, r * 0.8)

    def _fog(self, p, x0, y0, w, h):
        for i in range(5):
            cx = x0 + w * (0.5 + 0.35 * math.sin(self.t * 0.12 + i * 1.7))
            cy = y0 + h * (0.15 + i * 0.2)
            p.save(); p.translate(cx, cy); p.scale(1.0, 0.22)
            g = QRadialGradient(QPointF(0, 0), w * 0.55)
            col = 235 if self.is_day else 130
            g.setColorAt(0, QColor(col, col, col + 5, 120)); g.setColorAt(1, QColor(col, col, col, 0))
            p.setBrush(QBrush(g)); p.drawEllipse(QPointF(0, 0), w * 0.55, w * 0.55)
            p.restore()

    def _rain(self, p, x0, y0, w, h):
        storm = self.kind == "storm"
        base = QColor(190, 210, 245) if self.is_day or storm else QColor(150, 175, 225)
        for d in self.rain:
            x, y = x0 + d[0] * w, y0 + d[1] * h
            ln = d[3] * h
            c = QColor(base); c.setAlpha(int(150 * d[4] * (0.7 + 0.3 * self.intensity)))
            p.setPen(QPen(c, 1.0 + d[4] * 0.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(x, y), QPointF(x + ln * 0.22, y - ln))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for sx, k in self.splashes:
            c = QColor(base); c.setAlpha(int(110 * (1 - k)))
            p.setPen(QPen(c, 1.0))
            r = 2 + 7 * k
            p.drawEllipse(QPointF(x0 + sx * w, y0 + h - 2), r, r * 0.3)
        p.setPen(Qt.PenStyle.NoPen)

    def _snow(self, p, x0, y0, w, h):
        for f in self.snow:
            x = x0 + (f[0] + math.sin(f[4]) * 0.015) * w
            y = y0 + f[1] * h
            r = f[3]
            g = QRadialGradient(QPointF(x, y), r * 1.8)
            g.setColorAt(0, QColor(255, 255, 255, 235)); g.setColorAt(0.5, QColor(255, 255, 255, 120)); g.setColorAt(1, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g)); p.drawEllipse(QPointF(x, y), r * 1.8, r * 1.8)

    def _lightning(self, p, x0, y0, w, h, flash):
        pts, branch = self.bolt
        a = self.bolt_age
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        glow = QRadialGradient(QPointF(x0 + pts[0][0] * w, y0 + h * 0.2), w * 0.7)
        glow.setColorAt(0, QColor(200, 190, 255, int(150 * flash))); glow.setColorAt(1, QColor(120, 110, 220, 0))
        p.setBrush(QBrush(glow)); p.drawRect(QRectF(x0, y0, w, h))
        p.setBrush(QColor(190, 200, 255, int(70 * flash))); p.drawRect(QRectF(x0, y0, w, h))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        if a < 0.09 or 0.14 < a < 0.3:
            for seg, wd in ((pts, 1.0), (branch, 0.6)):
                path = QPainterPath(QPointF(x0 + seg[0][0] * w, y0 + seg[0][1] * h))
                for sx, sy in seg[1:]: path.lineTo(QPointF(x0 + sx * w, y0 + sy * h))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(QColor(170, 160, 255, 70), 7 * wd, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)); p.drawPath(path)
                p.setPen(QPen(QColor(220, 225, 255, 150), 3 * wd, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)); p.drawPath(path)
                p.setPen(QPen(QColor(255, 255, 255, 255), 1.4 * wd, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)); p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
