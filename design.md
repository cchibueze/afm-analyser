# AFM Surface Feature Analysis — Initial Software Design

## 1. Purpose and scope

This document describes the initial software design for the requirements in `requirements.md`. It covers a command-line Python program that reads a general AFM height-table CSV and an operator request file, analyzes a 2D height grid, and writes requested results and operational outputs.

The initial scope is trenches, pits, and bumps. A GUI, 3D or stacked-wafer data, confidence values, vendor-specific input formats, and a general plugin system are outside the initial design.

The approved scientific definitions are recorded in `requirements.md`. Production analysis should implement those definitions and validate them against the approved reference cases. Exploratory prototypes remain evidence about possible techniques, not authoritative scientific behavior unless a rule was explicitly adopted.

## 2. Design summary

The production code uses a `src`-layout Python package, with tests under `tests/` and project configuration in `pyproject.toml`. Keep modules focused on the agreed responsibilities and add them as their interfaces are implemented. The exploratory scripts remain in `prototypes/` and are not the production architecture. The initial request increment defines feature and threshold models in `models.py` and request validation/defaults in `requests.py`; later increments can add input, analysis, reporting, selection, and output modules as their contracts are agreed.

Keep scientific calculations separate from file parsing and report formatting. Use explicit data passed between stages rather than making analysis depend on CSV/INP syntax or output paths. Set up operational reporting at the beginning of a run so progress, warnings, and errors can be recorded throughout input handling and analysis. Write final results and requested plots when the relevant analysis data is available.

Use nanometers (nm) and square nanometers (nm²) as internal units. Convert supported input measurements and thresholds to these units when reading/validating inputs, and convert feature measurements to requested result units when writing results.

## 3. Responsibilities and boundaries

These responsibilities describe the production component boundaries, not a requirement for one module or class per responsibility. Modules should be introduced where they provide a clear cohesive home for implemented behavior.

| Responsibility | Owns | Does not own |
|---|---|---|
| CLI orchestration | Accepting the input paths, setting up the run, calling the stages, and determining run completion. | Scientific definitions or file-format parsing details. |
| CSV input | Reading metadata and the height matrix; validating the shape and values needed to form image data. | Feature detection or measurement. |
| INP request input | Reading request keywords and optional specifications. | Scientific algorithms. |
| Request models and validation | Representing feature-specific thresholds and validated selections; applying documented defaults, including trench-only selection and the trench length-to-width constraint. | Duplicating defaults in detectors or output code. |
| Run reporting | Recording progress, warnings, and errors throughout the run in the logfile and, when requested, making those details available for inclusion in results. | Scientific calculations or feature measurements. |
| Candidate analysis | Preprocessing heights, detecting requested candidates, measuring required properties, and applying the approved boundary and local-reference rules. Detection and measurements use their specified filtered/smoothed image representations. | CSV/INP syntax, logfile paths, and report formatting. |
| Overlap selection | Grouping overlapping candidates of the same type and resolving cross-type overlaps using the agreed rule. | Candidate generation or result serialization. |
| Results and plots | Writing type-indexed features, counts, measurements, calculation choices, logfile location, optional operational details, and requested plots. | Recomputing scientific measurements. |

Do not introduce a general detector interface, plugin registry, dependency-injection mechanism, or multiple output backends without a concrete requirement. If the feature algorithms become substantial, they can be separated into functions or modules while retaining the data boundaries described below.

## 4. Principal data and interfaces

The following are conceptual values passed between stages. Their final Python representation and exact fields depend on the file-format and scientific decisions that remain open.

- **Image data:** a 2D grid of measured surface heights plus metadata describing pixel dimensions, physical width and row-axis length, and stated units. CSV metadata rows use `# Key,value`; the required keys are `ImageWidth`, `ImageHeight`, `ImageWidthPixel`, `ImageHeightPixel`, and `ImageDataUnit`. Blank lines and comment rows may precede the matrix; the first non-comment row begins it, and comments after that point are invalid. The declared unit (`m` or `nm`) applies to both extents and all matrix heights. Width and height are the physical extents along the matrix column and row axes. Each extent runs from the first through last grid point, so pitch is extent divided by pixel count minus one; pixel counts must be at least two, and matrix dimensions must match the declared counts. The physical row-axis extent is represented internally as `length_nm`, distinct from the per-point `heights_nm` values. Analysis receives calibrated physical spacing and heights in nm.
- **Parsed request:** operator-specified feature types, thresholds, result units, detail level, plot request, and whether operational details should also appear in the results file.
- **Effective request:** validated request with documented defaults applied. Thresholds are represented in nm; area values use nm². The local-reference shell is fixed at 11×11 pixels in the initial implementation; operator configuration is deferred to a future increment. Bump and pit thresholds have separate models so their fields and behavior can evolve independently.
- **Feature candidate/result:** feature type, region representation, and required measurements. The region representation must support agreed grouping and overlap decisions. Whether results include location or pixel coordinates remains open.
- **Run reporter:** a lightweight way for stages to record progress, warnings, and errors as the run proceeds. It should be initialized by the CLI and passed explicitly to stages that need to report. Scientific code should not write directly to files or know logfile formatting.
- **Analysis result:** selected features and their measurements, together with enough effective-request information to describe calculation choices in the results file.

At a high level, the interfaces are:

1. Read the CSV into image data.
2. Read, validate, and default the INP request into an effective request.
3. Detect and measure candidates using image data and the effective request.
4. Group and select candidates according to overlap rules.
5. Write results and any requested plots from the analysis result and effective request.

Run reporting is available throughout these steps, rather than being a final-only output stage. File writers remain outside scientific analysis.

## 5. Data flow

```text
CLI starts run and sets up output paths and run reporter
  ├── CSV reader ──> image data and calibrated metadata ─────────────┐
  ├── INP reader ──> validated request with defaults ────────────────┤
  │                                                                  v
  │                                                  candidate detection and
  │                                                  scientific measurements
  │                                                                  │
  │                                                overlap grouping/selection
  │                                                                  │
  └── run reporter <── progress, warnings, and errors                 v
                                               results and requested plots

Run reporter ──> logfile throughout the run
             └─> results file too, when requested
```

The results file is written when sufficient analysis data is available. The logfile is written during the run, so operational information is preserved even if later analysis or output fails. Scientific analysis output is not printed to the console; CLI diagnostics and logfile setup or writing failures may be printed to standard error. Scientific results are written to an output file in a later increment. CLI exit behavior remains to be specified.

## 6. Scientific analysis and overlap rules

Candidate analysis shall follow the approved scientific rules in `requirements.md`:

- Preprocess trenches by replacing heights with absolute image-wide Z-score greater than 3 by the image-wide mean. For bumps and pits, replace heights that differ by more than 1000 nm from the mean of their centered 11×11-pixel neighborhood with that local mean; exclude the point being filtered and use available neighborhood pixels at image edges. Apply Gaussian smoothing at sigma 1 pixel after filtering. Use the filtered-and-smoothed image for detection, and the filtered, unsmoothed image for measurements. Bump and pit gradients use one-pixel differences with calibrated physical pixel spacing; trench detection need not calculate gradients.
- Use a fixed 11×11-pixel shell for each candidate's local reference in the initial implementation; operator configuration is deferred to a future increment. Exclude footprint points, retain shell values at or above the image-wide median, and average them. If none remain, use the median of the filtered image. This applies to all feature types.
- A trench footprint contains points whose depth below the local reference is at least the requested minimum trench depth. Trench depth is local reference minus mean filtered height over the footprint; length and width use region-moment axes with V2's rectangular correction.
- Bump seeds use the intersection of `local_maxima` and `h_maxima` with h = 4.8 nm; pit seeds use the intersection of `local_minima` and `h_minima` with h = 4.8 nm. Bump and pit boundaries grow from these extrema on the detection image. After the steep flank, the first outward point where slope falls below 20% grade defines the boundary; retain the connected interior, including low-slope seed areas. Merge same-type candidates whose grown footprints touch under 8-connectivity.
- Bump/pit area is pixel-cell count times calibrated pixel pitches, clipping cells at image edges. Their diameter threshold uses equivalent-area diameter. Their aspect ratio is the region-moment major axis divided by minor axis and must be below 1.5. Centered-height reference measurements average a 3×3 neighborhood around the bump maximum or pit minimum, including the extremum pixel and clipping at image edges.
- Minimum thresholds pass at equality. Group connected same-type footprints, recompute measurements from each merged footprint, then apply thresholds. Compare unrounded measurements and round only for display.

Overlap selection is a distinct responsibility. Same-type footprints touching by an edge or corner merge transitively. For different-type footprints, calculate intersection-over-union from their projected XY areas using calibrated pixel pitches and edge-clipped pixel cells. Suppress the lower-priority whole feature only when that ratio is at least 80%; lower ratios, including contact without shared area, retain both. Priority is trench, then pit, then bump. Selected results are returned in separate trench, pit, and bump lists, each sorted by centroid; priority governs suppression rather than ordering across those lists. Software tests can check behavior against defined examples, but passing tests alone does not establish scientific correctness.

## 7. Requirements coverage

| Requirement area | Design response |
|---|---|
| 2D height grid and measurement metadata (REQ-001–004) | Image data represents the calibrated 2D surface; no GUI or 3D model is included. |
| Input formats and operator choices (REQ-010–019) | The CSV metadata syntax, required keys, supported units, matrix dimensions, and pixel-pitch convention are specified in REQ-010–012. A dedicated future input responsibility will parse INP requests; request validation applies documented defaults. |
| Feature definitions and measurements (REQ-020–028) | Scientific analysis follows approved preprocessing, boundary, local-reference, measurement, and aspect-ratio rules. Internal units are nm and nm², with result conversion at output. |
| Grouping and priority (REQ-030–033) | Separate overlap selection merges 8-connected same-type footprints and suppresses lower-priority whole features when mixed-type intersection-over-union is at least 80%, using trench, pit, bump priority. Selected outputs are separated into feature-specific centroid-ordered lists. |
| Results, logs, plots, and console behavior (REQ-040–048) | Results and plots are file outputs; run reporting writes operational messages during the run; optional messages are included in results by request; no confidence values or console analysis output. |
| Workflow, machine independence, and scientific validation (REQ-050–053) | CLI orchestrates general height-table input. Tests support software behavior; approved reference cases and additional independent data assess scientific validity. |

## 8. Alternatives and trade-offs

### Prototype script versus production package

The exploratory single scripts were useful for learning and workflow refinement. The production package establishes focused module boundaries incrementally so request validation can be tested independently and later responsibilities do not become coupled to file syntax or output paths. The trade-off is a small amount of packaging structure up front; adding modules only as responsibilities are implemented avoids speculative abstractions.

### Separate detector class or module per feature

Separate feature implementations can make distinct algorithms easier to understand if they become large or evolve independently. Starting with the simplest organization that keeps each algorithm understandable avoids parallel boilerplate and speculative interfaces. A shared abstraction should be introduced only if the actual algorithms demonstrate meaningful common behavior.

### Logging only after analysis versus throughout the run

Final-only logging would lose progress and warnings produced during input handling or candidate generation, and could lose useful context if a run fails. Initialize the run reporter at startup and allow stages to report operational events. Keep that reporter lightweight; a general event framework is unnecessary unless actual requirements demand it.

### Overlap inside detectors versus a selection step

Embedding all overlap behavior in each detector might appear simpler for one feature type, but it obscures the explicit cross-type priority rule. A separate selection responsibility makes the rule visible and changeable without prescribing a generic selection framework.

### Internal and output units

Carrying varied units through scientific calculations would increase conversion and comparison complexity. Converting to nm and nm² at the boundaries gives thresholds and measurements a consistent basis. The initial production input conversion supports meters and nanometers; the CSV declared unit applies to image width, row-axis length, and the height values in the matrix. The existing CSV keys `ImageHeight` and `ImageHeightPixel` describe the row-axis physical extent and its pixel count; internally these are `length_nm` and `length_pixels`. Other result-unit choices remain to be specified before output conversion is implemented.

## 9. Assumptions, risks, and open decisions

The following are not resolved by this design and must not be silently guessed during implementation:

1. **INP grammar:** Keywords, optional values, duplicate requests, malformed input behavior, and exact output-detail choices.
2. **Result units:** Units beyond the nm and nm² defaults and area conversion rules remain to be specified. Internal units are nm and nm².
3. **Reported location:** Whether each feature needs coordinates, a bounding region, or another location description.
4. **Outputs:** Exact results layout, meaning of detail levels, required plot types/content, filenames, and behavior on partial output failure.
5. **Operational behavior:** Error versus warning definitions, logfile format, handling of invalid/incomplete files, and CLI exit codes. Scientific analysis output stays off the console; CLI diagnostics and logfile setup or writing failures may be printed to standard error.
6. **Environment and validation:** Python 3.13 and later are supported; the installation environment and additional independent scientific validation datasets/tolerances remain to be specified. The approved reference cases and expected ranges are in `requirements.md`.

The largest risk is treating algorithmic choices as implementation details when they affect scientific meaning. Those choices should be documented and checked against reference data before claims of scientific correctness.

## 10. Incremental implementation sequence

1. Agree CSV and INP formats, external units, invalid-input behavior, and CLI output/exit conventions.
2. Build the production package incrementally, with explicit data passed between input, analysis, selection, reporting, and output responsibilities. Keep exploratory prototypes separate.
3. Implement request models, validation, and documented defaults; test those defaults and validation rules. Add file parsing only after its syntax is agreed.
4. Implement the approved scientific definitions and validate each feature path against the reference examples in `requirements.md`; add independent scientific reference data when supplied.
5. Implement same-type grouping and cross-type priority using 8-connectivity, the approved 80% intersection-over-union cutoff, whole-feature suppression, and feature-specific centroid-ordered outputs.
6. Add lightweight operational reporting to the CLI and pass the reporter explicitly to pipeline stages as they are implemented. Write progress, warnings, and errors to a plain-text logfile; allow CLI diagnostics and logfile failures on standard error while keeping scientific analysis output off the console.
7. Add results output once sufficient analysis data is available, including the logfile location and optional operational details; then add requested plots.
8. Run end-to-end CLI checks and compare scientific outputs to the supplied reference data.
9. Add or refine modules only where implemented responsibilities or independent testing needs justify those boundaries.

This sequence is incremental: input/output contracts can be established early, while scientific rules remain explicit decisions rather than assumptions hidden in code.
