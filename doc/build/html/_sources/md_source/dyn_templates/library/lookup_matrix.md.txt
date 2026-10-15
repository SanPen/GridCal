# 2D lookup tables

<!-- veragrid-block-introduction:start -->
**2D lookup tables** evaluate a tabulated surface instead of assuming one closed-form equation. They map two measured or commanded inputs to empirical outputs such as efficiency, saturation, capability, or control schedules.

## Typical use

- Use it when manufacturer data or a calibrated characteristic is available as points or a matrix.
- Keep breakpoints ordered and decide deliberately whether values outside the table clip or extrapolate.
<!-- veragrid-block-introduction:end -->

### Purpose

The Basic library exposes two distinct surface interpolators:

- **Bilinear lookup table** interpolates linearly inside each grid cell.
- **2D spline lookup table** applies natural cubic interpolation across both axes.

Both blocks clip coordinates outside the table to its nearest boundary.

### Behavior

- Receives two independent inputs.
- Interpolates on a stored matrix whose x and y axes are strictly increasing.
- Outputs one approximated scalar value.

### Characteristics

- Useful for efficiency maps, saturation surfaces, and two-input nonlinear relationships.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi1` | First independent input variable | model-dependent |
| Input | `yi2` | Second independent input variable | model-dependent |
| Output | `yo` | Interpolated output value | model-dependent |
| Setting | `x_y_z_values` | Ordered x axis, ordered y axis, and row-major z matrix | model-dependent |

## How to use it

- Use bilinear interpolation for piecewise-planar data and predictable local behavior.
- Use the spline variant when a smooth surface is required.
- Keep each axis strictly increasing and provide one z row per y point with one value per x point.
