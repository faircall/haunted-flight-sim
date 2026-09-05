"""Compact redhead authoring controls used by the animation inspector."""
import copy
import math

import pyray as pr
import g_ui
import g_animation_authoring as authoring


def row(ui, actions):
    rect = g_ui.ui_next_rect(ui)
    width = rect.width / len(actions)
    for index, (key, label, action) in enumerate(actions):
        if g_ui.ui_button(ui, "animation_edit:" + key, label,
                          pr.Rectangle(rect.x + index * width, rect.y, width - 2, rect.height)):
            action()


def draw(ui, state, character="redhead"):
    debug = state["animation_debug"]
    draft_key = character + "_animation_draft"
    if debug.get("authoring_character") != character:
        debug.update(authoring_character=character, save_review=False, authoring_error=None,
                     edit_field=None, edit_group="legs" if character == "player" else "side legs")
    panel = g_ui.ui_current_panel(ui)
    if panel is not None:
        panel["spacing"] = 1
    try:
        if debug.get("authoring_error"):
            draw_review(ui, debug, state.get(draft_key, {}))
            return
        if draft_key not in state:
            state[draft_key] = authoring.new_draft(character=character)
        draft = state[draft_key]
        if debug.get("save_review"):
            draw_review(ui, debug, draft)
            return
        rect = g_ui.ui_next_rect(ui, 16)
        half = rect.width / 2
        track, track_changed = g_ui.ui_dropdown(
            ui, "animation_edit:track", "", debug.get("track", "walk"), ("walk", "run"),
            rect=pr.Rectangle(rect.x, rect.y, half - 2, rect.height), max_visible=2)
        debug["facing"], _ = g_ui.ui_dropdown(
            ui, "animation_edit:facing", "", debug.get("facing", "right"),
            ("right", "left", "up", "down"),
            rect=pr.Rectangle(rect.x + half, rect.y, half, rect.height), max_visible=4)
        debug["track"] = track
        index_text, changed = g_ui.ui_dropdown(
            ui, "animation_edit:pose", "pose", str(debug.get("edit_keyframe", 0) + 1),
            ("1", "2", "3", "4"), max_visible=4)
        index = int(index_text) - 1
        debug["edit_keyframe"] = index
        # Keep the edited pose stable while continuous playback advances separately.
        if changed or track_changed:
            debug.update(playback="keyframe", keyframe=index, phase=index * math.tau / 4)
        group_options = ("legs", "arms", "body", "rig") if character == "player" else ("side legs", "front legs", "arms", "body", "rig")
        group, _ = g_ui.ui_dropdown(ui, "animation_edit:group", "group",
                                    debug.get("edit_group", "side legs"),
                                    group_options, max_visible=5)
        debug["edit_group"] = group
        profile_path = authoring.pose_path(character, debug["facing"], group, track)
        pose = authoring.get_path(draft["document"], profile_path)[index]
        rig_name = "PLAYER_CUTOUT_RIG_DEFAULTS" if character == "player" else "REDHEAD_CUTOUT_RIG_DEFAULTS"
        groups = {
            "side legs": [k for k in pose if "upper_leg_degrees" in k or "knee_bend" in k],
            "front legs": [k for k in pose if "front_leg" in k],
            "arms": [k for k in pose if "arm" in k or "elbow" in k],
            "body": [k for k in pose if k.startswith("body_") or "torso" in k],
            "rig": ["footfall_phase_degrees", "movement_blend_response", "profile_blend_response",
                    "run_blend_start_speed_fraction", "run_blend_full_speed_fraction"],
        }
        if character == "player":
            groups["legs"] = [k for k in pose if any(word in k for word in ("leg", "knee", "foot"))]
            groups["arms"] = [k for k in pose if any(word in k for word in ("arm", "elbow", "hand"))]
            groups["rig"] = ["footfall_phase_degrees", "movement_blend_response", "profile_blend_response"]
        keys = groups[group]
        # Short labels fit the native 480x270 editor canvas.
        labels = {k: k.replace("_degrees", " deg").replace("_pixels", " px")
                  .replace("upper_", "").replace("_bend", "").replace("front_", "")
                  .replace("_", " ") for k in keys}
        labels.update({k: v for k, v in {
            "footfall_phase_degrees": "footfall deg",
            "movement_blend_response": "move response",
            "profile_blend_response": "gait response",
            "run_blend_start_speed_fraction": "run start",
            "run_blend_full_speed_fraction": "run full",
            "front_arm_angle_scale": "front arm scale",
            "front_elbow_angle_scale": "front elbow scale",
        }.items() if k in keys})
        selected = debug.get("edit_field")
        if selected not in keys:
            selected = keys[0]
        label, _ = g_ui.ui_dropdown(ui, "animation_edit:field", "", labels[selected],
                                    tuple(labels.values()), max_visible=5)
        key = next(k for k in keys if labels[k] == label)
        debug["edit_field"] = key
        values = draft["document"][rig_name] if group == "rig" else pose
        bounds = ((0.0, 1.0) if key.endswith("fraction") else
                  (-180.0, 180.0) if key.endswith("degrees") else (0.0, 60.0)) if group == "rig" else authoring.field_bounds(key)
        value, changed = g_ui.ui_number_input_float(
            ui, f"animation_edit:value:{track}:{index}:{key}",
            "deg" if key.endswith("degrees") else "px" if key.endswith("pixels") else "value",
            values[key], *bounds)
        linked, _ = g_ui.ui_dropdown(ui, "animation_edit:link", "opposite",
                                     "linked" if debug.get("edit_linked") else "independent",
                                     ("independent", "linked"), max_visible=2)
        debug["edit_linked"] = linked == "linked"
        if changed:
            if group == "rig":
                document = copy.deepcopy(draft["document"])
                document[rig_name][key] = value
                authoring.commit(draft, document)
            else:
                authoring.edit_pose(draft, track, index, key, value, debug["edit_linked"], profile_path)
        def reset():
            if group == "rig":
                document = copy.deepcopy(draft["document"])
                document[rig_name][key] = draft["baseline"][rig_name][key]
                authoring.commit(draft, document)
            else:
                authoring.reset_pose(draft, track, index, profile_path)
        row(ui, (("copy", "Copy", lambda: authoring.copy_pose(draft, track, index, profile_path)),
                 ("paste", "Paste", lambda: authoring.paste_pose(draft, track, index, profile_path)),
                 ("reset", "Reset", reset)))
        def playback():
            debug["playback"] = "keyframe" if debug.get("playback") == "continuous" else "continuous"
            if debug["playback"] == "keyframe":
                debug.update(keyframe=index, phase=index * math.tau / 4)
        row(ui, (("undo", "Undo", lambda: authoring.history(draft)),
                 ("redo", "Redo", lambda: authoring.history(draft, redo=True)),
                 ("play", "Pause" if debug.get("playback") == "continuous" else "Play", playback)))
        def toggle_preview():
            draft["preview"] = not draft["preview"]
        def revert():
            # Keep the previous document in undo, but adopt the latest file baseline.
            previous = draft["document"]
            fresh = authoring.new_draft(character=character)
            fresh["undo"] = draft["undo"] + [previous]
            draft.clear()
            draft.update(fresh)
        def review():
            authoring.prepare_save(draft)
            debug.update(save_review=True, review_page=0)
        row(ui, (("preview", "Preview on" if draft["preview"] else "Preview off", toggle_preview),
                 ("revert", "Revert", revert)))
        def toggle_highlight():
            debug["highlight_component"] = not debug.get("highlight_component", False)
        row(ui, (("save", "Save code", review),
                 ("highlight", "Flash on" if debug.get("highlight_component") else "Flash off",
                  toggle_highlight)))
        g_ui.ui_label(ui, "animation_edit:status",
                      "Unsaved changes" if authoring.dirty(draft) else draft["message"], font_size=8)
    except (ValueError, SyntaxError, OSError, TypeError) as error:
        debug["authoring_error"] = str(error)
    if debug.get("authoring_error"):
        # A persistent message page prevents an error from disappearing next frame.
        debug["save_review"] = True


def draw_review(ui, debug, draft):
    error = debug.get("authoring_error")
    review = draft.get("review")
    lines = []
    for line in ([error] if error else (review or {}).get("diff", ["No changes"])):
        # Raylib's bitmap font clamps tiny sizes; wrap by measured pixels.
        remaining = line.lstrip()
        if not remaining:
            lines.append("")
        while remaining:
            count = 1
            while count < len(remaining) and pr.measure_text(remaining[:count + 1], 8) <= 138:
                count += 1
            lines.append(remaining[:count])
            remaining = remaining[count:]
    page = min(debug.get("review_page", 0), max(0, (len(lines) - 1) // 10))
    g_ui.ui_label(ui, "animation_edit:review_title", "Save error" if error else "Review code changes", font_size=8)
    for index, line in enumerate(lines[page * 10:page * 10 + 10]):
        g_ui.ui_label(ui, f"animation_edit:diff:{index}", line, font_size=8)
    def back():
        debug.update(save_review=False, authoring_error=None)
    def save():
        authoring.save(draft)
        debug["save_review"] = False
    row(ui, (("diff_previous", f"< {page + 1}/{max(1, (len(lines) + 9) // 10)}", lambda: debug.update(review_page=max(0, page - 1))),
             ("diff_next", ">", lambda: debug.update(review_page=min((len(lines) - 1) // 10, page + 1)))))
    row(ui, (("back", "Back", back),) if error else
        (("back", "Back", back), ("confirm_save", "Save code", save)))
