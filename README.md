# AFM Analysis

AFM Analysis is a Python command-line program for finding and measuring trenches, bumps, and pits in two-dimensional atomic force microscopy (AFM) height data. It reads a CSV height table and writes a text results file, a log file, and optionally an overview plot.

The project supports Python 3.13 and later. Its scientific calculations are being developed against documented reference cases; passing software tests does not establish that results are scientifically valid for every instrument, sample, or dataset.

## Features

- Reads a two-dimensional height matrix and metadata from a CSV file.
- Detects trenches, bumps, and pits using the implemented analysis methods.
- Reports feature measurements in nanometers (nm) and projected areas in square nanometers (nm²).
- Writes a plain-text results file and an operational log; can also write an overview PNG plot.
- Provides a command-line interface named `afm-analysis`.

## Requirements

- Python 3.13 or later.
- An input CSV file following the format described below.

## Install from a source checkout

Clone the repository and change into its directory:

```bash
git clone https://github.com/cchibueze/afm-analyser.git
cd afm-analyser
```

Install the program and its runtime dependencies:

```bash
python -m pip install .
```

For development, install the test and lint tools as well:

```bash
python -m pip install -e ".[dev]"
```

The editable install makes code changes in the checkout available without reinstalling. It is intended for development; `python -m pip install .` installs the package from the checkout as a regular package.

## Input CSV format

The CSV file begins with metadata comment rows, followed by a comma-separated numeric height matrix. Required metadata keys are:

- `ImageWidth`: physical extent along the matrix columns.
- `ImageHeight`: physical extent along the matrix rows.
- `ImageWidthPixel`: number of matrix columns.
- `ImageHeightPixel`: number of matrix rows.
- `ImageDataUnit`: `m` or `nm`; this unit applies to both physical extents and every height value.

Metadata rows use `# Key,value` form. Blank lines and comment rows may appear before the matrix starts. The first non-comment data row begins the matrix; comments are not allowed after that point. The matrix dimensions must match the declared pixel counts, and each pixel count must be at least two. Physical extents span the first through last grid points, so pixel pitch is calculated as extent divided by pixel count minus one.

Example:

```csv
# ImageWidth,4.0e-7
# ImageHeight,4.0e-7
# ImageWidthPixel,3
# ImageHeightPixel,3
# ImageDataUnit,m
0,0,0
0,1.0e-8,0
0,0,0
```

This example has three rows and three columns. Its extents and height values are expressed in meters.

## Run an analysis

Analyze trenches with the documented default thresholds (5 nm depth, 3 nm width, and 6 nm length):

```bash
afm-analysis --path data/two-trenches.csv
```

By default, trenches are selected. To analyze more feature types, name them with `--features` and provide any threshold overrides you need:

```bash
afm-analysis \
  --path data/bump.csv \
  --features bump \
  --bump-height-nm 4 \
  --bump-diameter-nm 4
```

Feature selection accepts `trench`, `bump`, and `pit`, separated by commas. The available threshold options are:

| Feature | Options | Defaults |
| --- | --- | --- |
| Trench | `--trench-depth-nm`, `--trench-width-nm`, `--trench-length-nm` | 5 nm depth, 3 nm width, 6 nm length |
| Bump | `--bump-height-nm`, `--bump-diameter-nm` | 4 nm height, 4 nm diameter |
| Pit | `--pit-depth-nm`, `--pit-diameter-nm` | 4 nm depth, 4 nm diameter |

Trench length must be at least 1.5 times its width. Thresholds for a feature require that feature to be selected. For example, `--pit-depth-nm` requires `--features pit` (or a feature list that includes `pit`).

The results file defaults to `results/output`. Choose a different file path with `--output`. The program also writes a log file under `results/` using the output filename stem; `--plot` writes an overview PNG there as well. For example:

```bash
afm-analysis \
  --path data/two-trenches.csv \
  --output results/two-trenches.txt \
  --plot
```

This writes `results/two-trenches.txt`, `results/two-trenches.log`, and `results/two-trenches.png`. Add `--include-details` to include operational log details in the results file. On a successful run, scientific analysis is written to files rather than printed to the console. Errors are reported on standard error, and the program returns a nonzero exit status when a run fails.

To see every command-line option:

```bash
afm-analysis --help
```

## Tests and code checks

Install the development tools and run the checks locally:

```bash
python -m pip install -e ".[dev]"
pytest
ruff check .
```

GitHub Actions runs pytest and Ruff for Python 3.13 and 3.14 on pushes to `main` and pull requests targeting `main`. The tests check implemented software behavior and the included reference cases; they do not establish scientific correctness beyond the data and expectations being tested.

## Current limitations

- Input is the documented general CSV height-table format; vendor-specific AFM exports are not supported automatically.
- Operator settings are supplied through command-line options. `.inp` request-file parsing is not implemented.
- Results currently use nm and nm²; choosing alternate result units is not implemented.
- An overview plot is available, but configurable plot types and output-detail levels are not implemented.
- The documented scientific reference cases provide bounded checks, not validation across all AFM instruments or datasets.

## Project documents

- [`requirements.md`](requirements.md) describes product requirements and scientific reference expectations.
- [`design.md`](design.md) describes the initial software design and planned boundaries.
