# Mandelbulb

**3D Mandelbulb fractal generator** for Blender 5.1.

This add-on allows you to create and explore Mandelbulb and Julia fractals directly inside Blender. Geometry is generated from a **Signed Distance Field (SDF)** evaluated with NumPy and converted into a mesh using the **Surface Nets** algorithm.

---

## Features

* 3D Mandelbulb fractal generation
* Julia set mode support
* Fully animatable power parameter
* Offset and twist distortions
* Surface extraction using Surface Nets
* Automatic updates when parameters change
* Keyframe animation support
* Compatible with Blender 5.1+

---

## Usage

### Creating a Mandelbulb

1. Open the **Mandelbulb** tab in the 3D View.
2. Click **Add Mandelbulb**.
3. Adjust the parameters to achieve the desired result.

The mesh is automatically regenerated whenever parameters are modified.

---

## Parameters

### SDF Grid

#### Resolution

Number of voxels used to evaluate the fractal.

Recommended values:

* 32: fast preview
* 64: medium quality
* 128: high quality
* 256: very high quality

Higher resolutions produce more detail but significantly increase computation time.

#### Grid Size

Defines the region of space evaluated around the origin.

---

### Mandelbulb Formula

#### Power

Exponent used in the White–Nylander Mandelbulb formula.

Examples:

* 2: shapes similar to a three-dimensional Mandelbrot set
* 8: classic Mandelbulb
* non-integer values: experimental forms

#### Max Iterations

Maximum number of iterations used to determine set membership.

Higher values reveal finer details.

#### Escape Radius

Distance at which a point is considered to have diverged.

The standard value is:

* 2.0

---

### Julia Mode

Generates a 3D Julia fractal.

When Julia mode is enabled:

* the constant **c** remains fixed;
* **Julia C** controls the resulting shape.

---

### Distortion

#### Offset

Translates the coordinates before fractal evaluation.

Useful for exploring different regions of fractal space.

#### Twist

Applies a progressive rotation at each iteration.

Can create helical, spiraling, or twisted structures.

---

### Surface Nets

#### Smooth Normals

Enables smoothing on the generated mesh.

#### Iso Level

Controls the extraction level of the isosurface.

* 0.0: theoretical surface
* positive values: expanded surface
* negative values: contracted surface

---

## Animation

All parameters can be animated using Blender keyframes.

Examples:

* power animation
* transitions between different Julia fractals
* progressive iso-level variation
* dynamic twisting effects

The add-on automatically regenerates Mandelbulb objects whenever the current frame changes.

---

## Internal Workflow

The generation pipeline is as follows:

1. Create a regular volumetric grid.
2. Evaluate the Signed Distance Field (SDF) using vectorized NumPy operations.
3. Compute the Mandelbulb fractal using the White–Nylander formula.
4. Estimate distances using the Hubbard–Douady distance estimator.
5. Extract the isosurface using Surface Nets.
6. Generate the final Blender mesh.

This approach produces smoother and more accurate surfaces than simple voxelization methods.

---

## Requirements

* Blender 5.1 or later
* NumPy (included with Blender)

No additional external dependencies are required.

---

## License

Distributed under the GPL 3.0 License or later.
