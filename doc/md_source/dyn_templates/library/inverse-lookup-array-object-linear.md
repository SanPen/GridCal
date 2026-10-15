# Inverse linear lookup table

<!-- veragrid-block-introduction:start -->
**Inverse linear lookup table** finds the independent value that corresponds to a supplied tabulated output.

## Typical use

- Use it to invert a calibrated one-dimensional characteristic without deriving a closed-form inverse.
- Keep the table's y values strictly monotonic so that every input has at most one result.
<!-- veragrid-block-introduction:end -->

The block swaps the role of the stored axes and applies clipped linear interpolation. Increasing and decreasing output tables are both accepted; decreasing tables are normalized internally.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Input value to invert through the table | model-dependent |
| Output | `yo` | Interpolated inverse lookup result | model-dependent |
| Setting | `points` | Stored `(x, y)` table; y must be strictly monotonic | model-dependent |
