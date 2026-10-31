# AFM Surface Feature Analysis — Requirements

## 1. Purpose and scope

- **REQ-001 — Purpose:** The program shall analyze AFM chip-wafer surface data and identify requested surface features.
- **REQ-002 — Initial surface data:** The initial version shall process a 2D height grid, with one height value `z` for each `(x, y)` grid point, and associated measurement metadata.
- **REQ-003 — Initial feature types:** The initial version shall support trenches, bumps, and pits.
- **REQ-004 — Bounded initial scope:** The initial version shall remain a simple program focused on these requirements. A GUI and 3D or stacked-wafer data are outside its scope.
- **REQ-005 — Future feature growth:** The feature definitions and selection rules shall be changeable as requirements evolve, without prescribing a software architecture here.

## 2. Inputs and operator requests

- **REQ-010 — Image data file:** The program shall accept a `.csv` file containing metadata in its first lines, followed by the 2D height matrix, with each matrix row represented by a line.
- **REQ-011 — Image metadata:** The metadata shall describe image width and row-axis length in pixels and physical length units, and state a declared unit that applies to both physical image dimensions and the height values in the matrix.
- **REQ-012 — Supported input units:** The initial production implementation shall support meters and nanometers for physical image dimensions and height data.
- **REQ-013 — Request file:** The initial version shall accept operator requests through a `.inp` text file containing lines with keywords and optional specifications.
- **REQ-014 — Feature requests:** The request file shall allow the operator to specify wanted feature types and feature-specific thresholds.
- **REQ-015 — Output requests:** The request file shall allow the operator to request output detail, plots, inclusion of analysis details in the results file, and result measurement units where applicable.
- **REQ-016 — Feature default:** If feature types are omitted, the program shall look for trenches only.
- **REQ-017 — Default trench thresholds:** Unless overridden, the trench thresholds shall be 5 nm depth, 3 nm width, and 6 nm length. The requested trench length threshold shall be at least 1.5 times the requested trench width threshold.
- **REQ-018 — Default bump and pit thresholds:** Unless overridden, bump thresholds shall be 4 nm minimum height and 4 nm diameter; pit thresholds shall be 4 nm minimum depth and 4 nm diameter.
- **REQ-019 — Defaults:** The program shall apply documented defaults when optional requests are omitted.

## 3. Feature definitions and measurements

- **REQ-020 — Trench definition:** A trench is a roughly rectangular surface gap whose bottom is substantially lower than nearby surrounding surface points. Its bottom or walls may bend or deviate to some degree from a rectangular shape.
- **REQ-021 — Trench measurements:** For each reported trench, results shall include length, width, and depth.
- **REQ-022 — Bump definition:** A bump is a group of surface points locally higher than nearby surrounding points. Its 2D projection is generally round, though it may be square-like.
- **REQ-023 — Bump measurements:** For each reported bump, results shall include projected area and maximum height relative to nearby surrounding points.
- **REQ-024 — Pit definition:** A pit is a group of surface points locally lower than nearby surrounding points, with a projected shape similar to a bump.
- **REQ-025 — Pit measurements:** For each reported pit, results shall include projected area and maximum depth relative to nearby surrounding points.
- **REQ-026 — Measurement units:** Feature measurements shall default to nanometers; projected area shall default to nm². The operator may request other result units.

## 4. Feature grouping and overlap

- **REQ-030 — Same-type overlap:** Overlapping regions of the same feature type shall be treated as one entity.
- **REQ-031 — Different-type overlap:** When regions of different feature types overlap, only the feature type with the highest priority shall be selected for the overlapping entity.
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
- **REQ-047 — Console output:** The initial version shall not print analysis output to the console.
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
- **AC-007:** Same-type overlapping regions are reported as one entity; different-type overlaps follow the stated priority.
- **AC-008:** A logfile contains errors, warnings, and progress reports; requested plots and optional operational details are produced.
- **AC-009:** Analysis output is not printed to the console.

## 8. Assumptions and unresolved questions

These details are not yet specified and should remain open rather than be guessed:

- The exact syntax and supported keywords for `.inp` files.
- The exact metadata syntax and conventions for the `.csv` file, including how metadata lines are distinguished from matrix rows.
- The exact comparison behavior at each threshold and how thresholds apply before or after candidate grouping.
- How feature boundaries are determined, how measurements such as trench length and width are calculated, and how the nearby surrounding reference points are selected.
- How overlap is determined when regions have different boundaries or only partially intersect.
- Whether results should include a feature’s location or pixel coordinates; these are not yet specified.
- The exact text layout and meaning of output detail levels.
- Which plots are required and what they should show.
- What constitutes an error versus a warning, and how invalid or incomplete inputs should be reported.
- What installation environments should be supported.
- The scientific reference data and independent validation criteria are to be supplied as the project progresses.
