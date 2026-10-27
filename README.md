# Shader Creator for Maya

Shader Creator is an Autodesk Maya tool that builds PBR materials from a set of texture files in a few clicks. It supports **Arnold** (`aiStandardSurface`) and **V-Ray** (`VRayMtl`) from one window. It scans a folder for the textures that belong to a material, builds the shading network, and assigns the result to your selected geometry.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [The Interface](#the-interface)
- [How Texture Detection Works](#how-texture-detection-works)
- [What Gets Built](#what-gets-built)
- [Replacing an Existing Material](#replacing-an-existing-material)
- [Running Without the Shelf Button](#running-without-the-shelf-button)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)
- [Project Files](#project-files)
- [License](#license)

## Features

- **Dual engine support:** Arnold and V-Ray from a single window, switchable from a dropdown. The tool opens on the engine matching your current render settings.
- **Texture set detection:** Pick one texture and the tool finds every texture in that folder that shares its name prefix, then offers them in a dropdown on each channel.
- **UDIM support:** Numbered tile sequences (`.1001.`, `.1002.`, ...) are collapsed into one `<UDIM>` entry, and the file node is set to UDIM tiling mode.
- **Full PBR channel set:** Base Color, Ambient Occlusion, Roughness, Metalness, Specular Weight, Opacity, Normal and Displacement, plus the advanced slots Transmission, Subsurface, Emission, Sheen and Coat.
- **Correct color spaces:** Color maps (base color and the optional color maps in the advanced slots) are set to `sRGB`. Data maps (roughness, metalness, normal, etc.) are set to `Raw`.
- **Optional utility nodes:** Per-channel toggles add range/remap nodes and color-correction nodes.
- **Shared UV placement:** All file nodes in a material share one `place2dTexture` node.
- **Material replacement:** Can rebuild an existing material under the same name and clean up the old network, while protecting Maya's default shaders.
- **Safety checks:** Warns if the selected engine's plug-in is not loaded, or if it differs from the active renderer in Render Settings. It never changes your Render Settings.

## Requirements

- Autodesk Maya with Python 3 (Maya 2022 or later). The script uses f-strings and dockable `workspaceControl` windows.
- For Arnold materials: the **Arnold for Maya (`mtoa`)** plug-in loaded.
- For V-Ray materials: the **V-Ray for Maya (`vrayformaya`)** plug-in loaded.

You only need the plug-in for the engine you actually use. Load it from **Windows > Settings/Preferences > Plug-in Manager**.

## Installation

1. Download or clone this repository and keep `install.mel`, `ShaderCreator.py` and `icon.png` together in the same folder.
2. Drag and drop `install.mel` into the Maya viewport (or open it in the Script Editor and run it).
3. The installer:
   - copies `ShaderCreator.py` into your Maya user scripts folder,
   - copies the icon into your Maya preferences `icons` folder,
   - adds a **Shader Creator** button to the **Custom** shelf (creating the shelf if needed), replacing any older button from a previous version.
4. A confirmation dialog appears when it finishes. Click the shelf button to launch the tool.

Installing again is safe and is also how you update: re-run `install.mel` from the newer download and restart Maya, or reload the module, so Maya picks up the new script.

## Quick Start

1. Select the mesh(es) to receive the material.
2. Click **Shader Creator** on the Custom shelf.
3. Choose the **Render Engine** (Arnold or V-Ray).
4. Type a material name, or tick **Use current material name** to reuse the name of the material already on the selection.
5. Click **Detect Materials** and pick any one texture from your set.
6. On each channel you want, choose the matching file from its dropdown.
7. Click **Create Material**.

## The Interface

### Top section

| Control | What it does |
| --- | --- |
| **Render Engine** | Switches between Arnold and V-Ray. Labels, utility options and advanced section names update to match. |
| **Name Your Material** | Name for the new shader. If left empty you are asked whether to continue with a default name (`ArnoldMat` or `VRayMat`). |
| **Use current material name** | Reuses the name of the material currently assigned to the selection and disables the name field. |
| **Target Material** | Appears when the selection already has materials. Choose which one the new material replaces. |
| **Delete old material and textures** | Removes the replaced material's network once nothing uses it any more. On by default. |
| **Detect Materials** | Opens a file browser and scans the chosen texture's folder for the rest of the set. |
| **Material Detected** | Shows the name prefix the tool derived from the chosen file. |

### Texture channels

Each channel has a dropdown (filled after detection), a file path field with a browse button for choosing a file manually, and an **X** button to clear it. Channels left empty are skipped.

| Channel | Optional toggle |
| --- | --- |
| Base Color | Use Color Correct (Arnold) / Use VRayColorCorrection (V-Ray) |
| Ambient Occlusion | Use Range (Arnold) / Use Remap (V-Ray) |
| Roughness | Use Range / Use Remap |
| Metalness | Use Range / Use Remap |
| Specular Weight | Use Range / Use Remap |
| Opacity | Use Range / Use Remap |
| Normal | none |
| Displacement | Use Range / Use Remap (off by default) |

### Advanced sections

Collapsed by default. Each has a **Weight Map**, and some have extra options.

| Section (Arnold) | Section (V-Ray) | Extras |
| --- | --- | --- |
| Transmission | Refraction | Separate color texture |
| Subsurface | Translucency / SSS | Separate color texture |
| Emission | Self-Illumination | Separate color texture |
| Sheen | Sheen | Separate color texture, separate roughness texture |
| Coat | Coat | Separate color texture, separate roughness texture |

Ticking **Use separate color texture** or **Use separate roughness texture** reveals an extra map field for that slot.

### Other

- **Auto-refresh UI after material creation** clears all fields after a successful build, ready for the next material. On by default.
- **Edit > Refresh UI** clears every field manually.
- A small signature line sits at the bottom of the window.

## How Texture Detection Works

After you pick a file, the tool takes the file name without its extension and looks for the first of these channel keywords, preceded by `_` or `.`:

`basecolor`, `diffuse`, `albedo`, `roughness`, `rough`, `metalness`, `metallic`, `metal`, `normal`, `nrm`, `height`, `displacement`, `disp`, `opacity`, `alpha`, `ao`, `ambientocclusion`, `specular`

Everything before that keyword is the material prefix. If no keyword matches, the part before the last underscore is used instead.

For example, `Brick_Wall_basecolor.1001.png` gives the prefix `Brick_Wall`.

The tool then lists every file in the same folder that starts with that prefix and has one of these extensions: `.jpg`, `.jpeg`, `.png`, `.tga`, `.exr`, `.tif`, `.tiff`, `.hdr`.

You still choose which file goes on which channel using the dropdowns. Nothing is assigned to a channel until you select it.

**Tips**

- Keep each material's textures in a folder with a shared prefix.
- Use the browse button on any channel if a file lives elsewhere.
- For UDIMs, the tile number must be a four-digit number from 1001 up in the file name, such as `name.1001.png`.

## What Gets Built

### Arnold (`aiStandardSurface`)

| Channel | Network |
| --- | --- |
| Base Color | file (sRGB) > optional `aiColorCorrect` > `baseColor` |
| Ambient Occlusion | file > optional `aiRange` > multiplied into base color with `aiLayerRgba` |
| Roughness | file > optional `aiRange` > `specularRoughness` |
| Metalness | file > optional `aiRange` > `metalness` |
| Specular Weight | file > optional `aiRange` > `specular` |
| Opacity | file > optional `aiRange` > `opacity` |
| Normal | file > `aiNormalMap` > `normalCamera` |
| Displacement | file > optional `aiRange` > `displacementShader` (scale 0.005, zero value 0.5) |
| Transmission, Subsurface, Emission, Sheen, Coat | weight, color and roughness maps connected to the matching `aiStandardSurface` attributes |

### V-Ray (`VRayMtl`)

The material is set up with GGX reflections using roughness (`brdfType` 3, `useRoughness` on) and white reflection color, so the maps below control it.

| Channel | Network |
| --- | --- |
| Base Color | file (sRGB) > optional `VRayColorCorrection` > `color` |
| Ambient Occlusion | file > optional `remapValue` > multiplied into base color with `multiplyDivide` |
| Roughness | file > optional `remapValue` > `reflectionGlossiness` |
| Metalness | file > optional `remapValue` > `metalness` |
| Specular Weight | file > optional `remapValue` > `reflectionColorAmount` |
| Opacity | file > optional `remapValue` > `opacityMap` |
| Normal | file > `VRayNormalMap` > `bumpMap` |
| Displacement | file > optional `remapValue` > `displacementShader` (scale 0.005) |
| Refraction, Translucency / SSS, Self-Illumination, Sheen, Coat | weight, color and glossiness maps connected to the matching `VRayMtl` attributes |

Notes:

- For Subsurface / Translucency, when a weight map is used and no separate color map is given, the base color network is also fed into the subsurface color.
- With V-Ray, subsurface sets the translucency mode to SSS when the attribute is available.
- Self-Illumination multiplies the color by the weight map when both are present.

## Replacing an Existing Material

If your selection already has a material, it appears in **Target Material**.

- The new material is assigned to **every object using the old material**, not only the objects you selected.
- If **Delete old material and textures** is on, the old shading network is removed once nothing uses it.
- If the new name matches the old material's name, the old one is renamed or removed first so the new material can keep the name.
- Maya's built-in shaders (`lambert1`, `standardSurface1`, `particleCloud1` and similar, plus OpenPBR materials) are never deleted.
- With no existing material (or an unused one), the new material is assigned to your selected meshes.

## Running Without the Shelf Button

From the Maya Script Editor (Python tab), after installing:

```python
import ShaderCreator
ShaderCreator.create_shader_creator_ui()        # opens on the engine matching your renderer
ShaderCreator.create_ai_shader_ui()             # opens set to Arnold
ShaderCreator.create_vray_shader_ui()           # opens set to V-Ray
```

While developing, reload after editing the file:

```python
import importlib, ShaderCreator
importlib.reload(ShaderCreator)
ShaderCreator.create_shader_creator_ui()
```

## Troubleshooting

| Problem | Likely cause and fix |
| --- | --- |
| "Plugin Warning" dialog | The plug-in for the selected engine is not loaded. Enable `mtoa` (Arnold) or `vrayformaya` (V-Ray) in the Plug-in Manager. |
| "Render Engine Warning" dialog | Render Settings use a different renderer than the engine you picked. The material is still created. Change Render Settings yourself if needed. |
| "Selection Warning" dialog | No mesh is selected. Select at least one mesh first. |
| Dropdowns are empty after Detect Materials | No file in that folder starts with the detected prefix, or the extensions are not in the supported list. Use the browse button on each channel instead. |
| Wrong prefix detected | The file name has no recognized channel keyword. Rename the files so a keyword follows `_` or `.`, or pick maps manually. |
| UDIM not recognized | The tile number must be four digits starting at 1001. Check the naming pattern. |
| New script version not showing | Restart Maya or reload the `ShaderCreator` module after re-running `install.mel`. |
| Shelf button missing | Run `install.mel` again. The button is added to the **Custom** shelf. |

## Uninstallation

Drag and drop `uninstall.mel` into the Maya viewport, or run it from the Script Editor. It removes the installed script and icon, removes the shelf button, and closes the tool window if it is open.

## Project Files

| File | Purpose |
| --- | --- |
| `ShaderCreator.py` | The tool: interface and material-building logic. |
| `install.mel` | Installer: copies files and adds the shelf button. |
| `uninstall.mel` | Remover: deletes installed files and the shelf button. |
| `icon.png` | Shelf button icon. |
| `LICENSE` | MIT License text. |

## License

Released under the [MIT License](LICENSE).
