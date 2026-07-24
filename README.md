# Shader Creator for Maya

Shader Creator is a powerful Autodesk Maya tool designed to automate the process of creating PBR materials for **Arnold** (`aiStandardSurface`) and **V-Ray** (`VRayMtl`). It saves you time by automatically detecting texture maps, creating the necessary shading networks, and assigning them to your selected geometry.

## Features

- **Dual Engine Support:** Creates materials for both Arnold and V-Ray from a single unified interface.
- **Auto-Detection:** Simply select one texture map, and the tool will auto-detect the rest of the PBR texture set based on naming conventions (e.g., `_basecolor`, `_roughness`, `_normal`, etc.).
- **UDIM Support:** Automatically detects and configures UDIM sequences (`<UDIM>` / `1001`).
- **Comprehensive PBR Channels:** Supports Base Color, Ambient Occlusion, Roughness, Metalness, Specular Weight, Opacity, Normal, Displacement, Transmission, Subsurface, Emission, Sheen, and Coat.
- **Advanced Node Networks:** Automatically creates and connects `place2dTexture` nodes, handles color space settings (e.g., `sRGB` vs `Raw`), and sets `alphaIsLuminance` correctly.
- **Utility Node Integration:** Optionally adds and connects `aiRange` / `remapValue` nodes for value remapping and `aiColorCorrect` / `VRayColorCorrection` nodes for color tweaking.
- **Smart Cleanup:** Option to cleanly replace and delete old materials without affecting protected Maya default shaders.

## Installation

1. Drag and drop the `install.mel` file into the Maya viewport.
2. A confirmation dialog will appear, and a **Shader Creator** icon will be added to your **Custom** shelf.
3. Click the shelf button to launch the UI.

*Alternatively, you can manually run the `install.mel` script in the Maya Script Editor.*

## Usage

1. Select the mesh(es) you want to apply the new material to.
2. Click the **Shader Creator** button in your Custom shelf.
3. Select your target render engine (Arnold or V-Ray) from the dropdown.
4. Name your material or choose to use the current material's name.
5. Click **Detect Materials** and select any texture file from your PBR set. The tool will automatically find and assign the other maps in the same folder.
6. Check or uncheck utility nodes (e.g., Use Range, Use Color Correct) next to each map as needed.
7. Click **Create Material**.

## Uninstallation

To completely remove the tool, drag and drop the `uninstall.mel` file into the Maya viewport, or run it via the Script Editor. This will cleanly remove the script files, icons, and shelf buttons.

## Requirements

- Autodesk Maya (tested with recent versions)
- Arnold (mtoa) plugin OR V-Ray (vrayformaya) plugin loaded in the Plug-in Manager.
