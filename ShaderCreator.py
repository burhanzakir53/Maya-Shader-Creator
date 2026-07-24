import maya.cmds as cmds
import os
import re

# ======================================================
# CONSTANTS & GLOBAL STATE
# ======================================================
CHANNEL_KEYWORDS = [
    "basecolor", "diffuse", "albedo", "roughness", "rough", "metalness", 
    "metallic", "metal", "normal", "nrm", "height", "displacement", 
    "disp", "opacity", "alpha", "ao", "ambientocclusion", "specular"
]
VALID_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.tga', '.exr', '.tif', '.tiff', '.hdr')
ENGINE_ARNOLD = "Arnold"
ENGINE_VRAY = "V-Ray"

RENDER_ENGINES = {
    ENGINE_ARNOLD: {
        "title": "AI Standard Surface Builder",
        "default_material": "ArnoldMat",
        "renderer_names": ("arnold",),
        "plugin_names": ("mtoa", "mtoa.mll"),
        "plugin_label": "Arnold / MtoA",
    },
    ENGINE_VRAY: {
        "title": "V-Ray Material Builder",
        "default_material": "VRayMat",
        "renderer_names": ("vray", "vrayrenderer"),
        "plugin_names": ("vrayformaya", "vrayformaya.mll"),
        "plugin_label": "V-Ray for Maya",
    },
}
SECTION_KEYS = ["transmission", "subsurface", "emission", "sheen", "coat"]
SECTION_LABELS = {
    ENGINE_ARNOLD: {
        "transmission": "Transmission",
        "subsurface": "Subsurface",
        "emission": "Emission",
        "sheen": "Sheen",
        "coat": "Coat",
    },
    ENGINE_VRAY: {
        "transmission": "Refraction",
        "subsurface": "Translucency / SSS",
        "emission": "Self-Illumination",
        "sheen": "Sheen",
        "coat": "Coat",
    },
}

LAST_BROWSE_DIR = None
CURRENT_ENGINE = ENGINE_ARNOLD
SUPPRESS_ENGINE_CHANGE = False
ENGINE_DROPDOWN = None
MATERIAL_DROPDOWN = None
DELETE_OLD_TOGGLE = None
USE_CURRENT_NAME_TOGGLE = None
AUTO_REFRESH_TOGGLE = None
DETECTED_MAT_LABEL = None 
MASTER_PATH_HIDDEN = None 
UI_REFS = {}

# ======================================================
# HELPERS - MATERIAL QUERY & CLEANUP
# ======================================================

def get_materials_from_selection():
    """Returns unique materials assigned to currently selected objects."""
    mats = []
    shapes = cmds.ls(sl=True, dag=True, type='mesh', long=True) or []
    for shape in shapes:
        sgs = cmds.listConnections(shape, type="shadingEngine") or []
        for sg in sgs:
            shaders = cmds.listConnections(f"{sg}.surfaceShader") or []
            for sh in shaders:
                if sh not in mats:
                    mats.append(sh)
    return mats

def update_material_dropdown(*args):
    """Refreshes the target material dropdown based on selection context."""
    global MATERIAL_DROPDOWN
    if not MATERIAL_DROPDOWN or not cmds.optionMenu(MATERIAL_DROPDOWN, exists=True):
        return
        
    cmds.optionMenu(MATERIAL_DROPDOWN, e=True, dai=True)
    mats = get_materials_from_selection()
    
    if not mats:
        cmds.menuItem(label="No material detected", parent=MATERIAL_DROPDOWN)
        cmds.optionMenu(MATERIAL_DROPDOWN, e=True, enable=False, visible=False)
        return

    cmds.optionMenu(MATERIAL_DROPDOWN, e=True, visible=True)
    for m in mats:
        cmds.menuItem(label=m, parent=MATERIAL_DROPDOWN)
    cmds.optionMenu(MATERIAL_DROPDOWN, e=True, enable=(len(mats) >= 1))

def delete_shading_network(material):
    """Safely deletes a shading network while protecting default Maya materials."""
    if not cmds.objExists(material): return
    protected_mats = {"lambert1", "particleCloud1", "standardSurface1"}
    if material in protected_mats or "openPBR" in material: return
    
    sgs = cmds.listConnections(material, type="shadingEngine") or []
    nodes = set(cmds.listHistory(material, pruneDagObjects=True) or [])
    for sg in sgs:
        nodes.update(cmds.listHistory(sg, pruneDagObjects=True) or [])
        nodes.add(sg)
        
    global_protected = {"lambert1", "initialShadingGroup", "initialParticleSE", "particleCloud1"}
    nodes = [n for n in nodes if n not in global_protected and "openPBR" not in n]
    
    if nodes:
        try: cmds.delete(nodes)
        except Exception: pass

# ======================================================
# AUTO-DETECTION LOGIC
# ======================================================

def on_detect_materials_clicked(tex_fields, advanced):
    """Populates dropdowns based on chosen file prefix."""
    global LAST_BROWSE_DIR, MASTER_PATH_HIDDEN
    start_dir = LAST_BROWSE_DIR if LAST_BROWSE_DIR and os.path.exists(LAST_BROWSE_DIR) else (cmds.workspace(q=True, rd=True))
    path = cmds.fileDialog2(fileMode=1, startingDirectory=start_dir)
    
    if not path: return
    
    full_path = path[0]
    MASTER_PATH_HIDDEN = full_path 
    LAST_BROWSE_DIR = os.path.dirname(full_path)
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    
    name_no_ext = os.path.splitext(filename)[0]
    prefix = name_no_ext
    for kw in CHANNEL_KEYWORDS:
        match = re.search(f"[._]{kw}", name_no_ext, re.IGNORECASE)
        if match:
            prefix = name_no_ext[:match.start()]
            break
    if prefix == name_no_ext and "_" in name_no_ext: prefix = name_no_ext.rsplit("_", 1)[0]

    if not prefix:
        cmds.warning("Could not detect a material prefix from filename. Using full name.")
        prefix = name_no_ext

    cmds.text(DETECTED_MAT_LABEL, e=True, label=f"Material Detected:  {prefix}", fn="boldLabelFont")
    
    all_files = [f for f in os.listdir(directory) if f.startswith(prefix) 
                 and os.path.isfile(os.path.join(directory, f)) 
                 and f.lower().endswith(VALID_EXTENSIONS)]
    
    unique_maps = []
    seen_bases = set()
    for f in all_files:
        base_name = re.sub(r'\.1\d{3}\.', '.<UDIM>.', f)
        if base_name not in seen_bases:
            unique_maps.append(base_name)
            seen_bases.add(base_name)

    unique_maps.sort() # Ensure alphabetical order for user

    def update_dropdown(field_data):
        if "drop" not in field_data: return
        drop = field_data["drop"]
        cmds.optionMenu(drop, e=True, dai=True)
        cmds.menuItem(label="-- Select Map --", parent=drop)
        for label in unique_maps: cmds.menuItem(label=label, parent=drop)

    for key in tex_fields: update_dropdown(tex_fields[key])
    for key, data in advanced.items():
        for drop_key in ["weight_drop", "color_drop", "roughness_drop"]:
            if drop_key in data: update_dropdown({"drop": data[drop_key]})

def on_dropdown_change(value, text_field):
    global MASTER_PATH_HIDDEN
    if value == "-- Select Map --" or not MASTER_PATH_HIDDEN:
        cmds.textField(text_field, e=True, text="")
        return
    directory = os.path.dirname(MASTER_PATH_HIDDEN)
    actual_file = value.replace(".<UDIM>.", ".1001.")
    cmds.textField(text_field, e=True, text=os.path.join(directory, actual_file))

# ======================================================
# UI HELPERS & REFRESH
# ======================================================

def refresh_all_fields(tex_fields, advanced, material_name_field):
    """Resets all fields and collapses frames to default state."""
    global MASTER_PATH_HIDDEN, USE_CURRENT_NAME_TOGGLE
    for key, f in tex_fields.items():
        if isinstance(f, dict):
            cmds.textField(f["path"], e=True, text="")
            if "drop" in f: 
                cmds.optionMenu(f["drop"], e=True, dai=True)
                cmds.menuItem(label="-- Select Map --", parent=f["drop"])
            if "range" in f: cmds.checkBox(f["range"], e=True, v=(False if key == "displacement" else True))
            if "cc" in f: cmds.checkBox(f["cc"], e=True, v=True)
        else: cmds.textField(f, e=True, text="")

    for data in advanced.values():
        if "frame" in data: cmds.frameLayout(data["frame"], e=True, cl=True)
        for f_key in ["weight", "color", "roughness"]:
            if f_key in data: cmds.textField(data[f_key], e=True, text="")
        for d_key in ["weight_drop", "color_drop", "roughness_drop"]:
            if d_key in data: 
                cmds.optionMenu(data[d_key], e=True, dai=True)
                cmds.menuItem(label="-- Select Map --", parent=data[d_key])
        if "weight_range" in data: cmds.checkBox(data["weight_range"], e=True, v=True)
        if "color_cc" in data: cmds.checkBox(data["color_cc"], e=True, v=True)
        if "rough_range" in data: cmds.checkBox(data["rough_range"], e=True, v=True)
        if "use_sep" in data: cmds.checkBox(data["use_sep"], e=True, v=False)
        if "color_col" in data: cmds.columnLayout(data["color_col"], e=True, visible=False)
        if "use_sep_r" in data: cmds.checkBox(data["use_sep_r"], e=True, v=False)
        if "rough_col" in data: cmds.columnLayout(data["rough_col"], e=True, visible=False)

    cmds.textField(material_name_field, e=True, text="", enable=True)
    if USE_CURRENT_NAME_TOGGLE and cmds.checkBox(USE_CURRENT_NAME_TOGGLE, exists=True):
        cmds.checkBox(USE_CURRENT_NAME_TOGGLE, e=True, v=False)
    MASTER_PATH_HIDDEN = None
    cmds.text(DETECTED_MAT_LABEL, e=True, label="Material Detected: None")
    cmds.inViewMessage(amg="UI Cleared", pos="midCenter", fade=True)

def browse_file(field):
    global LAST_BROWSE_DIR
    start_dir = LAST_BROWSE_DIR if LAST_BROWSE_DIR and os.path.exists(LAST_BROWSE_DIR) else (cmds.workspace(q=True, rd=True))
    path = cmds.fileDialog2(fileMode=1, startingDirectory=start_dir)
    if path:
        cmds.textField(field, e=True, text=path[0])
        LAST_BROWSE_DIR = os.path.dirname(path[0])

def get_path(field):
    if not field: return None
    p = cmds.textField(field, q=True, text=True)
    return p if p and os.path.exists(p) else None

def set_node_editors_connected_view():
    """Use Maya's second Node Editor detail level for generated utility nodes."""
    editors = set()

    try:
        import maya.mel as mel
    except Exception:
        mel = None

    if mel:
        for command in ("getCurrentNodeEditor", "getCurrentNodeEditor()"):
            try:
                current_editor = mel.eval(command)
                if current_editor:
                    editors.add(current_editor)
                    break
            except Exception:
                pass

        for panel in cmds.getPanel(scriptType="nodeEditorPanel") or []:
            try:
                editor = mel.eval('editorNameFromPanel "{0}"'.format(panel))
                if editor:
                    editors.add(editor)
            except Exception:
                pass

    for editor in ("hyperShadePrimaryNodeEditor", "nodeEditorPanel1NodeEditorEd"):
        editors.add(editor)

    for editor in editors:
        try:
            if cmds.nodeEditor(editor, exists=True):
                cmds.nodeEditor(editor, e=True, nodeViewMode="connected")
        except Exception:
            pass

def defer_node_editors_connected_view():
    set_node_editors_connected_view()
    try:
        cmds.evalDeferred("import ShaderCreator; ShaderCreator.set_node_editors_connected_view()", lowestPriority=True)
    except Exception:
        pass

def normalize_engine(engine):
    return engine if engine in RENDER_ENGINES else ENGINE_ARNOLD

def get_current_renderer():
    try:
        return cmds.getAttr("defaultRenderGlobals.currentRenderer")
    except Exception:
        return None

def get_renderer_label(renderer):
    if not renderer:
        return "Unknown"
    renderer_key = renderer.lower()
    for engine, config in RENDER_ENGINES.items():
        if renderer_key in config["renderer_names"]:
            return engine
    return renderer

def get_engine_from_current_renderer():
    renderer = get_current_renderer()
    if not renderer:
        return ENGINE_ARNOLD
    renderer_key = renderer.lower()
    for engine, config in RENDER_ENGINES.items():
        if renderer_key in config["renderer_names"]:
            return engine
    return ENGINE_ARNOLD

def renderer_matches_engine(engine):
    renderer = get_current_renderer()
    if not renderer:
        return True
    return renderer.lower() in RENDER_ENGINES[engine]["renderer_names"]

def plugin_loaded(plugin_names):
    for plugin_name in plugin_names:
        try:
            if cmds.pluginInfo(plugin_name, q=True, loaded=True):
                return True
        except Exception:
            pass
    return False

def get_plugin_warning_message(engine):
    engine = normalize_engine(engine)
    config = RENDER_ENGINES[engine]
    if plugin_loaded(config["plugin_names"]):
        return None
    return "{0} plugin is not installed or not loaded. Please install or enable it via Plug-in Manager before proceeding.".format(config["plugin_label"])

def get_renderer_mismatch_message(engine):
    engine = normalize_engine(engine)
    if renderer_matches_engine(engine):
        return None
    current_renderer = get_current_renderer()
    return "Render Settings currently use {0}. Selected engine is {1}.".format(
        get_renderer_label(current_renderer), engine
    )

def get_engine_warning_messages(engine):
    engine = normalize_engine(engine)
    messages = []

    renderer_message = get_renderer_mismatch_message(engine)
    plugin_message = get_plugin_warning_message(engine)
    if renderer_message:
        messages.append(renderer_message)
    if plugin_message:
        messages.append(plugin_message)

    return messages

def set_engine_dropdown_value(engine):
    global SUPPRESS_ENGINE_CHANGE
    if not ENGINE_DROPDOWN or not cmds.optionMenu(ENGINE_DROPDOWN, exists=True):
        return

    SUPPRESS_ENGINE_CHANGE = True
    try:
        cmds.optionMenu(ENGINE_DROPDOWN, e=True, value=normalize_engine(engine))
    finally:
        SUPPRESS_ENGINE_CHANGE = False

def prompt_renderer_mismatch(engine):
    engine = normalize_engine(engine)
    if renderer_matches_engine(engine):
        return True

    current_renderer = get_current_renderer()
    cmds.confirmDialog(
        title='Render Engine Warning',
        message='Render Settings currently use {0}. Selected engine is {1}.\n\nThe tool will not change Render Settings automatically.'.format(
            get_renderer_label(current_renderer), engine
        ),
        button=['OK'],
        defaultButton='OK',
        icon='warning'
    )
    return True

def update_engine_warning_label(engine):
    engine = normalize_engine(engine)

    plugin_message = get_plugin_warning_message(engine)
    if plugin_message:
        cmds.confirmDialog(
            title='Plugin Warning',
            message=plugin_message,
            button=['OK'],
            defaultButton='OK',
            icon='warning'
        )
        return None

    renderer_message = get_renderer_mismatch_message(engine)
    if renderer_message:
        prompt_renderer_mismatch(engine)

    return engine

def validate_engine_before_create(engine):
    engine = normalize_engine(engine)
    config = RENDER_ENGINES[engine]

    if not plugin_loaded(config["plugin_names"]):
        cmds.confirmDialog(
            title='Plugin Warning',
            message='{0} plugin is not installed or not loaded. Please install or enable it via Plug-in Manager before creating {1} materials.'.format(
                config["plugin_label"], engine
            ),
            button=['OK'],
            defaultButton='OK',
            icon='warning'
        )
        return False

    if not prompt_renderer_mismatch(engine):
        return False

    return True

def get_range_checkbox_label(engine):
    return "Use Remap" if normalize_engine(engine) == ENGINE_VRAY else "Use Range"

def get_color_correct_checkbox_label(engine):
    return "Use VRayColorCorrection" if normalize_engine(engine) == ENGINE_VRAY else "Use Color Correct"

def reset_ui_refs():
    global UI_REFS
    UI_REFS = {
        "workspace": "shaderCreatorWorkspace",
        "header": None,
        "range_checkboxes": [],
        "color_correct_checkboxes": [],
        "advanced_frames": {},
        "create_button": None,
        "tex_fields": None,
        "advanced": None,
        "material_name_field": None,
    }

def apply_engine_ui(engine):
    global CURRENT_ENGINE
    engine = normalize_engine(engine)
    CURRENT_ENGINE = engine
    config = RENDER_ENGINES[engine]

    workspace = UI_REFS.get("workspace")
    if workspace and cmds.workspaceControl(workspace, exists=True):
        cmds.workspaceControl(workspace, e=True, label=config["title"])

    header = UI_REFS.get("header")
    if header and cmds.text(header, exists=True):
        cmds.text(header, e=True, label=config["title"])

    for checkbox in UI_REFS.get("range_checkboxes", []):
        if checkbox and cmds.checkBox(checkbox, exists=True):
            cmds.checkBox(checkbox, e=True, label=get_range_checkbox_label(engine))

    for checkbox in UI_REFS.get("color_correct_checkboxes", []):
        if checkbox and cmds.checkBox(checkbox, exists=True):
            cmds.checkBox(checkbox, e=True, label=get_color_correct_checkbox_label(engine))

    for key, frame in UI_REFS.get("advanced_frames", {}).items():
        if frame and cmds.frameLayout(frame, exists=True):
            cmds.frameLayout(frame, e=True, label=SECTION_LABELS[engine][key])

    create_button = UI_REFS.get("create_button")
    tex_fields = UI_REFS.get("tex_fields")
    advanced = UI_REFS.get("advanced")
    material_name_field = UI_REFS.get("material_name_field")
    if create_button and cmds.button(create_button, exists=True) and tex_fields is not None and advanced is not None and material_name_field:
        create_command = create_vray_shader if engine == ENGINE_VRAY else create_ai_shader
        cmds.button(create_button, e=True, command=lambda *_: create_command(tex_fields, advanced, material_name_field))

def on_engine_changed(new_engine):
    if SUPPRESS_ENGINE_CHANGE:
        return

    previous_engine = CURRENT_ENGINE
    engine = normalize_engine(new_engine)
    if get_plugin_warning_message(engine):
        update_engine_warning_label(engine)
        set_engine_dropdown_value(previous_engine)
        apply_engine_ui(previous_engine)
        return

    apply_engine_ui(engine)
    effective_engine = update_engine_warning_label(engine)
    if effective_engine and effective_engine != engine:
        apply_engine_ui(effective_engine)

# ======================================================
# UI CREATION
# ======================================================

def create_shader_creator_ui(engine=None):
    global ENGINE_DROPDOWN, MATERIAL_DROPDOWN, DELETE_OLD_TOGGLE
    global USE_CURRENT_NAME_TOGGLE, AUTO_REFRESH_TOGGLE, DETECTED_MAT_LABEL

    engine = normalize_engine(engine or get_engine_from_current_renderer())
    config = RENDER_ENGINES[engine]

    USE_CURRENT_NAME_TOGGLE = None
    reset_ui_refs()

    control_name = UI_REFS["workspace"]
    for old_control in ("aiShaderWorkspace", "vrayShaderWorkspace", control_name):
        if cmds.workspaceControl(old_control, exists=True):
            cmds.deleteUI(old_control)

    workspace = cmds.workspaceControl(
        control_name,
        label=config["title"],
        retain=False,
        widthProperty="free",
        heightProperty="free",
        minimumWidth=360,
        minimumHeight=420,
        initialWidth=700,
        initialHeight=850
    )
    
    tex_fields, advanced = {}, {}
    cmds.scrollLayout(horizontalScrollBarThickness=0, verticalScrollBarThickness=16, childResizable=True)
    main_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 20))
    cmds.menuBarLayout()
    edit_menu = cmds.menu(label="Edit", tearOff=True)
    cmds.setParent(main_layout)

    ENGINE_DROPDOWN = cmds.optionMenu(label="Render Engine", width=300)
    cmds.menuItem(label=ENGINE_ARNOLD)
    cmds.menuItem(label=ENGINE_VRAY)
    cmds.optionMenu(ENGINE_DROPDOWN, e=True, value=engine, cc=lambda value: on_engine_changed(value))
    cmds.separator(style="in", h=10)

    UI_REFS["header"] = cmds.text(config["title"], align="center", fn="boldLabelFont", h=30)
    material_name_field = cmds.textField(placeholderText="Name Your Material :)")
    USE_CURRENT_NAME_TOGGLE = cmds.checkBox(label="Use current material name", v=False, cc=lambda v: cmds.textField(material_name_field, e=True, enable=not v))
    cmds.separator(style="in", h=10)
    MATERIAL_DROPDOWN = cmds.optionMenu(label="Target Material", visible=False, width=300)
    cmds.menuItem(label="No material detected")
    DELETE_OLD_TOGGLE = cmds.checkBox(label="Delete old material and textures", v=True)
    cmds.separator(style="in", h=10)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
    cmds.button(label="Detect Materials", height=35, command=lambda *_: on_detect_materials_clicked(tex_fields, advanced))
    DETECTED_MAT_LABEL = cmds.text(label="Material Detected: None", align="left")
    cmds.setParent("..")
    cmds.separator(style="in", h=10)
    cmds.menuItem(label="Refresh UI", parent=edit_menu, command=lambda *_: refresh_all_fields(tex_fields, advanced, material_name_field))

    def file_picker(label, utility_type=None, default_val=True):
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        cmds.text(f"{label}:", align="left")
        drop = cmds.optionMenu(width=300, cc=lambda val: on_dropdown_change(val, f_field))
        cmds.menuItem(label="-- Select Map --")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnWidth3=(240, 40, 30))
        f_field = cmds.textField(placeholderText="Select file...")
        cmds.iconTextButton(style="iconOnly", image1="folder-open.png", command=lambda *_: browse_file(f_field))
        cmds.button(label="X", command=lambda *_: (cmds.textField(f_field, e=True, text=""), cmds.optionMenu(drop, e=True, sl=1)))
        cmds.setParent("..")
        util_cb = None
        if utility_type:
            util_label = get_color_correct_checkbox_label(engine) if utility_type == "cc" else get_range_checkbox_label(engine)
            cmds.rowLayout(numberOfColumns=2, columnWidth2=(10, 200))
            cmds.text("")
            util_cb = cmds.checkBox(label=util_label, v=default_val)
            if utility_type == "cc":
                UI_REFS["color_correct_checkboxes"].append(util_cb)
            else:
                UI_REFS["range_checkboxes"].append(util_cb)
            cmds.setParent("..")
        cmds.setParent("..")
        return f_field, util_cb, drop

    f_base, cb_base, d_base = file_picker("Base Color", "cc")
    tex_fields["basecolor"] = {"path": f_base, "cc": cb_base, "drop": d_base}
    for name in ["Ambient Occlusion", "Roughness", "Metalness", "Specular Weight", "Opacity"]:
        f, cb, d = file_picker(name, "range")
        tex_fields[name.lower().replace(" ", "")] = {"path": f, "range": cb, "drop": d}
    f_norm, _, d_norm = file_picker("Normal")
    tex_fields["normal"] = {"path": f_norm, "drop": d_norm}
    f_disp, cb_disp, d_disp = file_picker("Displacement", "range", default_val=False)
    tex_fields["displacement"] = {"path": f_disp, "range": cb_disp, "drop": d_disp}

    cmds.separator(style="in", h=10)
    sections = [("transmission", 1, 1, 0), ("subsurface", 1, 1, 0), ("emission", 1, 1, 0), ("sheen", 1, 1, 1), ("coat", 1, 1, 1)]

    for key, has_w, has_c, has_r in sections:
        f_layout = cmds.frameLayout(label=SECTION_LABELS[engine][key], collapsable=True, cl=True, mw=5, parent=main_layout)
        UI_REFS["advanced_frames"][key] = f_layout
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        entry = {"frame": f_layout}
        if has_w: entry["weight"], entry["weight_range"], entry["weight_drop"] = file_picker("Weight Map", "range")
        if has_c:
            entry["use_sep"] = cmds.checkBox(label="Use separate color texture", v=False)
            entry["color_col"] = cmds.columnLayout(adjustableColumn=True, visible=False)
            entry["color"], entry["color_cc"], entry["color_drop"] = file_picker("Color Map", "cc")
            cmds.setParent("..")
            cmds.checkBox(entry["use_sep"], e=True, cc=lambda v, c=entry["color_col"]: cmds.columnLayout(c, e=True, visible=bool(v)))
        if has_r:
            entry["use_sep_r"] = cmds.checkBox(label="Use separate roughness texture", v=False)
            entry["rough_col"] = cmds.columnLayout(adjustableColumn=True, visible=False)
            entry["roughness"], entry["rough_range"], entry["roughness_drop"] = file_picker("Roughness Map", "range")
            cmds.setParent("..")
            cmds.checkBox(entry["use_sep_r"], e=True, cc=lambda v, c=entry["rough_col"]: cmds.columnLayout(c, e=True, visible=bool(v)))
        advanced[key] = entry
        cmds.setParent(main_layout)

    cmds.separator(style="in", h=10, parent=main_layout)
    UI_REFS["create_button"] = cmds.button(label="Create Material", height=45, bgc=(1, 1, 1), parent=main_layout)
    AUTO_REFRESH_TOGGLE = cmds.checkBox(label="Auto-refresh UI after material creation", v=True, parent=main_layout)

    UI_REFS["tex_fields"] = tex_fields
    UI_REFS["advanced"] = advanced
    UI_REFS["material_name_field"] = material_name_field
    apply_engine_ui(engine)

    cmds.scriptJob(event=["SelectionChanged", update_material_dropdown], protected=True, parent=workspace)
    cmds.scriptJob(event=["RecentCommandChanged", update_material_dropdown], protected=True, parent=workspace)
    cmds.scriptJob(event=["Undo", update_material_dropdown], protected=True, parent=workspace)
    cmds.scriptJob(event=["Redo", update_material_dropdown], protected=True, parent=workspace)
    
    update_material_dropdown()
    effective_engine = update_engine_warning_label(engine)
    if effective_engine and effective_engine != engine:
        apply_engine_ui(effective_engine)

def create_ai_shader_ui():
    create_shader_creator_ui(ENGINE_ARNOLD)

def create_vray_shader_ui():
    create_shader_creator_ui(ENGINE_VRAY)

# ======================================================
# CORE SHADER GENERATION LOGIC
# ======================================================

def create_ai_shader(tex_fields, advanced, material_name_field):
    global MATERIAL_DROPDOWN, DELETE_OLD_TOGGLE, USE_CURRENT_NAME_TOGGLE, AUTO_REFRESH_TOGGLE

    mesh_sel = cmds.ls(sl=True, dag=True, type='mesh')
    if not mesh_sel:
        cmds.confirmDialog(title='Selection Warning', message='Please select at least one mesh to create a material.', button=['OK'], defaultButton='OK', icon='warning')
        return
    if not validate_engine_before_create(ENGINE_ARNOLD):
        return

    sel = cmds.ls(sl=True, long=True)
    old_mat = cmds.optionMenu(MATERIAL_DROPDOWN, q=True, value=True) if sel and cmds.optionMenu(MATERIAL_DROPDOWN, q=True, exists=True) else None
    if old_mat == "No material detected" or (old_mat and not cmds.objExists(old_mat)): old_mat = None

    use_current = cmds.checkBox(USE_CURRENT_NAME_TOGGLE, q=True, v=True) if USE_CURRENT_NAME_TOGGLE else False
    if use_current and old_mat:
        mat_name_input = old_mat
    else:
        mat_name_input = cmds.textField(material_name_field, q=True, text=True).strip()

    if not mat_name_input:
        res = cmds.confirmDialog(title='Naming Warning', message="You didn't name your material.", button=['Continue', 'Cancel'])
        if res == 'Cancel': return
        mat_name = RENDER_ENGINES[ENGINE_ARNOLD]["default_material"]
    else: mat_name = mat_name_input

    if old_mat and old_mat == mat_name:
        cmds.rename(old_mat, f"{old_mat}_old")
        old_mat = f"{old_mat}_old"

    shader = cmds.shadingNode("aiStandardSurface", asShader=True, name=mat_name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{mat_name}SG")
    cmds.connectAttr(f"{shader}.outColor", f"{sg}.surfaceShader", f=True)

    place2d = cmds.shadingNode("place2dTexture", asUtility=True)

    def create_file(name, path, colorSpace="Raw", alphaLum=True):
        f = cmds.shadingNode("file", asTexture=True, name=f"file_{name}")
        attrs = ["coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree", "vertexCameraOne"]
        for attr in attrs: cmds.connectAttr(f"{place2d}.{attr}", f"{f}.{attr}", f=True)
        cmds.connectAttr(f"{place2d}.outUV", f"{f}.uvCoord", f=True)
        cmds.connectAttr(f"{place2d}.outUvFilterSize", f"{f}.uvFilterSize", f=True)
        cmds.setAttr(f"{f}.ignoreColorSpaceFileRules", 1); cmds.setAttr(f"{f}.colorSpace", colorSpace, type="string")
        cmds.setAttr(f"{f}.alphaIsLuminance", alphaLum); cmds.setAttr(f"{f}.fileTextureName", path, type="string")
        match = re.search(r"\b(1\d{3})\b", os.path.basename(path))
        if match and int(match.group(1)) >= 1001: cmds.setAttr(f"{f}.uvTilingMode", 3)
        return f

    base_node, base_cc_out = None, None
    if get_path(tex_fields["basecolor"]["path"]):
        base_file_node = create_file('baseColor', get_path(tex_fields['basecolor']['path']), 'sRGB', False)
        base_node = f"{base_file_node}.outColor"

    if get_path(tex_fields["ambientocclusion"]["path"]) and base_node:
        ao = create_file("AO", get_path(tex_fields["ambientocclusion"]["path"]), alphaLum=True); ao_out = f"{ao}.outColor"
        if cmds.checkBox(tex_fields["ambientocclusion"]["range"], q=True, v=True):
            ao_range = cmds.shadingNode("aiRange", asUtility=True); cmds.connectAttr(ao_out, f"{ao_range}.input", f=True); ao_out = f"{ao_range}.outColor"
        layer = cmds.shadingNode("aiLayerRgba", asUtility=True); cmds.setAttr(f"{layer}.operation2", 23); cmds.setAttr(f"{layer}.enable2", 1)
        cmds.connectAttr(base_node, f"{layer}.input1", f=True); cmds.connectAttr(ao_out, f"{layer}.input2", f=True); base_node = f"{layer}.outColor"

    if base_node:
        final_base = base_node
        if cmds.checkBox(tex_fields["basecolor"]["cc"], q=True, v=True):
            cc = cmds.shadingNode("aiColorCorrect", asUtility=True); cmds.connectAttr(base_node, f"{cc}.input", f=True); final_base = f"{cc}.outColor"
            base_cc_out = final_base
        else: base_cc_out = base_node
        cmds.connectAttr(final_base, f"{shader}.baseColor", f=True)

    scalars = {"roughness": "specularRoughness", "metalness": "metalness", "specularweight": "specular", "opacity": "opacity"}
    for k, attr in scalars.items():
        p = get_path(tex_fields[k]["path"])
        if p:
            f = create_file(k, p, alphaLum=True); final_scalar = f"{f}.outColor"
            if cmds.checkBox(tex_fields[k]["range"], q=True, v=True):
                r = cmds.shadingNode("aiRange", asUtility=True); cmds.connectAttr(f"{f}.outColor", f"{r}.input", f=True); final_scalar = f"{r}.outColor"
            if k == "opacity": cmds.connectAttr(final_scalar, f"{shader}.{attr}", f=True)
            else: cmds.connectAttr(f"{final_scalar}R", f"{shader}.{attr}", f=True)

    if get_path(tex_fields["normal"]["path"]):
        nrm = cmds.shadingNode("aiNormalMap", asUtility=True); cmds.connectAttr(f"{create_file('normal', get_path(tex_fields['normal']['path']), alphaLum=False)}.outColor", f"{nrm}.input", f=True); cmds.connectAttr(f"{nrm}.outValue", f"{shader}.normalCamera", f=True)

    if get_path(tex_fields["displacement"]["path"]):
        disp = cmds.shadingNode("displacementShader", asShader=True); cmds.setAttr(f"{disp}.scale", 0.005); cmds.setAttr(f"{disp}.aiDisplacementZeroValue", 0.5)
        d_f = create_file("disp", get_path(tex_fields["displacement"]["path"])); final_disp = f"{d_f}.outColor"
        if cmds.checkBox(tex_fields["displacement"]["range"], q=True, v=True):
            dr = cmds.shadingNode("aiRange", asUtility=True); cmds.connectAttr(f"{d_f}.outColor", f"{dr}.input", f=True); final_disp = f"{dr}.outColor"
        cmds.connectAttr(f"{final_disp}R", f"{disp}.displacement", f=True); cmds.connectAttr(f"{disp}.displacement", f"{sg}.displacementShader", f=True)

    for key, (w_attr, c_attr, r_attr) in {"transmission": ("transmission", "transmissionColor", None), "subsurface": ("subsurface", "subsurfaceColor", None), "emission": ("emission", "emissionColor", None), "sheen": ("sheen", "sheenColor", "sheenRoughness"), "coat": ("coat", "coatColor", "coatRoughness")}.items():
        data = advanced[key]; w_path, c_path, r_path = get_path(data.get("weight")), get_path(data.get("color")), get_path(data.get("roughness"))
        u_sep_c, u_sep_r = cmds.checkBox(data["use_sep"], q=True, v=True) if data.get("use_sep") else False, cmds.checkBox(data["use_sep_r"], q=True, v=True) if data.get("use_sep_r") else False
        
        # Cleanup: Set defaults regardless
        if key == "subsurface":
            cmds.setAttr(f"{shader}.subsurfaceType", 2); cmds.setAttr(f"{shader}.subsurfaceRadius", 1.0, 0, 0, type="double3")

        if w_path:
            wf = create_file(f"{key}_w", w_path); final_w = f"{wf}.outColor"
            if cmds.checkBox(data["weight_range"], q=True, v=True):
                r = cmds.shadingNode("aiRange", asUtility=True); cmds.connectAttr(f"{wf}.outColor", f"{r}.input", f=True); final_w = f"{r}.outColor"
            cmds.connectAttr(f"{final_w}R", f"{shader}.{w_attr}", f=True)
            if key == "subsurface" and not u_sep_c and base_cc_out: cmds.connectAttr(base_cc_out, f"{shader}.subsurfaceColor", f=True)

        if u_sep_r and r_path and r_attr:
            rf = create_file(f"{key}_r", r_path); final_r = f"{rf}.outColor"
            if cmds.checkBox(data["rough_range"], q=True, v=True):
                rr = cmds.shadingNode("aiRange", asUtility=True); cmds.connectAttr(f"{rf}.outColor", f"{rr}.input", f=True); final_r = f"{rr}.outColor"
            cmds.connectAttr(f"{final_r}R", f"{shader}.{r_attr}", f=True)
        if u_sep_c and c_path:
            cf = create_file(f"{key}_c", c_path, "sRGB", False); final_c = f"{cf}.outColor"
            if cmds.checkBox(data["color_cc"], q=True, v=True):
                cc = cmds.shadingNode("aiColorCorrect", asUtility=True); cmds.connectAttr(f"{cf}.outColor", f"{cc}.input", f=True); final_c = f"{cc}.outColor"
            cmds.connectAttr(final_c, f"{shader}.{c_attr}", f=True)

    # --- Updated: Global Material Replacement Logic ---
    target_geometry = []
    if old_mat and cmds.objExists(old_mat):
        old_sgs = cmds.listConnections(old_mat, type="shadingEngine") or []
        for osg in old_sgs:
            # Gather ALL members using this material
            mems = cmds.sets(osg, q=True) or []
            target_geometry.extend(mems)
    
    # Fallback to selection if no material detected or it's unused
    if not target_geometry:
        target_geometry = mesh_sel
        
    if target_geometry:
        cmds.sets(target_geometry, edit=True, forceElement=sg)

    update_material_dropdown()
    
    # Delete old material only if it's truly empty now
    if old_mat and cmds.objExists(old_mat):
        if cmds.checkBox(DELETE_OLD_TOGGLE, q=True, v=True): 
            sgs_old = cmds.listConnections(old_mat, type="shadingEngine") or []
            if not any(cmds.sets(sg, q=True) for sg in sgs_old):
                delete_shading_network(old_mat)

    if cmds.checkBox(AUTO_REFRESH_TOGGLE, q=True, v=True): refresh_all_fields(tex_fields, advanced, material_name_field)

def create_vray_shader(tex_fields, advanced, material_name_field):
    global MATERIAL_DROPDOWN, DELETE_OLD_TOGGLE, USE_CURRENT_NAME_TOGGLE, AUTO_REFRESH_TOGGLE

    mesh_sel = cmds.ls(sl=True, dag=True, type='mesh')
    if not mesh_sel:
        cmds.confirmDialog(title='Selection Warning', message='Please select at least one mesh to create a material.', button=['OK'], defaultButton='OK', icon='warning')
        return
    if not validate_engine_before_create(ENGINE_VRAY):
        return

    sel = cmds.ls(sl=True, long=True)
    old_mat = cmds.optionMenu(MATERIAL_DROPDOWN, q=True, value=True) if sel and cmds.optionMenu(MATERIAL_DROPDOWN, q=True, exists=True) else None
    if old_mat == "No material detected" or (old_mat and not cmds.objExists(old_mat)): old_mat = None

    use_current = cmds.checkBox(USE_CURRENT_NAME_TOGGLE, q=True, v=True) if USE_CURRENT_NAME_TOGGLE else False
    if use_current and old_mat:
        mat_name_input = old_mat
    else:
        mat_name_input = cmds.textField(material_name_field, q=True, text=True).strip()
        
    if not mat_name_input:
        res = cmds.confirmDialog(title='Naming Warning', message="You didn't name your material.", button=['Continue', 'Cancel'])
        if res == 'Cancel': return
        mat_name = RENDER_ENGINES[ENGINE_VRAY]["default_material"]
    else: mat_name = mat_name_input

    target_geometry = []
    if old_mat and cmds.objExists(old_mat):
        old_sgs = cmds.listConnections(old_mat, type="shadingEngine") or []
        for osg in old_sgs:
            mems = cmds.sets(osg, q=True) or []
            target_geometry.extend(mems)
    
    if not target_geometry:
        target_geometry = mesh_sel

    if old_mat and old_mat == mat_name:
        if cmds.checkBox(DELETE_OLD_TOGGLE, q=True, v=True):
            cmds.select(clear=True)
            delete_shading_network(old_mat)
            old_mat = None

    shader = cmds.shadingNode("VRayMtl", asShader=True, name=mat_name)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{shader}SG")
    cmds.connectAttr(f"{shader}.outColor", f"{sg}.surfaceShader", f=True)

    cmds.setAttr(f"{shader}.brdfType", 3)
    cmds.setAttr(f"{shader}.useRoughness", 1)
    cmds.setAttr(f"{shader}.reflectionColor", 1, 1, 1, type="double3")

    place2d = cmds.shadingNode("place2dTexture", asUtility=True)
    vray_color_correct_nodes = []

    def create_file(name, path, colorSpace="Raw", alphaLum=True):
        f = cmds.shadingNode("file", asTexture=True, name=f"file_{name}")
        attrs = ["coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree", "vertexCameraOne"]
        for attr in attrs: cmds.connectAttr(f"{place2d}.{attr}", f"{f}.{attr}", f=True)
        cmds.connectAttr(f"{place2d}.outUV", f"{f}.uvCoord", f=True)
        cmds.connectAttr(f"{place2d}.outUvFilterSize", f"{f}.uvFilterSize", f=True)
        cmds.setAttr(f"{f}.ignoreColorSpaceFileRules", 1); cmds.setAttr(f"{f}.colorSpace", colorSpace, type="string")
        cmds.setAttr(f"{f}.alphaIsLuminance", alphaLum); cmds.setAttr(f"{f}.fileTextureName", path, type="string")
        match = re.search(r"\b(1\d{3})\b", os.path.basename(path))
        if match and int(match.group(1)) >= 1001: cmds.setAttr(f"{f}.uvTilingMode", 3)
        return f

    base_node, base_cc_out = None, None
    if get_path(tex_fields["basecolor"]["path"]):
        base_file_node = create_file('baseColor', get_path(tex_fields['basecolor']['path']), 'sRGB', False)
        base_node = f"{base_file_node}.outColor"

    if get_path(tex_fields["ambientocclusion"]["path"]) and base_node:
        ao = create_file("AO", get_path(tex_fields["ambientocclusion"]["path"]), alphaLum=True); ao_out = f"{ao}.outColor"
        if cmds.checkBox(tex_fields["ambientocclusion"]["range"], q=True, v=True):
            ao_remap = cmds.shadingNode("remapValue", asUtility=True)
            cmds.connectAttr(f"{ao}.outColorR", f"{ao_remap}.inputValue", f=True)
            ao_out = f"{ao_remap}.outValue"
        mult = cmds.shadingNode("multiplyDivide", asUtility=True)
        cmds.setAttr(f"{mult}.operation", 1)
        cmds.connectAttr(base_node, f"{mult}.input1", f=True)
        if cmds.checkBox(tex_fields["ambientocclusion"]["range"], q=True, v=True):
            cmds.connectAttr(ao_out, f"{mult}.input2X", f=True)
            cmds.connectAttr(ao_out, f"{mult}.input2Y", f=True)
            cmds.connectAttr(ao_out, f"{mult}.input2Z", f=True)
        else:
            cmds.connectAttr(ao_out, f"{mult}.input2", f=True)
        base_node = f"{mult}.output"

    if base_node:
        final_base = base_node
        if cmds.checkBox(tex_fields["basecolor"]["cc"], q=True, v=True):
            cc = cmds.shadingNode("VRayColorCorrection", asTexture=True)
            vray_color_correct_nodes.append(cc)
            cmds.connectAttr(base_node, f"{cc}.texture_map", f=True)
            final_base = f"{cc}.outColor"
            base_cc_out = final_base
        else: base_cc_out = base_node
        cmds.connectAttr(final_base, f"{shader}.color", f=True)

    scalars = {
        "roughness": "reflectionGlossiness",
        "metalness": "metalness",
        "specularweight": "reflectionColorAmount",
        "opacity": "opacityMap"
    }
    for k, attr in scalars.items():
        p = get_path(tex_fields[k]["path"])
        if p:
            f = create_file(k, p, alphaLum=True)
            if k == "opacity":
                final_scalar = f"{f}.outColor"
                if cmds.checkBox(tex_fields[k]["range"], q=True, v=True):
                    r = cmds.shadingNode("remapValue", asUtility=True)
                    cmds.connectAttr(f"{f}.outColorR", f"{r}.inputValue", f=True)
                    expand = cmds.shadingNode("multiplyDivide", asUtility=True)
                    cmds.setAttr(f"{expand}.operation", 1)
                    cmds.connectAttr(f"{r}.outValue", f"{expand}.input1X", f=True)
                    cmds.connectAttr(f"{r}.outValue", f"{expand}.input1Y", f=True)
                    cmds.connectAttr(f"{r}.outValue", f"{expand}.input1Z", f=True)
                    cmds.setAttr(f"{expand}.input2", 1, 1, 1, type="double3")
                    final_scalar = f"{expand}.output"
                cmds.connectAttr(final_scalar, f"{shader}.{attr}", f=True)
            else:
                final_out = f"{f}.outColorR"
                if cmds.checkBox(tex_fields[k]["range"], q=True, v=True):
                    r = cmds.shadingNode("remapValue", asUtility=True)
                    cmds.connectAttr(f"{f}.outColorR", f"{r}.inputValue", f=True)
                    final_out = f"{r}.outValue"
                cmds.connectAttr(final_out, f"{shader}.{attr}", f=True)

    if get_path(tex_fields["normal"]["path"]):
        nrm_file = create_file('normal', get_path(tex_fields['normal']['path']), alphaLum=False)
        nrm = cmds.shadingNode("VRayNormalMap", asTexture=True)
        cmds.setAttr(f"{nrm}.mapType", 1)
        cmds.connectAttr(f"{nrm_file}.outColor", f"{nrm}.map", f=True)
        cmds.connectAttr(f"{nrm}.outColor", f"{shader}.bumpMap", f=True)

    if get_path(tex_fields["displacement"]["path"]):
        disp = cmds.shadingNode("displacementShader", asShader=True)
        cmds.setAttr(f"{disp}.scale", 0.005)
        d_f = create_file("disp", get_path(tex_fields["displacement"]["path"]))
        final_disp_out = f"{d_f}.outColorR"
        if cmds.checkBox(tex_fields["displacement"]["range"], q=True, v=True):
            dr = cmds.shadingNode("remapValue", asUtility=True)
            cmds.connectAttr(f"{d_f}.outColorR", f"{dr}.inputValue", f=True)
            final_disp_out = f"{dr}.outValue"
        cmds.connectAttr(final_disp_out, f"{disp}.displacement", f=True)
        cmds.connectAttr(f"{disp}.displacement", f"{sg}.displacementShader", f=True)

    advanced_attr_map = {
        "transmission": ("refractionColorAmount", "refractionColor",  None),
        "subsurface":   ("translucencyAmount",    "translucencyColor", None),
        "emission":     (None,                    "illumColor",       None),
        "sheen":        ("sheenColorAmount",      "sheenColor",       "sheenGlossiness"),
        "coat":         ("coatColorAmount",       "coatColor",        "coatGlossiness"),
    }

    for key, (w_attr, c_attr, r_attr) in advanced_attr_map.items():
        data = advanced[key]
        w_path = get_path(data.get("weight"))
        c_path = get_path(data.get("color"))
        r_path = get_path(data.get("roughness"))
        u_sep_c = cmds.checkBox(data["use_sep"], q=True, v=True) if data.get("use_sep") else False
        u_sep_r = cmds.checkBox(data["use_sep_r"], q=True, v=True) if data.get("use_sep_r") else False

        if key == "subsurface" and (w_path or (u_sep_c and c_path)):
            for attr in ["translucencyMode", "translucency", "translucency_type"]:
                try:
                    enum_str = cmds.attributeQuery(attr, node=shader, listEnum=True)
                    if enum_str:
                        # Parse Maya enum string e.g. "None:Volumetric=5:SSS"
                        # The =N syntax means "jump index to N"
                        parts = enum_str[0].split(':')
                        idx = 0
                        enum_map = {}
                        for part in parts:
                            if '=' in part:
                                name, val = part.rsplit('=', 1)
                                idx = int(val)
                                enum_map[name.upper()] = idx
                            else:
                                enum_map[part.upper()] = idx
                            idx += 1
                        # Pick SSS first, then Hybrid, then Volumetric
                        for target in ["SSS", "HYBRID", "VOLUMETRIC"]:
                            if target in enum_map:
                                cmds.setAttr(f"{shader}.{attr}", enum_map[target])
                                break
                        break
                except Exception:
                    pass

        if key == "emission":
            w_out, c_out = None, None
            if w_path:
                wf = create_file("emission_w", w_path)
                w_out = f"{wf}.outColor"
                if cmds.checkBox(data["weight_range"], q=True, v=True):
                    r = cmds.shadingNode("remapValue", asUtility=True)
                    cmds.connectAttr(f"{wf}.outColorR", f"{r}.inputValue", f=True)
                    expand = cmds.shadingNode("multiplyDivide", asUtility=True)
                    cmds.connectAttr(f"{r}.outValue", f"{expand}.input1X", f=True)
                    cmds.connectAttr(f"{r}.outValue", f"{expand}.input1Y", f=True)
                    cmds.connectAttr(f"{r}.outValue", f"{expand}.input1Z", f=True)
                    cmds.setAttr(f"{expand}.input2", 1, 1, 1, type="double3")
                    w_out = f"{expand}.output"
            
            if u_sep_c and c_path:
                cf = create_file("emission_c", c_path, "sRGB", False)
                c_out = f"{cf}.outColor"
                if cmds.checkBox(data["color_cc"], q=True, v=True):
                    cc = cmds.shadingNode("VRayColorCorrection", asTexture=True)
                    vray_color_correct_nodes.append(cc)
                    cmds.connectAttr(f"{cf}.outColor", f"{cc}.texture_map", f=True)
                    c_out = f"{cc}.outColor"
            elif w_out and not u_sep_c and base_cc_out:
                c_out = base_cc_out
                    
            if w_out and c_out:
                mult = cmds.shadingNode("multiplyDivide", asUtility=True)
                cmds.connectAttr(c_out, f"{mult}.input1", f=True)
                cmds.connectAttr(w_out, f"{mult}.input2", f=True)
                cmds.connectAttr(f"{mult}.output", f"{shader}.illumColor", f=True)
            elif w_out:
                cmds.connectAttr(w_out, f"{shader}.illumColor", f=True)
            elif c_out:
                cmds.connectAttr(c_out, f"{shader}.illumColor", f=True)
                
            if w_out or c_out:
                try: cmds.setAttr(f"{shader}.selfIlluminationGi", 1)
                except Exception: pass
            continue

        if w_path:
            wf = create_file(f"{key}_w", w_path)
            final_w = f"{wf}.outColorR"
            if cmds.checkBox(data["weight_range"], q=True, v=True):
                r = cmds.shadingNode("remapValue", asUtility=True)
                cmds.connectAttr(f"{wf}.outColorR", f"{r}.inputValue", f=True)
                final_w = f"{r}.outValue"
            cmds.connectAttr(final_w, f"{shader}.{w_attr}", f=True)
            if key == "subsurface" and not u_sep_c and base_cc_out:
                cmds.connectAttr(base_cc_out, f"{shader}.translucencyColor", f=True)

        if u_sep_r and r_path and r_attr:
            rf = create_file(f"{key}_r", r_path)
            final_r = f"{rf}.outColorR"
            if cmds.checkBox(data["rough_range"], q=True, v=True):
                rr = cmds.shadingNode("remapValue", asUtility=True)
                cmds.connectAttr(f"{rf}.outColorR", f"{rr}.inputValue", f=True)
                final_r = f"{rr}.outValue"
            cmds.connectAttr(final_r, f"{shader}.{r_attr}", f=True)

        if u_sep_c and c_path:
            cf = create_file(f"{key}_c", c_path, "sRGB", False)
            final_c = f"{cf}.outColor"
            if cmds.checkBox(data["color_cc"], q=True, v=True):
                cc = cmds.shadingNode("VRayColorCorrection", asTexture=True)
                vray_color_correct_nodes.append(cc)
                cmds.connectAttr(f"{cf}.outColor", f"{cc}.texture_map", f=True)
                final_c = f"{cc}.outColor"
            cmds.connectAttr(final_c, f"{shader}.{c_attr}", f=True)

    if vray_color_correct_nodes:
        defer_node_editors_connected_view()

    if target_geometry:
        valid_targets = [g for g in target_geometry if cmds.objExists(g.split('.')[0])]
        if valid_targets:
            cmds.sets(valid_targets, edit=True, forceElement=sg)

    update_material_dropdown()
    
    if old_mat and cmds.objExists(old_mat):
        if cmds.checkBox(DELETE_OLD_TOGGLE, q=True, v=True): 
            sgs_old = cmds.listConnections(old_mat, type="shadingEngine") or []
            if not any(cmds.sets(sg, q=True) for sg in sgs_old):
                cmds.select(shader, r=True)
                delete_shading_network(old_mat)
                if sel: cmds.select(sel, r=True)

    if cmds.checkBox(AUTO_REFRESH_TOGGLE, q=True, v=True): refresh_all_fields(tex_fields, advanced, material_name_field)

if __name__ == "__main__":
    create_shader_creator_ui()
