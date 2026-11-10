# AFM Surface Feature Analysis — Requirements

## 1. Purpose and scope

- **REQ-001 — Purpose:** The program shall analyze AFM chip-wafer surface data and identify requested surface features.
- **REQ-002 — Initial surface data:** The initial version shall process a 2D height grid, with one height value `z` for each `(x, y)` grid point, and associated measurement metadata.
- **REQ-003 — Initial feature types:** The initial version shall support trenches, bumps, and pits.
- **REQ-004 — Bounded initial scope:** The initial version shall remain a simple program focused on these requirements. A GUI and 3D or stacked-wafer data are outside its scope.
- **REQ-005 — Future feature growth:** The feature definitions and selection rules shall be changeable as requirements evolve, without prescribing a software architecture here.

## 2. Inputs and operator requests

- **REQ-010 — Image data file:** The program shall accept a `.csv` file with metadata rows in `# Key,value` form followed by a comma-separated 2D height matrix. Blank lines and comment rows are allowed before the matrix; the first non-comment row starts the matrix, and comments are not allowed after it starts.
- **REQ-011 — Image metadata:** The metadata shall include `ImageWidth`, `ImageHeight`, `ImageWidthPixel`, `ImageHeightPixel`, and `ImageDataUnit`. Width and height specify physical extents along the matrix column and row axes, respectively; pixel fields specify the corresponding matrix dimensions. The declared unit applies to both physical extents and matrix heights. The extent spans the first through last grid points, so pixel pitch is physical extent divided by pixel count minus one. Each pixel count shall be at least two, and matrix dimensions shall match the metadata.
- **REQ-012 — Supported input units:** The initial production implementation shall support meters and nanometers for physical image dimensions and height data.
- **REQ-013 — Request file:** The initial version shall accept operator requests through a `.inp` text file containing lines with keywords and optional specifications.
- **REQ-014 — Feature requests:** The request file shall allow the operator to specify wanted feature types and feature-specific thresholds.
- **REQ-015 — Output requests:** The request file shall allow the operator to request output detail, plots, inclusion of analysis details in the results file, and result measurement units where applicable.
- **REQ-016 — Feature default:** If feature types are omitted, the program shall look for trenches only.
- **REQ-017 — Default trench thresholds:** Unless overridden, the trench thresholds shall be 5 nm depth, 3 nm width, and 6 nm length. The requested trench length threshold shall be at least 1.5 times the requested trench width threshold.
- **REQ-018 — Default bump and pit thresholds:** Unless overridden, bump thresholds shall be 4 nm minimum height and 4 nm diameter; pit thresholds shall be 4 nm minimum depth and 4 nm diameter.
- **REQ-019 — Defaults:** The program shall apply documented defaults when optional requests are omitted.

## 3. Feature definitions and measurements

- **REQ-020 — Detection preprocessing:** For trench detection, calculate the image-wide mean and standard deviation, replace heights whose absolute Z-score is greater than 3 with the image-wide mean, then apply Gaussian smoothing with sigma 1 pixel. For bump and pit detection, calculate each point's local arithmetic mean from an 11×11-pixel window centered on that point, excluding the point itself and using available pixels at image edges. Replace a height with that local mean when its absolute difference from the local mean is greater than 1000 nm, then apply Gaussian smoothing with sigma 1 pixel. In both cases, the outlier-replaced, unsmoothed grid is the filtered image; the smoothed grid is the detection image. Measurements shall use the filtered image, not the smoothed image. Gradient calculations are required for bump and pit detection but are not required for trench detection.
- **REQ-021 — Local reference surface:** For each candidate, the program shall form a shell around its footprint using a fixed 11×11-pixel neighborhood in the initial implementation. Operator configuration of this neighborhood is deferred to a future increment. Exclude footprint points and retain shell heights greater than or equal to the image-wide median. The local reference height shall be the average of retained shell heights. If none are available, use the median of all filtered image heights. Apply this rule to trenches, bumps, and pits.
- **REQ-022 — Trench definition and boundary:** A trench is a roughly rectangular surface gap whose bottom is lower than nearby surrounding surface points; its bottom or walls may bend or deviate from a rectangular shape. Relative to the local reference height, include filtered-image footprint points whose depth is greater than or equal to the requested minimum trench depth. Points above that boundary criterion belong to the transition wall or surrounding surface and are excluded.
- **REQ-023 — Trench measurements:** For each reported trench, results shall include length, width, and depth. Depth is the local reference height minus the average filtered height of all collected trench points. Length and width shall use the region-moment major and minor axes, respectively, with the rectangular correction used in exploratory prototype V2.
- **REQ-024 — Bump definition and boundary:** A bump is a locally higher region with a generally round or square-like projection. Identify seeds using both `local_maxima` and `h_maxima` on the detection image, with h = 4.8 nm. Grow outward using slope calculated from one-pixel finite differences with calibrated physical pixel spacing. After the steep flank, the first outward location where slope falls below 20% grade marks the boundary. Retain the seed-connected interior even where its slope is low; stop at the first below-threshold crossing even if slope later increases.
- **REQ-025 — Bump measurements and shape:** For each reported bump, results shall include projected area and maximum height relative to the local reference. Projected area shall be the footprint pixel-cell count times calibrated pixel pitch in both axes, with cells clipped at image edges. The minimum-diameter threshold shall use equivalent-area diameter, 2 × sqrt(area / π). The aspect ratio, calculated as the region-moment major axis divided by its minor axis, shall be below 1.5. Centered height for reference cases shall be the average filtered height in a 3×3 window around the highest pixel, including that pixel; at an image edge, use available window pixels.
- **REQ-026 — Pit definition and boundary:** A pit is a locally lower region with a projected shape similar to a bump. Identify seeds using both `local_minima` and `h_minima` on the detection image, with h = 4.8 nm. Grow outward using slope calculated from one-pixel finite differences with calibrated physical pixel spacing. After the steep flank, the first outward location where slope falls below 20% grade marks the boundary. Retain the seed-connected interior even where its slope is low; stop at the first below-threshold crossing even if slope later increases.
- **REQ-027 — Pit measurements and shape:** For each reported pit, results shall include projected area and maximum depth relative to the local reference. Projected area shall be the footprint pixel-cell count times calibrated pixel pitch in both axes, with cells clipped at image edges. The minimum-diameter threshold shall use equivalent-area diameter, 2 × sqrt(area / π). The aspect ratio, calculated as the region-moment major axis divided by its minor axis, shall be below 1.5. Centered height for reference cases shall be the average filtered height in a 3×3 window around the lowest pixel, including that pixel; at an image edge, use available window pixels.
- **REQ-028 — Measurement units:** Feature measurements shall default to nanometers; projected area shall default to nm². The operator may request other result units.

## 4. Feature grouping and overlap

- **REQ-030 — Same-type overlap:** Same-type footprints connected by 8-connectivity, including diagonal pixel contact, shall be treated as one entity. Same-type extrema whose grown footprints connect shall be combined. Recompute measurements from the combined footprint and apply feature thresholds to those measurements.
- **REQ-031 — Different-type overlap:** For footprints of different feature types, calculate intersection-over-union from their projected XY areas using calibrated pixel pitches and edge-clipped pixel cells. When this ratio is at least 80%, retain only the higher-priority whole feature and suppress the lower-priority whole feature. Overlap below 80%, including contact without shared area, shall not cause suppression.
- **REQ-032 — Initial priority:** The initial priority order shall be trench, then pit, then bump.
- **REQ-033 — Future selection rules:** The selection rule shall be changeable in future work to allow other rules, such as selection based on physical prominence.

## 5. Results, logs, and plots

- **REQ-040 — Results file:** Each analysis shall produce a plain-text results file.
- **REQ-041 — Per-feature results:** Results shall identify each feature by type and an index within its type, report the total number of detected features of each type, and include the required measurements.
- **REQ-042 — Calculation summary:** The results file shall include the operator’s specified calculation choices.
- **REQ-043 — Analysis details:** The results file shall identify where the logfile can be found. Analysis details mean operational information such as errors, warnings, and progress reports; they do not mean additional scientific calculations or feature measurements.
- **REQ-044 — Log file:** Errors, warnings, and progress reports shall be recorded in a plain-text logfile.
- **REQ-045 — Optional details in results:** When requested, operational analysis details (errors, warnings, and progress reports) may also be included in the results file.
- **REQ-046 — Plots:** When requested, plots shall be generated as additional files.
- **REQ-047 — Console output:** The initial version shall not print scientific analysis output to the console. CLI diagnostics and logfile setup or writing failures may be printed to standard error; scientific results shall be written to an output file in a later increment.
- **REQ-048 — Confidence values deferred:** The initial version shall not calculate or report confidence values. Future work may add separate confidence measures for whether a region is an actual feature and whether it is of interest.

## 6. Usability and scientific constraints

- **REQ-050 — Project workflow:** The project shall support a workflow of cloning the GitHub repository, installing the required Python environment, running tests with `pytest`, and running an operator-requested analysis through a CLI in a terminal or IDE.
- **REQ-051 — Machine independence:** The initial version shall not depend on a particular AFM machine or vendor export format; it shall process the specified general height-table format.
- **REQ-052 — Scientific validation:** Feature definitions, thresholds, measurements, and analysis results shall be checked against scientific reference data supplied during the project. Passing software tests alone shall not establish scientific correctness.
- **REQ-053 — Python version:** The project shall support Python 3.13 and later versions.

## 7. Draft acceptance criteria

- **AC-001:** Given a valid `.csv` height table and metadata plus a `.inp` request file, the program completes an analysis and produces a text results file.
- **AC-002:** When no feature type is specified, the program analyzes trenches by default.
- **AC-003:** When no thresholds are specified, the documented default thresholds are applied in nanometers. The defaults give a trench length-to-width ratio of 2.0, and every accepted trench threshold configuration satisfies the minimum ratio of 1.5.
- **AC-004:** Each reported feature has a type-specific index, and the results state the total count for each reported type.
- **AC-005:** Trench results include length, width, and depth; bump results include projected area and maximum height; pit results include projected area and maximum depth.
- **AC-006:** Measurements use the requested units, or the documented defaults if none are requested.
- **AC-007:** Same-type footprints connected by 8-connectivity are reported as one entity. For different-type footprints, an intersection-over-union ratio of at least 80% suppresses the lower-priority whole feature; lower ratios retain both.
- **AC-008:** A logfile contains errors, warnings, and progress reports; requested plots and optional operational details are produced.
- **AC-009:** Scientific analysis output is not printed to the console; CLI diagnostics may be printed to standard error.
- **AC-010 — Preprocessing and measurements:** Trench preprocessing replaces heights with absolute image-wide Z-score greater than 3 by the image-wide mean. Bump and pit preprocessing replaces heights that differ by more than 1000 nm from the mean of their centered 11×11-pixel neighborhood (excluding the point) with that local mean. Both paths then apply sigma-1-pixel Gaussian smoothing for detection and use the filtered, unsmoothed image for measurements.
- **AC-011 — Trench reference case:** On `data/trenches.csv`, analysis identifies 3 horizontal, somewhat skewed trenches; each has width 45–55 nm and length 501–503 nm, and their mean depth is 28–32 nm.
- **AC-012 — Bump reference case:** On `data/bump.csv`, the centered noisy bump measures 18–22 nm in equivalent-area diameter, has 3×3 centered height 3–7 nm, and aspect ratio below 1.5.
- **AC-013 — Pit reference case:** On `data/pit.csv`, the centered noisy pit measures 18–22 nm in equivalent-area diameter, has 3×3 minimum-centered height −2 to +2 nm, and aspect ratio below 1.5.

## 8. Assumptions and unresolved questions

These details are not yet specified and should remain open rather than be guessed:

- The exact syntax and supported keywords for `.inp` files.
- Whether results should include a feature’s location or pixel coordinates; these are not yet specified.
- The exact text layout and meaning of output detail levels.
- Which plots are required and what they should show.
- What constitutes an error versus a warning, and how invalid or incomplete inputs should be reported.
- What installation environments should be supported.
- Additional independent scientific validation data and tolerances may be supplied as the project progresses; the initial approved reference cases and expected ranges are specified in AC-011–AC-013.
