# 1D lookup tables

<!-- veragrid-block-introduction:start -->
**1D lookup tables** evaluate a tabulated characteristic instead of assuming one closed-form equation. Interpolation maps measured or commanded inputs to empirical outputs such as efficiency, saturation, capability, or control schedules while preserving the supplied breakpoints.

## Typical use

- Use it when manufacturer data or a calibrated characteristic is available as points or a matrix.
- Keep breakpoints ordered and decide deliberately whether values outside the table clip or extrapolate.
<!-- veragrid-block-introduction:end -->

### Purpose

The Basic library provides one canonical block for each distinct one-dimensional behavior:

- **Linear lookup table** stores a configurable point table and uses linear interpolation. General options select clipping or linear extrapolation outside the table.
- **Spline lookup table** stores a configurable point table and uses a natural cubic spline. Values outside the table are clipped to the first or final sample.
- **Dynamic linear lookup table** receives the lookup points as signals. General options select the number of points and the clipping rule.

### Behavior

- Receives one scalar lookup coordinate.
- Interpolates between strictly increasing x breakpoints.
- Outputs the corresponding approximated value.

### Characteristics

- Stored-table blocks expose their point table in the block settings.
- The dynamic block exposes `arr_x1...N` and `arr_y1...N` as signal inputs.
- The former fixed-size and object-array entries remain loadable for legacy files but are no longer duplicated in the Library.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Independent input variable for the lookup | model-dependent |
| Output | `yo` | Interpolated output value | model-dependent |
| Setting | `points` | Stored `(x, y)` point table for linear and spline blocks | model-dependent |
| General option | `point_count` | Number of signal-driven points in a dynamic linear table | count |
| General option | `clip` | Clip to endpoint values instead of extrapolating | boolean |
| Dynamic inputs | `arr_x1...N` | Ordered signal-driven x breakpoints | model-dependent |
| Dynamic inputs | `arr_y1...N` | Signal-driven samples corresponding to the x breakpoints | model-dependent |

## How to use it

- Use a stored-table block for fixed calibration data.
- Use the dynamic block only when another part of the model must drive the table coordinates or samples.
- Keep every x breakpoint strictly greater than the preceding breakpoint.
