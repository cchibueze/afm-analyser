"""Plot selected AFM features over the measured height grid."""

from __future__ import annotations

from pathlib import Path

from afm_analysis.models import ImageData, SelectedCandidates


def write_overview_plot(
    path: str | Path, image: ImageData, selected: SelectedCandidates
) -> None:
    """Write a PNG height map with selected feature footprints and labels."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots()
    axis.imshow(image.heights_nm, cmap="viridis", origin="upper")
    styles = (
        ("Trench", selected.trenches, "red"),
        ("Pit", selected.pits, "cyan"),
        ("Bump", selected.bumps, "magenta"),
    )
    for name, features, color in styles:
        for index, feature in enumerate(features, start=1):
            axis.contour(feature.footprint, levels=[0.5], colors=[color], linewidths=0.8)
            axis.annotate(
                f"{name} {index}",
                (feature.centroid_x_pixel, feature.centroid_y_pixel),
                color="white",
                fontsize=7,
                ha="center",
            )
    axis.set_xlabel("X pixel")
    axis.set_ylabel("Y pixel")
    figure.tight_layout()
    plot_path = Path(path)
    temporary_path = plot_path.with_suffix(".tmp.png")
    try:
        figure.savefig(temporary_path, format="png", dpi=150)
        temporary_path.replace(plot_path)
    finally:
        plt.close(figure)
        temporary_path.unlink(missing_ok=True)
