bl_info = {
    "name": "Mandelbulb",
    "author": "Suussonic",
    "version": (1, 0, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Mandelbulb",
    "description": "Génère des fractales Mandelbulb 3D",
    "warning": "",
    "doc_url": "https://github.com/Suussonic/Mandelbulb",
    "category": "Add Mesh",
}

import bpy
import bmesh
import numpy as np
from bpy.types import Operator, Panel, PropertyGroup
from bpy.props import (
    FloatProperty, IntProperty, BoolProperty,
    FloatVectorProperty, PointerProperty,
)


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 1 — PROPRIÉTÉS (PropertyGroup)
# ─────────────────────────────────────────────────────────────────────────────

def _update_mandelbulb(self, context):
    """Callback déclenché à chaque modification de propriété."""
    obj = context.active_object
    if obj and obj.get("is_mandelbulb"):
        regenerate_mandelbulb(obj, context)


class MandelbulbProperties(PropertyGroup):
    """Conteneur de toutes les propriétés de la fractale (attaché à la scène)."""

    # ── Grille SDF ────────────────────────────────────────────────────────────
    resolution: IntProperty(
        name="Résolution",
        description=(
            "Nombre de voxels par axe (NxNxN). "
            "Attention : 64³ = 262 144 cellules, 128³ = 2 M"
        ),
        default=56,
        soft_min=16, soft_max=256,   # ← plage slider; pas de hard-limit bloquante
        update=_update_mandelbulb,
    )
    grid_size: FloatProperty(
        name="Taille grille",
        description="Demi-largeur du volume évalué (unités Blender)",
        default=1.5,
        soft_min=0.2, soft_max=8.0,
        update=_update_mandelbulb,
    )

    # ── Paramètres mathématiques ──────────────────────────────────────────────
    power: FloatProperty(
        name="Puissance",
        description=(
            "Exposant de la formule White-Nylander "
            "(8 = Mandelbulb classique, 2 = forme Mandelbrot, "
            "valeurs non-entières = formes exotiques)"
        ),
        default=8.0,
        soft_min=1.0, soft_max=32.0,
        update=_update_mandelbulb,
    )
    iterations: IntProperty(
        name="Itérations max",
        description=(
            "Nombre maximum d'itérations avant de décider "
            "si un point appartient à l'ensemble"
        ),
        default=10,
        soft_min=1, soft_max=64,
        update=_update_mandelbulb,
    )
    bailout: FloatProperty(
        name="Rayon d'échappement",
        description=(
            "Distance au-delà de laquelle la suite est considérée divergente. "
            "Valeur standard : 2.0"
        ),
        default=2.0,
        soft_min=0.5, soft_max=20.0,
        update=_update_mandelbulb,
    )

    # ── Mode Julia ────────────────────────────────────────────────────────────
    julia_mode: BoolProperty(
        name="Mode Julia",
        description=(
            "En mode Julia, c est fixé par julia_c "
            "au lieu d'être égal à la position du point évalué"
        ),
        default=False,
        update=_update_mandelbulb,
    )
    julia_c: FloatVectorProperty(
        name="Constante Julia (c)",
        description="Constante c utilisée en mode Julia",
        default=(0.0, 0.0, 0.0),
        soft_min=-3.0, soft_max=3.0,  # plus de hard-limit à ±2
        update=_update_mandelbulb,
    )

    # ── Distorsions ───────────────────────────────────────────────────────────
    offset: FloatVectorProperty(
        name="Décalage",
        description="Translation du point d'évaluation (exploration de zones)",
        default=(0.0, 0.0, 0.0),
        soft_min=-5.0, soft_max=5.0,  # était bloqué à ±3
        update=_update_mandelbulb,
    )
    twist: FloatProperty(
        name="Torsion",
        description="Rotation progressive à chaque itération (spirales)",
        default=0.0,
        soft_min=-5.0, soft_max=5.0,  # était bloqué à ±1
        update=_update_mandelbulb,
    )

    # ── Surface Nets ──────────────────────────────────────────────────────────
    smooth_normals: BoolProperty(
        name="Normales lissées",
        description="Active le smooth shading sur toutes les faces",
        default=True,
        update=_update_mandelbulb,
    )
    iso_level: FloatProperty(
        name="Niveau iso",
        description=(
            "Niveau d'isosurface SDF extrait (0.0 = surface exacte, "
            "valeur positive = surface gonflée, négative = surface rétrécye)"
        ),
        default=0.0,       # ← CORRIGÉ : était 0.001, ce qui biaisait la surface
        soft_min=-0.1, soft_max=0.1,
        precision=4,
        update=_update_mandelbulb,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 2 — ALGORITHME MANDELBULB (Signed Distance Field)
#
#  Formule White-Nylander (Wikipedia) :
#    v^n := r^n · <sin(n·θ)·cos(n·φ),  sin(n·θ)·sin(n·φ),  cos(n·θ)>
#  avec :
#    r     = sqrt(x²+y²+z²)
#    φ     = arctan2(y, x)              [azimut, plan XY]
#    θ     = arctan2(sqrt(x²+y²), z)   [polaire, depuis axe Z]
#
#  SDF estimée par la méthode Hubbard-Douady :
#    d ≈ 0.5 · |z| · ln(|z|) / |dz/dc|
# ─────────────────────────────────────────────────────────────────────────────

def mandelbulb_sdf_numpy(points, props):
    """
    Évalue la SDF du Mandelbulb sur un tableau de points 3D (vectorisé NumPy).

    Paramètres
    ----------
    points : ndarray (N, 3)  — coordonnées XYZ
    props  : MandelbulbProperties

    Retour
    ------
    distances : ndarray (N,)
        Positif  = extérieur de l'ensemble
        Négatif  = intérieur de l'ensemble
    """
    power    = props.power
    max_iter = props.iterations
    bailout  = props.bailout
    julia    = props.julia_mode
    julia_c  = np.array(props.julia_c)
    twist    = props.twist
    offset   = np.array(props.offset)

    N = len(points)
    pts = points + offset

    # Position initiale z = c (équivaut à sauter la 1re itération triviale z=0→c)
    zx = pts[:, 0].copy()
    zy = pts[:, 1].copy()
    zz = pts[:, 2].copy()

    if julia:
        cx = np.full(N, julia_c[0])
        cy = np.full(N, julia_c[1])
        cz = np.full(N, julia_c[2])
    else:
        cx = pts[:, 0].copy()
        cy = pts[:, 1].copy()
        cz = pts[:, 2].copy()

    # Norme de la dérivée (méthode Hubbard-Douady) ; initialisée à 1
    dz_norm = np.ones(N)

    escaped = np.zeros(N, dtype=bool)
    r_final = np.ones(N)

    for _ in range(max_iter):
        r2 = zx*zx + zy*zy + zz*zz
        r  = np.sqrt(r2)

        # Détection des nouvelles évasions
        newly_escaped = (~escaped) & (r > bailout)
        escaped  |= newly_escaped
        r_final   = np.where(newly_escaped, r, r_final)

        if np.all(escaped):
            break

        mask = ~escaped

        # Dérivée : |dz'| = power · r^(power-1) · |dz| + 1
        r_pm1   = np.where(mask, np.power(np.maximum(r, 1e-10), power - 1.0), 1.0)
        dz_norm = np.where(mask, power * r_pm1 * dz_norm + 1.0, dz_norm)

        # Torsion optionnelle (rotation autour de Z)
        if abs(twist) > 1e-8:
            angle   = twist * r * np.pi
            cos_a   = np.cos(angle)
            sin_a   = np.sin(angle)
            new_zx  = zx * cos_a - zy * sin_a
            new_zy  = zx * sin_a + zy * cos_a
            zx = np.where(mask, new_zx, zx)
            zy = np.where(mask, new_zy, zy)

        # ── Formule White-Nylander ────────────────────────────────────────
        r_safe  = np.maximum(r, 1e-10)

        # Coordonnées sphériques
        theta   = np.arctan2(np.sqrt(zx*zx + zy*zy), zz)   # polaire  [0, π]
        phi     = np.arctan2(zy, zx)                          # azimut   [-π, π]

        # Élévation à la puissance n
        rn      = np.power(r_safe, power)
        theta_n = theta * power
        phi_n   = phi   * power

        sin_t   = np.sin(theta_n)

        # Nouveau z^power
        new_zx = rn * sin_t * np.cos(phi_n)
        new_zy = rn * sin_t * np.sin(phi_n)
        new_zz = rn * np.cos(theta_n)

        # Addition de c
        zx = np.where(mask, new_zx + cx, zx)
        zy = np.where(mask, new_zy + cy, zy)
        zz = np.where(mask, new_zz + cz, zz)

    # Points non échappés → intérieur, on leur attribue une grande valeur
    r_final = np.where(~escaped, bailout * 2.0, r_final)

    # Estimation SDF de Hubbard-Douady : d = 0.5 · |z| · ln(|z|) / |dz|
    r_f_safe = np.maximum(r_final, 1e-10)
    dz_safe  = np.maximum(dz_norm, 1e-10)
    sdf = 0.5 * r_f_safe * np.log(r_f_safe) / dz_safe

    # Intérieur → distance négative
    sdf = np.where(~escaped, -np.abs(sdf), sdf)

    return sdf


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 3 — SURFACE NETS AMÉLIORÉ  (Gibson 1998)
#
#  Principe : un vertex par voxel actif (traversé par la surface),
#  positionné au barycentre des intersections sur les 12 arêtes du cube.
#  Les faces sont des quads connectant les 4 voxels autour de chaque arête active.
# ─────────────────────────────────────────────────────────────────────────────

def surface_nets_improved(sdf_grid, grid_size, resolution, threshold=0.0):
    """
    Extraction de surface par Surface Nets sur une grille SDF.

    Paramètres
    ----------
    sdf_grid   : ndarray (N, N, N)
    grid_size  : float — demi-largeur du volume
    resolution : int   — N
    threshold  : float — niveau iso (0.0 = surface exacte du SDF)

    Retour
    ------
    vertices : list of (x, y, z)
    faces    : list of (i0, i1, i2, i3)  — quads
    """
    N         = resolution
    cell_size = (2.0 * grid_size) / (N - 1)
    g         = sdf_grid

    # ── Étape 1 : Cellules actives ───────────────────────────────────────────
    c000 = g[:-1, :-1, :-1]
    c100 = g[1:,  :-1, :-1]
    c010 = g[:-1, 1:,  :-1]
    c110 = g[1:,  1:,  :-1]
    c001 = g[:-1, :-1, 1: ]
    c101 = g[1:,  :-1, 1: ]
    c011 = g[:-1, 1:,  1: ]
    c111 = g[1:,  1:,  1: ]

    min_val     = np.minimum.reduce([c000, c100, c010, c110, c001, c101, c011, c111])
    max_val     = np.maximum.reduce([c000, c100, c010, c110, c001, c101, c011, c111])
    active_mask = (min_val < threshold) & (max_val >= threshold)

    active_i, active_j, active_k = np.where(active_mask)
    n_active = len(active_i)

    if n_active == 0:
        return [], []

    # ── Étape 2 : Vertices sub-voxel ────────────────────────────────────────
    vertex_index = np.full((N - 1, N - 1, N - 1), -1, dtype=np.int32)
    vertex_index[active_i, active_j, active_k] = np.arange(n_active)

    # 12 arêtes : (coin_A, coin_B, Δx, Δy, Δz)
    EDGES = [
        (0, 1, 1, 0, 0), (2, 3, 1, 0, 0), (4, 5, 1, 0, 0), (6, 7, 1, 0, 0),
        (0, 2, 0, 1, 0), (1, 3, 0, 1, 0), (4, 6, 0, 1, 0), (5, 7, 0, 1, 0),
        (0, 4, 0, 0, 1), (1, 5, 0, 0, 1), (2, 6, 0, 0, 1), (3, 7, 0, 0, 1),
    ]
    # Positions locales des 8 coins dans le voxel
    CORNERS = [
        (0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0),
        (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1),
    ]

    vertices = []

    for idx in range(n_active):
        i = int(active_i[idx])
        j = int(active_j[idx])
        k = int(active_k[idx])

        # Coin origine du voxel en coordonnées monde
        ox = -grid_size + i * cell_size
        oy = -grid_size + j * cell_size
        oz = -grid_size + k * cell_size

        # Valeurs SDF des 8 coins
        vals = (
            g[i,   j,   k  ],  # 0
            g[i+1, j,   k  ],  # 1
            g[i,   j+1, k  ],  # 2
            g[i+1, j+1, k  ],  # 3
            g[i,   j,   k+1],  # 4
            g[i+1, j,   k+1],  # 5
            g[i,   j+1, k+1],  # 6
            g[i+1, j+1, k+1],  # 7
        )

        sum_x = sum_y = sum_z = 0.0
        count = 0

        for (a, b, dx, dy, dz) in EDGES:
            va, vb = vals[a], vals[b]
            if (va < threshold) != (vb < threshold):
                # Interpolation linéaire pour trouver l'intersection sur l'arête
                t  = (threshold - va) / (vb - va + 1e-12)
                t  = max(0.0, min(1.0, t))
                ca = CORNERS[a]
                sum_x += ox + (ca[0] + t * dx) * cell_size
                sum_y += oy + (ca[1] + t * dy) * cell_size
                sum_z += oz + (ca[2] + t * dz) * cell_size
                count += 1

        if count > 0:
            vertices.append((sum_x / count, sum_y / count, sum_z / count))
        else:
            # Fallback : centre du voxel
            vertices.append((
                ox + 0.5 * cell_size,
                oy + 0.5 * cell_size,
                oz + 0.5 * cell_size,
            ))

    # ── Étape 3 : Faces (quads) ──────────────────────────────────────────────
    # Chaque arête active génère un quad formé par les 4 voxels adjacents.

    faces = []

    def get_vi(ci, cj, ck):
        if 0 <= ci < N-1 and 0 <= cj < N-1 and 0 <= ck < N-1:
            return int(vertex_index[ci, cj, ck])
        return -1

    for idx in range(n_active):
        i = int(active_i[idx])
        j = int(active_j[idx])
        k = int(active_k[idx])

        # Arête selon Y (entre voxel j et j+1) — quad dans le plan XZ
        if j + 1 < N:
            va = g[i, j, k]
            vb = g[i, j + 1, k]
            if (va < threshold) != (vb < threshold):
                v0 = get_vi(i-1, j, k-1)
                v1 = get_vi(i,   j, k-1)
                v2 = get_vi(i,   j, k  )
                v3 = get_vi(i-1, j, k  )
                if v0 >= 0 and v1 >= 0 and v2 >= 0 and v3 >= 0:
                    if va < threshold:
                        faces.append((v0, v1, v2, v3))
                    else:
                        faces.append((v3, v2, v1, v0))

        # Arête selon Z (entre voxel k et k+1) — quad dans le plan XY
        if k + 1 < N:
            va = g[i, j, k]
            vb = g[i, j, k + 1]
            if (va < threshold) != (vb < threshold):
                v0 = get_vi(i-1, j-1, k)
                v1 = get_vi(i,   j-1, k)
                v2 = get_vi(i,   j,   k)
                v3 = get_vi(i-1, j,   k)
                if v0 >= 0 and v1 >= 0 and v2 >= 0 and v3 >= 0:
                    if va < threshold:
                        faces.append((v3, v2, v1, v0))
                    else:
                        faces.append((v0, v1, v2, v3))

        # Arête selon X (entre voxel i et i+1) — quad dans le plan YZ
        if i + 1 < N:
            va = g[i, j, k]
            vb = g[i + 1, j, k]
            if (va < threshold) != (vb < threshold):
                v0 = get_vi(i, j-1, k-1)
                v1 = get_vi(i, j,   k-1)
                v2 = get_vi(i, j,   k  )
                v3 = get_vi(i, j-1, k  )
                if v0 >= 0 and v1 >= 0 and v2 >= 0 and v3 >= 0:
                    if va < threshold:
                        faces.append((v0, v1, v2, v3))
                    else:
                        faces.append((v3, v2, v1, v0))

    return vertices, faces


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 4 — GÉNÉRATION DU MESH BLENDER
# ─────────────────────────────────────────────────────────────────────────────

def regenerate_mandelbulb(obj, context):
    """
    1. Construit la grille NxNxN
    2. Évalue la SDF (vectorisé NumPy)
    3. Extrait la surface (Surface Nets)
    4. Met à jour le mesh Blender
    """
    props     = context.scene.mandelbulb_props
    N         = props.resolution
    grid_size = props.grid_size

    # Grille régulière
    lin = np.linspace(-grid_size, grid_size, N)
    XX, YY, ZZ = np.meshgrid(lin, lin, lin, indexing='ij')
    points = np.stack([XX.ravel(), YY.ravel(), ZZ.ravel()], axis=1)

    # SDF
    sdf_flat = mandelbulb_sdf_numpy(points, props)
    sdf_grid = sdf_flat.reshape(N, N, N)

    # Surface Nets — iso-level corrigé à props.iso_level (défaut 0.0)
    verts, faces = surface_nets_improved(
        sdf_grid, grid_size, N, threshold=props.iso_level
    )

    # Mise à jour du mesh via BMesh
    mesh = obj.data
    bm   = bmesh.new()

    bm_verts = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()

    for face_indices in faces:
        try:
            bm.faces.new([bm_verts[fi] for fi in face_indices])
        except Exception:
            pass  # face dégénérée → ignorée

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    if props.smooth_normals:
        for f in bm.faces:
            f.smooth = True

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 5 — OPÉRATEURS BLENDER
# ─────────────────────────────────────────────────────────────────────────────

class OBJECT_OT_add_mandelbulb(Operator):
    """Crée un nouvel objet Mandelbulb dans la scène."""
    bl_idname  = "mesh.add_mandelbulb"
    bl_label   = "Ajouter Mandelbulb"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.mandelbulb_props
        N = props.resolution

        mesh = bpy.data.meshes.new("Mandelbulb")
        obj  = bpy.data.objects.new("Mandelbulb", mesh)

        context.collection.objects.link(obj)
        context.view_layer.objects.active = obj
        obj.select_set(True)
        obj["is_mandelbulb"] = True

        regenerate_mandelbulb(obj, context)

        self.report({'INFO'}, f"Mandelbulb généré ({N}³ = {N**3:,} voxels)")
        return {'FINISHED'}


class OBJECT_OT_regenerate_mandelbulb(Operator):
    """Force la régénération du Mandelbulb actif."""
    bl_idname  = "mesh.regenerate_mandelbulb"
    bl_label   = "Régénérer Mandelbulb"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.get("is_mandelbulb"):
            self.report({'WARNING'}, "Sélectionnez un objet Mandelbulb")
            return {'CANCELLED'}
        regenerate_mandelbulb(obj, context)
        self.report({'INFO'}, "Mandelbulb régénéré")
        return {'FINISHED'}


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 6 — PANNEAU UI
# ─────────────────────────────────────────────────────────────────────────────

class VIEW3D_PT_mandelbulb(Panel):
    """Panneau dans la 3D Viewport, onglet 'Mandelbulb'."""
    bl_label      = "Mandelbulb Fractal"
    bl_idname     = "VIEW3D_PT_mandelbulb"
    bl_space_type = 'VIEW_3D'
    bl_region_type= 'UI'
    bl_category   = "Mandelbulb"

    def draw(self, context):
        layout = self.layout
        props  = context.scene.mandelbulb_props

        # Boutons d'action
        layout.operator("mesh.add_mandelbulb",       icon='MESH_ICOSPHERE')
        obj = context.active_object
        if obj and obj.get("is_mandelbulb"):
            layout.operator("mesh.regenerate_mandelbulb", icon='FILE_REFRESH')

        layout.separator()

        # Grille
        box = layout.box()
        box.label(text="Grille SDF", icon='GRID')
        box.prop(props, "resolution")
        box.prop(props, "grid_size")

        # Formule
        box = layout.box()
        box.label(text="Formule Mandelbulb", icon='FORCE_VORTEX')
        box.prop(props, "power")
        box.prop(props, "iterations")
        box.prop(props, "bailout")

        # Julia
        box = layout.box()
        row = box.row()
        row.prop(props, "julia_mode", toggle=True, icon='OUTLINER_OB_POINTCLOUD')
        if props.julia_mode:
            box.prop(props, "julia_c")

        # Distorsion
        box = layout.box()
        box.label(text="Distorsion", icon='MOD_WAVE')
        box.prop(props, "offset")
        box.prop(props, "twist")

        # Surface Nets
        box = layout.box()
        box.label(text="Surface Nets", icon='MOD_REMESH')
        box.prop(props, "smooth_normals")
        box.prop(props, "iso_level")


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 7 — MENU D'AJOUT & HANDLER DE FRAME
# ─────────────────────────────────────────────────────────────────────────────

def menu_func(self, context):
    """Entrée dans Add > Mesh."""
    self.layout.operator(
        OBJECT_OT_add_mandelbulb.bl_idname,
        text="Mandelbulb Fractal",
        icon='FORCE_VORTEX',
    )


@bpy.app.handlers.persistent
def on_frame_change(scene, depsgraph=None):
    """
    Régénère automatiquement tous les objets Mandelbulb à chaque frame,
    ce qui permet d'animer les propriétés (ex: power animé de 2 à 8).
    """
    for obj in scene.objects:
        if obj.get("is_mandelbulb"):
            try:
                regenerate_mandelbulb(obj, bpy.context)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
#  SECTION 8 — ENREGISTREMENT
# ─────────────────────────────────────────────────────────────────────────────

classes = (
    MandelbulbProperties,
    OBJECT_OT_add_mandelbulb,
    OBJECT_OT_regenerate_mandelbulb,
    VIEW3D_PT_mandelbulb,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.mandelbulb_props = PointerProperty(type=MandelbulbProperties)
    bpy.types.VIEW3D_MT_mesh_add.append(menu_func)

    if on_frame_change not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(on_frame_change)


def unregister():
    if on_frame_change in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(on_frame_change)

    bpy.types.VIEW3D_MT_mesh_add.remove(menu_func)
    del bpy.types.Scene.mandelbulb_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
