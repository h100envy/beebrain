"""
the 3d video: a pool travels through the point cloud brain, lobe by lobe, and the motor
lights PASS, WATCH or SKIP. 24 s at 1920x1080, 30 fps, h264 via ffmpeg.

  python render/video.py [out.mp4]          full render, default build/beebrain-3d.mp4
  PREVIEW=3,7.5 python render/video.py      only these seconds, as pngs in build/preview/
  RANGE=0,120 python render/video.py        only this frame range

the pools on screen are scripted for the video, not scored by the engine. the header says so.
idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cloud as B

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

W, H, FPS = 1920, 1080, 30
DUR = 24.0
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "beebrain-3d.mp4")
PREVIEW = os.environ.get("PREVIEW")          # render only listed seconds as pngs

FONT = os.path.join(ROOT, "brand", "fonts") + os.sep
def grotesk(size, weight="Bold"):
    f = ImageFont.truetype(FONT + "SpaceGrotesk.ttf", size)
    try: f.set_variation_by_name(weight)
    except Exception: pass
    return f
def mono(size, bold=False):
    f = ImageFont.truetype(FONT + "JetBrainsMono.ttf", size)
    try: f.set_variation_by_name("Bold" if bold else "Regular")
    except Exception: pass
    return f

PINK = (255, 79, 163); PINKH = (255, 175, 215); GREY = (120, 124, 140); DIMC = (60, 62, 74); BONE = (240, 236, 222)
GREEN = (63, 224, 138); RED = (255, 84, 104); ORANGE = (255, 176, 74); LIME = (204, 255, 60)
VCOL = {"PASS": GREEN, "SKIP": RED, "WATCH": ORANGE}

brain = B.Brain()
rng = np.random.default_rng(3)
N = len(brain.P)
TARGET = brain.P.copy()
START = rng.normal(size=(N, 3)); START /= np.linalg.norm(START, axis=1, keepdims=True)
START *= rng.uniform(1.4, 2.6, size=(N, 1))
DELAY = rng.random(N) * 0.9

T0, STEP = 3.0, 2.35
N_SHOW = 7

# the pools on screen come from the engine: a real run, a window of seven consecutive pools
sys.path.insert(0, ROOT)
from beebrain.brain import FEATS, N_KC  # noqa: E402
from beebrain.engine import Engine  # noqa: E402

SEED = int(os.environ.get("SEED", 5))
START = int(os.environ.get("START_POOL", 120))


def reason(p, t):
    L = t["lobes"]
    if p.obs["bundle"] > 0.5:
        return "bundle in the create block"
    if t["explore"]:
        return "explore entry, small size"
    if t["verdict"] == "PASS":
        if t["flag"]:
            return "pass with a flag, antennal %.2f" % L["antennal"]
        return "lobes agree" if t["consensus"] > 0.6 else "memory leans print, seen %d printed %d" % (t["seen"], t["won"])
    if t["verdict"] == "WATCH":
        return "memory unsure, %s" % ("narrative rising" if p.obs["accel"] > 0.55 else "narrative flat")
    if L["antennal"] < 0.45:
        return "noisy input, snipers %.0f%%" % (p.obs["snipers"] * 100)
    if L["mushroom"] < 0.4:
        return "memory leans rug, seen %d printed %d" % (t["seen"], t["won"])
    return "score below watch"


def window():
    """first window of N_SHOW pools from START with a pass, a watch, a skip and a close"""
    e = Engine(SEED)
    for _ in range(START):
        e.step()
    while True:
        snap = Engine(SEED)
        for _ in range(e.n):
            snap.step()
        pools, closes = [], []
        for i in range(N_SHOW):
            before = len(snap.closed)
            snap.next_pool()
            snap.tick_positions()
            for c in snap.closed[before:]:
                closes.append((i, c))
            p, t = snap.pool, snap.thought
            pools.append((p.name, t["verdict"], t["comb"], reason(p, t), t["act"], [p.obs[f] for f in FEATS], p.id))
            snap.act()
        kinds = {v for _, v, *_ in pools}
        if {"PASS", "WATCH", "SKIP"} <= kinds and closes:
            return pools, closes
        e.step()


_W, _C = window()
POOLS = [(n, v, sc, w) for n, v, sc, w, *_ in _W]
FIRST_ID, LAST_ID = _W[0][6], _W[-1][6]
OUTCOMES = []   # time, name, text, kind
for i, (name, pnl, final, _mn, _ex) in _C[:3]:
    OUTCOMES.append((T0 + STEP * i + 0.9, name, "closed %+.0f%%  %s" % (final * 100, "sugar" if pnl > 0 else "punishment"),
                     "sugar" if pnl > 0 else "pain"))
STAGES = [("antennal", 0.0), ("optic", 0.35), ("mushroom", 0.75), ("central", 1.10), ("motor", 1.45)]
LOBE_LABEL = {"antennal": "antennal lobes", "optic": "optic lobes", "mushroom": "mushroom bodies",
              "central": "central complex", "motor": "motor · seg"}
CENTROID = {k: brain.P[brain.mask(k)].mean(0) for k in LOBE_LABEL}
CENTROID["optic"] = np.array([0.82, 0.30, 0.0])
CENTROID["mushroom"] = np.array([-0.30, 0.44, -0.06])

# each mushroom point stands for one kenyon cell. it lights when that cell is in the pool's sparse code.
KC_OF = rng.integers(0, N_KC, size=brain.mask("mushroom").sum())
pool_masks = [np.isin(KC_OF, np.fromiter(w[4], int)) for w in _W]
feat = [np.array(w[5]) for w in _W]
glom = brain.S[brain.mask("antennal")] % 8
fb_mask = brain.mask("central") & (brain.S == 0)
opt_y = brain.P[brain.mask("optic"), 1]
fb_x = brain.P[fb_mask, 0]


def ease(u):
    u = min(1, max(0, u)); return u * u * (3 - 2 * u)


def camera(t):
    yaw = 0.15 + 0.55 * math.sin(t * 0.21 - 0.4)
    pitch = 0.20 + 0.07 * math.sin(t * 0.33)
    dist = 3.6 - 0.45 * ease((t - 0.5) / 3.0) + 0.5 * ease((t - (DUR - 3.2)) / 2.5)
    return yaw, pitch, dist


pulses = []           # (pts, start, dur, color)
fired = set()
counts = {"PASS": 0, "WATCH": 0, "SKIP": 0}
log = []


def schedule(t):
    """fire the events whose time has come"""
    for i, (name, verdict, score, why) in enumerate(POOLS):
        ts = T0 + i * STEP
        for stage, off in STAGES:
            key = (i, stage)
            if t >= ts + off and key not in fired:
                fired.add(key)
                if stage == "antennal":
                    brain.excite("antennal", 0.35 + 0.65 * feat[i][glom])
                    for s in "LR": pulses.append((brain.tracts["al_mb" + s], t, 0.45, (255, 245, 250)))
                elif stage == "optic":
                    ph = rng.random() * 6
                    brain.excite("optic", 0.25 + 0.75 * np.maximum(0, np.sin(opt_y * 9 + ph)) ** 2)
                    for s in "LR":
                        pulses.append((brain.tracts["ol_mb" + s], t, 0.4, (255, 245, 250)))
                        pulses.append((brain.tracts["ol_cx" + s], t + 0.05, 0.4, (255, 245, 250)))
                elif stage == "mushroom":
                    brain.excite("mushroom", np.where(pool_masks[i], 1.25, 0.12))
                    for s in "LR": pulses.append((brain.tracts["mb_cx" + s], t + 0.05, 0.3, (255, 245, 250)))
                elif stage == "central":
                    pos = -0.15 + 0.30 * min(1, max(0, (score - 0.3) / 0.45))
                    m = brain.mask("central")
                    vals = np.zeros(m.sum())
                    sub = brain.S[m] == 0
                    vals[sub] = 1.2 * np.exp(-((fb_x - pos) ** 2) / 0.0025)
                    brain.act[m] = np.maximum(brain.act[m], vals)
                    pulses.append((brain.tracts["cx_seg"], t + 0.08, 0.3, (255, 245, 250)))
                elif stage == "motor":
                    m = brain.mask("motor")
                    brain.act[m] = np.maximum(brain.act[m], 0.9)
                    brain.tint[m] = np.array(VCOL[verdict]) / 255
                    brain.tint_amt[m] = 1.0
                    counts[verdict] += 1
                    log.append((name, verdict, why))
    for (ts, name, text, kind) in OUTCOMES:
        if t >= ts and ("o", name) not in fired:
            fired.add(("o", name))
            col = LIME if kind == "sugar" else RED
            for s in "LR":
                pulses.append((brain.tracts["reward_mb" + s], t, 0.7, col))
                if kind == "sugar": pulses.append((brain.tracts["reward_al" + s], t, 0.5, col))
            log.append((name, text, "octopamine to antennal lobes and calyces" if kind == "sugar" else "punishment channel, memory marked rug"))


def assemble(t):
    u = np.clip((t - DELAY * 1.2) / 1.4, 0, 1)
    u = u * u * (3 - 2 * u)
    brain.P = START * (1 - u[:, None]) + TARGET * u[:, None]


def current_stage(t):
    for i in range(len(POOLS)):
        ts = T0 + i * STEP
        if ts <= t < ts + STEP:
            rel = t - ts
            st = None
            for stage, off in STAGES:
                if rel >= off: st = stage
            return i, st, rel
    return None, None, 0


def hud(img, t, yaw, pitch, dist, scale):
    d = ImageDraw.Draw(img, "RGBA")
    fade = ease((t - 1.0) / 1.2) * (1 - ease((t - (DUR - 3.0)) / 0.8))
    a = int(255 * fade)
    # header
    d.text((64, 52), "NERVE", font=grotesk(40), fill=PINK + (a,))
    d.text((64 + 148, 52), "BEEBRAIN", font=grotesk(40), fill=PINKH + (a,))
    d.text((66, 106), "a simulated bee brain scoring memecoin pools", font=mono(20), fill=GREY + (a,))
    d.text((W - 64, 60), "sim · synthetic pools · seed %d · pools #%d to #%d" % (SEED, FIRST_ID, LAST_ID), font=mono(18), fill=DIMC + (a,), anchor="ra")
    d.text((W - 64, 86), "960,000 neurons in a real bee · {:,} points drawn".format(len(brain.P)), font=mono(16), fill=DIMC + (a,), anchor="ra")
    i, st, rel = current_stage(t)
    # lobe label with leader line
    if st and fade > 0.2:
        c = CENTROID[st].copy()
        x, y, z, f = B.project(c[None], W, H, yaw, pitch, dist, scale)
        x, y = float(x[0]), float(y[0])
        lx, ly = (x + 190, y - 120) if x < W / 2 else (x - 190, y - 120)
        d.line([(x, y), (lx, ly)], fill=PINK + (int(170 * fade),), width=2)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], outline=PINK + (a,), width=2)
        d.text((lx, ly - 30), LOBE_LABEL[st], font=mono(22, True), fill=PINKH + (a,), anchor="mm")
    # pool card, bottom left
    if i is not None and fade > 0:
        name, verdict, score, why = POOLS[i]
        y0 = H - 230
        d.text((64, y0), "pool", font=mono(16), fill=GREY + (a,))
        d.text((64, y0 + 22), name, font=grotesk(46), fill=BONE + (a,))
        x = 64
        for stage, off in STAGES:
            done = rel >= off
            on = st == stage
            col = PINK if on else (PINKH if done else DIMC)
            d.text((x, y0 + 92), stage, font=mono(19, on), fill=col + (a,))
            x += int(d.textlength(stage, font=mono(19, on))) + 26
        if st == "motor":
            d.text((64, y0 + 134), why, font=mono(19), fill=GREY + (a,))
        # verdict, bottom right
        if st == "motor":
            k = ease((rel - 1.45) / 0.25)
            d.text((W - 64, H - 150), verdict, font=grotesk(92), fill=VCOL[verdict] + (int(a * k),), anchor="rs")
            d.text((W - 64, H - 128), "score %.2f" % score, font=mono(19), fill=GREY + (int(a * k),), anchor="ra")
    # counters
    if fade > 0:
        x = W - 64
        for key in ("SKIP", "WATCH", "PASS"):
            s = "%s %d" % (key, counts[key])
            d.text((x, H - 72), s, font=mono(20, True), fill=VCOL[key] + (a,), anchor="rs")
            x -= int(d.textlength(s, font=mono(20, True))) + 28
    # event log, top left under the header
    if fade > 0:
        for j, (n, v, w) in enumerate(log[-3:][::-1]):
            col = VCOL.get(v, LIME if "sugar" in v else RED)
            yy = 170 + j * 30
            al = int(a * (1 - j * 0.3))
            d.text((64, yy), n, font=mono(18, True), fill=BONE + (al,))
            d.text((200, yy), v.lower() if v in VCOL else v, font=mono(18), fill=col + (al,))
            d.text((200 + int(d.textlength(v.lower() if v in VCOL else v, font=mono(18))) + 20, yy), w, font=mono(18), fill=GREY + (al,))
    # title card
    tc = ease((t - (DUR - 2.6)) / 0.8)
    if tc > 0:
        d.text((W / 2, H / 2 - 20), "BEEBRAIN", font=grotesk(150), fill=BONE + (int(255 * tc),), anchor="ms")
        d.text((W / 2, H / 2 + 40), "a bee brain inside the nerve memecoin desk", font=mono(28), fill=PINK + (int(255 * tc),), anchor="ma")
        d.text((W / 2, H / 2 + 92), "github.com/h100envy/beebrain", font=mono(22), fill=GREY + (int(255 * tc),), anchor="ma")
    return img


def step_state(t):
    if t < 2.8:
        assemble(t)
    else:
        brain.P = TARGET
    brain.decay(0.93)
    schedule(t)


def frame(t):
    step_state(t)
    yaw, pitch, dist = camera(t)
    scale = H * 1.9
    live = []
    for pts, ts, dur, col in pulses:
        u = (t - ts) / dur
        if 0 <= u <= 1: live.append((pts, u, col))
    exposure = 0.3 + 0.7 * ease(t / 1.6)
    dim = 1 - 0.55 * ease((t - (DUR - 2.8)) / 0.8)
    img, _ = B.render(brain, W, H, yaw, pitch, dist=dist, scale=scale, pulses=live, exposure=exposure * dim)
    im = Image.fromarray(img)
    return hud(im, t, yaw, pitch, dist, scale)


if PREVIEW:
    ts = [float(x) for x in PREVIEW.split(",")]
    t = 0.0; k = 0
    while t <= max(ts) + 1e-6:
        im = frame(t)
        for p in ts:
            if abs(t - p) < 0.5 / FPS:
                os.makedirs(os.path.join(ROOT, "build", "preview"), exist_ok=True)
                im.save(os.path.join(ROOT, "build", "preview", "pv_%05.1f.png" % p))
        t += 1 / FPS
    sys.exit()

os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                       "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                       "-pix_fmt", "yuv420p", "-map_metadata", "-1", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
nf = int(DUR * FPS)
lo, hi = [int(x) for x in os.environ.get("RANGE", f"0,{nf}").split(",")]
for k in range(hi):
    t = k / FPS
    if k < lo:
        step_state(t)
        continue
    ff.stdin.write(np.asarray(frame(t).convert("RGB")).tobytes())
    if k % 60 == 0:
        print("frame", k, "/", nf, flush=True)
ff.stdin.close(); ff.wait()
print("done", OUT)
