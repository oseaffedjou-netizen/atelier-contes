"""Paper-cut puppet test: dog carrying cat, built and animated by code in Blender (bpy).
Usage: python3 puppet_test.py <shot:1|2> <out_dir> [frame_start frame_end] [--preview]"""
import bpy, bmesh, math, sys, os, random
from mathutils import Vector

SHOT = int(sys.argv[1]); OUT = sys.argv[2]
FA = int(sys.argv[3]) if len(sys.argv) > 3 else None; FB = int(sys.argv[4]) if len(sys.argv) > 4 else None
PREVIEW = '--preview' in sys.argv
IMG = os.environ.get('ASSETS', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'decors')) + '/'
FPS = 25
DUR = {1: 5.2, 2: 4.0}[SHOT]
random.seed(4)

# ---------------- scene ----------------
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
sc.render.engine = 'CYCLES'; sc.cycles.samples = 6 if not PREVIEW else 4; sc.cycles.use_adaptive_sampling = False; sc.cycles.filter_width = 1.2; sc.cycles.use_denoising = False
sc.cycles.max_bounces = 1; sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = (1920, 1080) if not PREVIEW else (960, 540)
sc.render.fps = FPS; sc.frame_start = 0; sc.frame_end = int(DUR * FPS) - 1
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
sc.render.image_settings.file_format = 'PNG'
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.0

# ---------------- materials ----------------
def paper_mat(name, rgb, alpha=1.0, fiber=0.16, strength=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 38; nz.inputs['Detail'].default_value = 10
    nz2 = nt.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 4; nz2.inputs['Detail'].default_value = 3
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(tc.outputs['Object'], nz2.inputs['Vector'])
    mix = nt.nodes.new('ShaderNodeMath'); mix.operation = 'MULTIPLY_ADD'
    nt.links.new(nz.outputs['Fac'], mix.inputs[0]); mix.inputs[1].default_value = fiber * 2; mix.inputs[2].default_value = 1 - fiber
    mix2 = nt.nodes.new('ShaderNodeMath'); mix2.operation = 'MULTIPLY_ADD'
    nt.links.new(nz2.outputs['Fac'], mix2.inputs[0]); mix2.inputs[1].default_value = 0.16; mix2.inputs[2].default_value = 0.92
    mul = nt.nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'
    nt.links.new(mix.outputs[0], mul.inputs[0]); nt.links.new(mix2.outputs[0], mul.inputs[1])
    col = nt.nodes.new('ShaderNodeRGB'); col.outputs[0].default_value = (*[c ** 2.2 for c in rgb], 1)
    vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'SCALE'
    nt.links.new(col.outputs[0], vm.inputs[0]); nt.links.new(mul.outputs[0], vm.inputs['Scale'])
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    nt.links.new(vm.outputs[0], em.inputs['Color'])
    if alpha < 1:
        tr = nt.nodes.new('ShaderNodeBsdfTransparent'); mx = nt.nodes.new('ShaderNodeMixShader')
        mx.inputs[0].default_value = alpha; nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
        nt.links.new(mx.outputs[0], out.inputs[0])
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
    return m

def image_mat(name, path, strength=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = bpy.data.images.load(path); em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Strength'].default_value = strength
    nt.links.new(tx.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], out.inputs[0])
    return m, tx.image

MATS = {}
def M(rgb, alpha=1.0, fiber=0.16):
    k = (rgb, alpha, fiber)
    if k not in MATS: MATS[k] = paper_mat(f'm{len(MATS)}', rgb, alpha, fiber)
    return MATS[k]

# ---------------- shapes ----------------
def blob(cx, cy, rx, ry, n=48, wob=0.05, tear=0.015, rot=0.0, seed=0):
    r = random.Random(seed); ph = [r.random() * 6.28 for _ in range(3)]
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        k = 1 + wob * (math.sin(2 * a + ph[0]) * 0.6 + math.sin(3 * a + ph[1]) * 0.4) + r.uniform(-tear, tear)
        x, y = math.cos(a) * rx * k, math.sin(a) * ry * k
        c, s = math.cos(rot), math.sin(rot)
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts

def limb(x0, y0, x1, y1, w0, w1, n=10, tear=0.008, seed=0):
    """tapered capsule from (x0,y0) to (x1,y1)"""
    r = random.Random(seed); dx, dy = x1 - x0, y1 - y0; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L; px, py = -uy, ux
    pts = []
    for i in range(n + 1):
        t = i / n; w = (w0 + (w1 - w0) * t) / 2
        pts.append((x0 + dx * t + px * w * (1 + r.uniform(-tear, tear) * 5), y0 + dy * t + py * w))
    for i in range(1, 8):  # round end
        a = math.pi * i / 8; w = w1 / 2
        pts.append((x1 + (px * math.cos(a) + ux * math.sin(a)) * w, y1 + (py * math.cos(a) + uy * math.sin(a)) * w))
    for i in range(n, -1, -1):
        t = i / n; w = (w0 + (w1 - w0) * t) / 2
        pts.append((x0 + dx * t - px * w * (1 + r.uniform(-tear, tear) * 5), y0 + dy * t - py * w))
    for i in range(1, 8):
        a = math.pi * i / 8; w = w0 / 2
        pts.append((x0 + (-px * math.cos(a) - ux * math.sin(a)) * w, y0 + (-py * math.cos(a) - uy * math.sin(a)) * w))
    return pts

def poly_obj(name, pts, mat, z, parent=None):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    vs = [bm.verts.new((x, y, 0)) for x, y in pts]
    f = bm.faces.new(vs); bmesh.ops.triangulate(bm, faces=[f]); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat); ob.location.z = z
    if parent: set_parent(ob, parent)
    return ob

def set_parent(ob, parent):
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy(); ob.parent = parent; ob.matrix_parent_inverse = parent.matrix_world.inverted(); ob.matrix_world = mw

def piece(name, pts, rgb, z, parent, edge=(0.95, 0.90, 0.80), shadow=True):
    """paper piece = colored shape + torn cream backing + soft drop shadow"""
    poly_obj(name, pts, M(rgb), z, parent)
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    r = random.Random(hash(name) % 999)
    back = [(cx + (x - cx) * 1.0 + (x - cx) / (abs(x - cx) + abs(y - cy) + 1e-6) * r.uniform(0.004, 0.011),
             cy + (y - cy) * 1.0 + (y - cy) / (abs(x - cx) + abs(y - cy) + 1e-6) * r.uniform(0.004, 0.011)) for x, y in pts]
    poly_obj(name + '_edge', back, M(EDGE if 'EDGE' in globals() else edge, fiber=0.22), z - 0.002, parent)
    if shadow:
        sh = [(x + 0.025, y - 0.03) for x, y in back]
        poly_obj(name + '_sh', sh, M((0.02, 0.01, 0.02), alpha=0.33, fiber=0.0), z - 0.004, parent)

def pivot(name, x, y, parent=None, z=0.0):
    e = bpy.data.objects.new(name, None); bpy.context.collection.objects.link(e); e.location = (x, y, z)
    if parent: set_parent(e, parent)
    return e

# ---------------- palette ----------------
TINT = {1: (0.72, 0.70, 0.84), 2: (0.70, 0.69, 0.85)}[SHOT]   # night grade so puppets sit in the illustration
def T(c): return tuple(min(1, c[i] * TINT[i]) for i in range(3))
BROWN = T((0.60, 0.34, 0.17)); BROWN_D = T((0.40, 0.22, 0.11)); BROWN_L = T((0.72, 0.45, 0.24))
WHITE = T((0.93, 0.87, 0.74)); WHITE_D = T((0.70, 0.64, 0.54))
NOSE = (0.07, 0.05, 0.05); EYE = (0.06, 0.04, 0.03)
TAB = T((0.58, 0.53, 0.45)); TAB_D = T((0.40, 0.36, 0.31)); STRIPE = T((0.24, 0.20, 0.17)); AMBER = (0.95, 0.66, 0.15)
GOLD = (1.0, 0.80, 0.30); EDGE = T((0.86, 0.80, 0.68))

def chaikin(pts, it=3):
    for _ in range(it):
        q = []
        for i in range(len(pts)):
            p0, p1 = pts[i], pts[(i + 1) % len(pts)]
            q += [(0.75 * p0[0] + 0.25 * p1[0], 0.75 * p0[1] + 0.25 * p1[1]), (0.25 * p0[0] + 0.75 * p1[0], 0.25 * p0[1] + 0.75 * p1[1])]
        pts = q
    return pts
def torn(pts, amt=0.006, seed=0):
    r = random.Random(seed); return [(x + r.uniform(-amt, amt), y + r.uniform(-amt, amt)) for x, y in pts]

# ---------------- dog rig (side view, facing +x, feet at y=0) ----------------
dog = pivot('dog', 0, 0)
cs = poly_obj('d_contact', blob(0.0, 0.0, 0.55, 0.05, seed=90, wob=0.0), M((0.02, 0.01, 0.03), alpha=0.42, fiber=0.0), -0.08, dog)
body = pivot('dog_body', 0, 0.55, dog)
BODY = chaikin([(0.40, 0.66), (0.43, 0.52), (0.30, 0.40), (0.10, 0.43), (-0.08, 0.48), (-0.28, 0.47), (-0.44, 0.53),
                (-0.47, 0.66), (-0.30, 0.71), (0.0, 0.70), (0.22, 0.72)])
piece('d_body', torn(BODY, 0.004, 1), BROWN, 0.00, body)
piece('d_saddle', torn(chaikin([(-0.38, 0.66), (-0.10, 0.70), (0.18, 0.71), (0.10, 0.62), (-0.15, 0.60), (-0.36, 0.60)]), 0.004, 2), BROWN_D, 0.010, body, shadow=False)
piece('d_chest', torn(chaikin([(0.43, 0.56), (0.30, 0.41), (0.12, 0.44), (0.20, 0.55), (0.34, 0.64)]), 0.004, 3), WHITE, 0.012, body, shadow=False)
piece('d_belly', torn(chaikin([(0.10, 0.44), (-0.10, 0.48), (-0.26, 0.48), (-0.05, 0.52)]), 0.003, 4), WHITE_D, 0.011, body, shadow=False)
neck = pivot('dog_neck', 0.34, 0.66, body)
piece('d_neck', torn(chaikin([(0.30, 0.62), (0.40, 0.56), (0.55, 0.74), (0.50, 0.84), (0.38, 0.76)]), 0.004, 5), BROWN, 0.02, neck)
head = pivot('dog_head', 0.50, 0.80, neck)
HEAD = chaikin([(0.47, 0.82), (0.53, 0.91), (0.64, 0.92), (0.72, 0.86), (0.86, 0.82), (0.86, 0.77), (0.72, 0.74), (0.60, 0.73), (0.50, 0.75)])
piece('d_head', torn(HEAD, 0.004, 6), BROWN, 0.03, head)
piece('d_muzzle', torn(chaikin([(0.70, 0.86), (0.86, 0.82), (0.86, 0.77), (0.72, 0.745), (0.66, 0.79)]), 0.003, 7), WHITE, 0.035, head, shadow=False)
piece('d_nose', blob(0.855, 0.805, 0.022, 0.017, seed=7, wob=0.0), NOSE, 0.04, head, shadow=False)
piece('d_eye', blob(0.63, 0.855, 0.016, 0.013, seed=8, wob=0.0), EYE, 0.04, head, shadow=False)
piece('d_brow', [(0.60, 0.875), (0.67, 0.882), (0.66, 0.872)], BROWN_D, 0.041, head, shadow=False)
piece('d_ear_far', [(0.50, 0.88), (0.50, 1.04), (0.58, 0.90)], BROWN_D, -0.02, head)
ear = pivot('dog_ear', 0.56, 0.90, head)
piece('d_ear', [(0.53, 0.89), (0.56, 1.07), (0.64, 0.91)], BROWN_D, 0.045, ear)
piece('d_ear_in', [(0.56, 0.91), (0.57, 1.01), (0.61, 0.92)], T((0.75, 0.50, 0.40)), 0.046, ear, shadow=False)
tail = pivot('dog_tail', -0.44, 0.65, body)
piece('d_tail', torn(chaikin([(-0.44, 0.69), (-0.60, 0.80), (-0.66, 0.95), (-0.62, 0.97), (-0.58, 0.82), (-0.44, 0.62)]), 0.004, 9), BROWN, -0.01, tail)
legs = {}
def leg(name, hx, hy, far, k, hind):
    col, colw = (BROWN_D, WHITE_D) if far else (BROWN, WHITE)
    z = -0.03 if far else 0.05
    up = pivot(name + '_up', hx, hy, body)
    if hind:
        piece(name + '_u', torn(chaikin([(hx - 0.10, hy + 0.10), (hx + 0.09, hy + 0.08), (hx + 0.04, hy - 0.20), (hx - 0.02, hy - 0.22)]), 0.004, 11), col, z, up)
    else:
        piece(name + '_u', limb(hx, hy + 0.04, hx + 0.01, hy - 0.21, 0.10, 0.055, seed=12), col, z, up)
    ky = hy - 0.21
    lo = pivot(name + '_lo', hx + (0.01 if hind else 0.01), ky, up)
    piece(name + '_l', limb(hx + 0.01, ky, hx + 0.0, ky - 0.24, 0.045, 0.036, seed=13), colw, z + 0.003, lo)
    piece(name + '_p', blob(hx + 0.035, ky - 0.255, 0.045, 0.022, seed=14, wob=0.0), colw, z + 0.006, lo)
    legs[name] = (up, lo, k)
leg('fl_far', 0.27, 0.47, True, 'F2', False); leg('bl_far', -0.30, 0.52, True, 'B2', True)
leg('fl', 0.31, 0.47, False, 'F1', False); leg('bl', -0.34, 0.52, False, 'B1', True)
piece('d_collar', limb(0.40, 0.78, 0.47, 0.64, 0.028, 0.028, seed=10), T((0.74, 0.62, 0.40)), 0.032, neck, shadow=False)

# ---------------- cat rig (crouched on the dog's back, gripping) ----------------
cat = pivot('cat', 0.02, 0.72, body)
CB = chaikin([(-0.20, 0.74), (-0.22, 0.82), (-0.10, 0.88), (0.08, 0.88), (0.18, 0.84), (0.20, 0.76), (0.05, 0.72), (-0.10, 0.71)])
piece('c_body', torn(CB, 0.004, 21), TAB, 0.08, cat)
for i, sx in enumerate([-0.15, -0.07, 0.01, 0.09]):
    piece(f'c_str{i}', torn(chaikin([(sx, 0.88), (sx + 0.03, 0.885), (sx + 0.045, 0.80), (sx + 0.025, 0.79)]), 0.003, 30 + i), STRIPE, 0.085, cat, shadow=False)
ctail = pivot('cat_tail', -0.20, 0.80, cat)
piece('c_tail', limb(-0.20, 0.80, -0.40, 1.02, 0.045, 0.03, seed=22), TAB, 0.075, ctail)
piece('c_tailtip', blob(-0.40, 1.02, 0.025, 0.025, seed=29, wob=0.0), STRIPE, 0.076, ctail, shadow=False)
chead = pivot('cat_head', 0.17, 0.86, cat)
CH = chaikin([(0.16, 0.86), (0.18, 0.95), (0.25, 0.98), (0.31, 0.96), (0.335, 0.90), (0.30, 0.85), (0.22, 0.84)])
piece('c_head', torn(CH, 0.003, 23), TAB, 0.095, chead)
piece('c_ear1', [(0.19, 0.94), (0.20, 1.04), (0.25, 0.97)], TAB_D, 0.096, chead)
piece('c_ear2', [(0.26, 0.975), (0.30, 1.05), (0.315, 0.95)], TAB_D, 0.090, chead)
piece('c_muzzle', blob(0.305, 0.885, 0.035, 0.028, seed=26), WHITE, 0.098, chead, shadow=False)
piece('c_eye', blob(0.27, 0.925, 0.017, 0.011, seed=24, wob=0.0), AMBER, 0.10, chead, shadow=False)
piece('c_pupil', blob(0.273, 0.925, 0.005, 0.010, seed=25, wob=0.0), EYE, 0.101, chead, shadow=False)
for i, (a1, b1) in enumerate([((0.20, 0.97), (0.22, 0.93)), ((0.235, 0.975), (0.245, 0.935))]):
    piece(f'c_hs{i}', limb(a1[0], a1[1], b1[0], b1[1], 0.012, 0.008, seed=40 + i), STRIPE, 0.099, chead, shadow=False)
bpy.ops.mesh.primitive_torus_add(major_radius=0.03, minor_radius=0.008, location=(0.345, 0.875, 0.105))
ring = bpy.context.active_object; ring.data.materials.append(paper_mat('gold', GOLD, fiber=0.02, strength=1.8)); set_parent(ring, chead)
cpaws = []
for nm, (x0, y0, x1, y1) in {'c_fpaw': (0.12, 0.78, 0.20, 0.66), 'c_bpaw': (-0.13, 0.76, -0.06, 0.66)}.items():
    p = pivot(nm, x0, y0, cat)
    piece(nm + '_s', limb(x0, y0, x1, y1, 0.05, 0.04, seed=hash(nm) % 99), TAB_D, 0.088, p)
    cpaws.append(p)

# ---------------- animation ----------------
def key(ob, f, rot=None, loc=None):
    if rot is not None: ob.rotation_euler.z = math.radians(rot); ob.keyframe_insert('rotation_euler', index=2, frame=f)
    if loc is not None: ob.location = loc; ob.keyframe_insert('location', frame=f)

PER = 0.40  # gallop period (s)
PH = {'F1': 0.0, 'F2': 0.10, 'B1': 0.55, 'B2': 0.65}
def gallop(t):
    w = 2 * math.pi / PER
    return w, (lambda k: w * t - 2 * math.pi * PH[k])

for f in range(sc.frame_start, sc.frame_end + 1):
    t = f / FPS; w = 2 * math.pi / PER
    for nm, (up, lo, k) in legs.items():
        a = w * t - 2 * math.pi * PH[k]
        front = k.startswith('F')
        swing = (38 if front else 34) * math.sin(a)
        bend = (35 + 35 * math.sin(a - 1.4)) if front else -(30 + 30 * math.sin(a + 1.6))
        key(up, f, rot=swing); key(lo, f, rot=bend)
    bob = 0.05 * math.sin(2 * w * t + 0.8)
    key(body, f, rot=4 * math.sin(w * t + 0.3), loc=(0, 0.55 + bob, 0))
    key(neck, f, rot=-5 * math.sin(w * t + 0.9))
    key(head, f, rot=-3 * math.sin(w * t + 1.4))
    key(ear, f, rot=-18 - 10 * math.sin(w * t + 2.0))
    key(tail, f, rot=8 + 14 * math.sin(w * t + 2.4))
    key(cat, f, rot=-3 + 4 * math.sin(w * t - 0.4), loc=(0.02, 0.74 + 0.025 * math.sin(2 * w * t + 0.2), 0))
    key(chead, f, rot=4 * math.sin(w * t + 0.6))
    key(ctail, f, rot=-10 + 22 * math.sin(w * t - 1.2))
    for i, p in enumerate(cpaws): key(p, f, rot=6 * math.sin(w * t + i))


# ---------------- background, foreground, camera ----------------
cam_data = bpy.data.cameras.new('cam'); cam_data.lens = 50
camo = bpy.data.objects.new('cam', cam_data); bpy.context.collection.objects.link(camo); sc.camera = camo

def bg_plane(img, z, width, cx, cy, strength=1.0):
    mat, im = image_mat('bg_' + img, IMG + img + '.png', strength)
    h = width * im.size[1] / im.size[0]
    bpy.ops.mesh.primitive_plane_add(size=1, location=(cx, cy, z)); ob = bpy.context.active_object
    ob.scale = (width, h, 1); ob.data.materials.append(mat)
    return ob

def grass_strip(z, y, x0, x1, rgb, hmax, seed, dens=60):
    r = random.Random(seed); x = x0
    while x < x1:
        x += r.uniform(0.25, 0.9) * 7 / dens * 6
        for j in range(r.randint(4, 8)):
            hh = r.uniform(0.35, 1) * hmax; lean = r.uniform(-0.35, 0.45) * hh; bx = x + r.uniform(-0.08, 0.08); w = r.uniform(0.018, 0.035)
            pts = [(bx - w, y), (bx - w * 0.3 + lean * 0.45, y + hh * 0.55), (bx + lean, y + hh), (bx + w * 0.5 + lean * 0.5, y + hh * 0.5), (bx + w, y)]
            c = tuple(min(1, k * r.uniform(0.8, 1.25)) for k in rgb)
            poly_obj(f'g{seed}_{x:.2f}_{j}', pts, M(c, fiber=0.2), z + r.uniform(-0.05, 0.05))

if SHOT == 1:
    # wide: B07 night doorway; dog bursts from the doorway area and runs left->right across the yard
    bg_plane('B07', -30, 31.0, 0.6, 1.2, strength=0.95)
    grass_strip(2.5, -2.45, -6, 8, (0.12, 0.10, 0.15), 0.85, 1)  # dark foreground grass (parallax)
    dog.location = (-1.0, -1.55, 0); dog.scale = (0.95, 0.95, 0.95)
    for f in range(sc.frame_start, sc.frame_end + 1):
        t = f / FPS
        x = -3.1 + 1.55 * t  # running speed in world units/s
        key(dog, f, loc=(x, -1.55, 0))
        cx = 0.0 + 0.55 * max(0, t - 1.0)
        key(camo, f, loc=(cx, 0.0, 10.0))
else:
    # tracking close: camera follows the dog; background and foreground stream past
    bg_plane('B02', -30, 40.0, 4.0, 0.6, strength=0.9)
    grass_strip(-1.0, -1.78, -4, 30, (0.30, 0.24, 0.22), 0.30, 2, dens=40)   # mid grass behind dog
    grass_strip(2.6, -1.45, -4, 40, (0.08, 0.07, 0.11), 1.0, 3, dens=30)
    cam_data.dof.use_dof = False; cam_data.dof.focus_distance = 8.0; cam_data.dof.aperture_fstop = 1.2     # near grass in front
    dog.scale = (1.55, 1.55, 1.55)
    for f in range(sc.frame_start, sc.frame_end + 1):
        t = f / FPS; x = 2.4 * t
        key(dog, f, loc=(x - 0.5, -1.75, 0))
        key(camo, f, loc=(x - 0.2, -0.35, 8.0))


sc.render.film_transparent = False
os.makedirs(OUT, exist_ok=True)
if FA is not None:
    sc.frame_start, sc.frame_end = FA, min(FB, sc.frame_end)
sc.render.filepath = os.path.join(OUT, 'f_')
bpy.ops.render.render(animation=True)
print('DONE')
