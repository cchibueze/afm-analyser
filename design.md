# AFM Surface Feature Analysis — Initial Software Design

## 1. Purpose and scope

This document describes the initial software design for the requirements in `requirements.md`. It covers a command-line Python program that reads a general AFM height-table CSV and an operator request file, analyzes a 2D height grid, and writes requested results and operational outputs.

The initial scope is trenches, pits, and bumps. A GUI, 3D or stacked-wafer data, confidence values, vendor-specific input formats, and a general plugin system are outside the initial design.

The design intentionally leaves the scientific definitions and algorithms that are unresolved in the requirements open. These include exact feature boundaries, local reference-surface selection, measurement methods, and partial-overlap behavior. Those decisions require scientific definitions and reference data before implementation can be considered validated.

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
| Candidate analysis | Detecting requested feature candidates and measuring required properties according to agreed scientific rules. | CSV/INP syntax, logfile paths, and report formatting. |
| Overlap selection | Grouping overlapping candidates of the same type and resolving cross-type overlaps using the agreed rule. | Candidate generation or result serialization. |
| Results and plots | Writing type-indexed features, counts, measurements, calculation choices, logfile location, optional operational details, and requested plots. | Recomputing scientific measurements. |

Do not introduce a general detector interface, plugin registry, dependency-injection mechanism, or multiple output backends without a concrete requirement. If the feature algorithms become substantial, they can be separated into functions or modules while retaining the data boundaries described below.

## 4. Principal data and interfaces

The following are conceptual values passed between stages. Their final Python representation and exact fields depend on the file-format and scientific decisions that remain open.

- **Image data:** a 2D height grid plus measurement metadata describing pixel dimensions, physical dimensions, and stated units. Analysis receives calibrated physical spacing and heights in nm.
- **Parsed request:** operator-specified feature types, thresholds, result units, detail level, plot request, and whether operational details should also appear in the results file.
- **Effective request:** validated request with documented defaults applied. Thresholds are represented in nm; area thresholds, if introduced by later approved requirements, would use nm². Bump and pit thresholds have separate models so their fields and behavior can evolve independently.
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

The results file is written when sufficient analysis data is available. The logfile is written during the run, so operational information is preserved even if later analysis or output fails. The program shall not print analysis output to the console. CLI exit behavior and any non-analysis diagnostics remain to be specified.

## 6. Scientific analysis and overlap rules

Candidate analysis owns the scientific logic for the requested initial feature types:

- A trench is a roughly rectangular gap substantially lower than nearby surrounding points; reported measurements are length, width, and depth.
- A bump is a locally higher region with a generally round or square-like projection; reported measurements are projected area and maximum height relative to nearby surroundings.
- A pit is a locally lower region with a projection similar to a bump; reported measurements are projected area and maximum depth relative to nearby surroundings.

The detailed rules for determining regions, surrounding points, and measurements must be agreed against scientific reference data. Software tests can check behavior against defined examples, but passing tests alone does not establish scientific correctness.

Overlap selection is a distinct responsibility because requirements define both same-type grouping and cross-type priority. Same-type overlapping candidates are treated as one entity. For overlaps between different feature types, the initial priority is trench, then pit, then bump. The exact geometric meaning of overlap, especially partial intersections, remains open. Future selection rules such as physical prominence should be considered only when specified; the initial implementation should not include speculative strategies.

## 7. Requirements coverage

| Requirement area | Design response |
|---|---|
| 2D height grid and measurement metadata (REQ-001–004) | Image data represents the calibrated 2D surface; no GUI or 3D model is included. |
| Input formats and operator choices (REQ-010–019) | Dedicated input responsibilities parse CSV and INP; request validation applies documented defaults. CSV physical dimensions and height values use the same declared unit, initially meters or nanometers. Exact syntax remains open. |
| Feature definitions and measurements (REQ-020–026) | Scientific analysis handles trench, bump, and pit candidates and their required measurements; algorithms await scientific definitions and reference data. Internal units are nm and nm², with result conversion at output. |
| Grouping and priority (REQ-030–033) | Separate overlap selection groups same-type overlap and applies trench, pit, bump priority. Partial-overlap semantics remain open. |
| Results, logs, plots, and console behavior (REQ-040–048) | Results and plots are file outputs; run reporting writes operational messages during the run; optional messages are included in results by request; no confidence values or console analysis output. |
| Workflow, machine independence, and scientific validation (REQ-050–052) | CLI orchestrates general height-table input. Tests support software behavior, while independent reference-data checks assess scientific validity. |

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

Carrying varied units through scientific calculations would increase conversion and comparison complexity. Converting to nm and nm² at the boundaries gives thresholds and measurements a consistent basis. The initial production input conversion supports meters and nanometers; the CSV declared unit applies to image width, image height, and the height matrix. Other result-unit choices remain to be specified before output conversion is implemented.

## 9. Assumptions, risks, and open decisions

The following are not resolved by this design and must not be silently guessed during implementation:

1. **CSV metadata format:** Exact fields and syntax, how metadata lines are identified, matrix validation, and how physical image width/height determine pixel spacing.
2. **INP grammar:** Keywords, optional values, duplicate requests, malformed input behavior, and exact output-detail choices.
3. **Supported units:** Initial production CSV input supports meters and nanometers, with one declared unit applying to physical image dimensions and height data. Result units beyond defaults, treatment of unknown units, and area conversion rules remain to be specified. Internal units are nm and nm².
4. **Threshold semantics:** Whether each threshold is a minimum, how equality at the threshold behaves, and whether dimensions apply to a candidate before or after grouping.
5. **Scientific definitions:** Boundary detection, local surroundings, baseline construction, trench length/width calculation, bump/pit area and extrema, and handling of distorted shapes.
6. **Overlap semantics:** How overlap is computed for regions with different boundaries, partial intersection, and whether priority suppresses a whole candidate or only its intersecting portion.
7. **Reported location:** Whether each feature needs coordinates, a bounding region, or another location description.
8. **Outputs:** Exact results layout, meaning of detail levels, required plot types/content, filenames, and behavior on partial output failure.
9. **Operational behavior:** Error versus warning definitions, logfile format, handling of invalid/incomplete files, CLI exit codes, and how to satisfy no-console-output behavior for both success and failure.
10. **Environment and validation:** Python 3.13 and later are supported; the installation environment and scientific reference datasets, expected outputs, and independent acceptance criteria remain to be specified.

The largest risk is treating algorithmic choices as implementation details when they affect scientific meaning. Those choices should be documented and checked against reference data before claims of scientific correctness.

## 10. Incremental implementation sequence

1. Agree CSV and INP formats, external units, invalid-input behavior, and CLI output/exit conventions.
2. Build the production package incrementally, with explicit data passed between input, analysis, selection, reporting, and output responsibilities. Keep exploratory prototypes separate.
3. Implement request models, validation, and documented defaults; test those defaults and validation rules. Add file parsing only after its syntax is agreed.
4. Agree scientific definitions and reference examples. Implement one feature path at a time, validating measurements against those references.
5. Implement same-type grouping and cross-type priority after overlap semantics and examples are agreed.
6. Add results and logfile output, with operational reporting active throughout the run; then add optional results details and requested plots.
7. Run end-to-end CLI checks and compare scientific outputs to the supplied reference data.
8. Add or refine modules only where implemented responsibilities or independent testing needs justify those boundaries.

This sequence is incremental: input/output contracts can be established early, while scientific rules remain explicit decisions rather than assumptions hidden in code.
