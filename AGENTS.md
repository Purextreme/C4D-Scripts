# Repository Guidelines

## Project Structure & Module Organization

This repository contains personal Cinema 4D production tools, targeting Cinema 4D 2024.5.1. Custom scripts usually live at the repository root as standalone `.py` files, for example `Transform_ResetPSR.py`, `Import_BatchSVGAssets.py`, and `Select_SimilarMeshObjects.py`.

Update `README.md` when adding or renaming a maintained script.

## Build, Test, and Development Commands

There is no build step. Scripts are loaded directly by Cinema 4D from `library/scripts/MyC4DScripts`.

- `py -3.12 -m py_compile .\ScriptName.py` checks Python syntax without launching Cinema 4D.
- `git status --short` reviews local changes before committing.
- Refresh scripts in Cinema 4D, or restart Cinema 4D, to test menu and Script Manager behavior.

## Coding Style & Naming Conventions

Use Python with the Cinema 4D `c4d` API. Prefer small, single-purpose scripts that run from the Script Manager without extra setup. Simple top-level flow is acceptable for short utilities; use functions when logic grows.

Use 4-space indentation. Keep file names descriptive and user-facing. Script file names should be English and use a category prefix pattern such as `Select_`, `CleanUp_`, `Display_`, `Import_`, `Spline_`, `Material_`, `Transfer_`, `Analyze_`, `Group_`, `Animate_`, or `Transform_`. Avoid spaces and Chinese characters in script file names. Keep comments brief, especially around C4D API behavior or scene mutations.

## Testing Guidelines

No automated test suite is currently present. At minimum, run `py_compile` on edited scripts. Behavioral testing should happen inside Cinema 4D 2024.5.1 on a disposable scene or copied production file. Verify selection handling, hierarchy changes, material/tag creation, and whether `c4d.EventAdd()` is required.

## Commit & Pull Request Guidelines

Recent commits use short imperative messages such as `Update README script index` and `Add similar mesh grouper script`. Follow that style: start with `Add`, `Update`, `Fix`, or `Remove`, and name the affected script or workflow.

Pull requests should include a concise description, scripts changed, manual Cinema 4D verification, and scene assumptions. Include screenshots or before/after notes for visual, selection, hierarchy, or material changes.

## Agent-Specific Instructions

Before editing, check for existing user changes and avoid unrelated cleanup. Do not reintroduce `.tif` icon files or overwrite user-modified scripts unless the request specifically asks for it.
