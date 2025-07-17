############
#
# Copyright (c) 2024 Maxim Yudayev and KU Leuven eMedia Lab
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Created 2024-2025 for the KU Leuven AidWear, AidFOG, and RevalExo projects
# by Maxim Yudayev [https://yudayev.com].
#
# ############

from .BaseComponent import BaseComponent
from utils.gui_utils import app
from dash import html, dcc, Input, Output, State, callback_context, ALL
import dash_bootstrap_components as dbc
import json


class AnnotationComponent(BaseComponent):
  """
  AnnotationComponent: Annotation management component

  This component handles all annotation-related functionality 

  - Add/Edit/Delete annotations
  - Annotation cards display
  - Keyboard shortcuts (N key for next input, 0-9 for label selection)
  - Start/End time buttons
  - Annotation counter
  """
  def __init__(self, annotation_options: list):
    """
    Annotation management component.

    Args:
        annotation_options: List of annotation label options
    """
    super().__init__(unique_id="annotation_panel", col_width=12)
    self._annotation_options = annotation_options
    self._annotation_values = [opt["value"] for opt in annotation_options]
    self._create_layout()
    self._activate_callbacks()


  def _create_layout(self):
    """Create annotation UI with cards and input fields."""
    self._layout = html.Div([
      html.H5("Annotations", className="text-center mb-2 mt-2"),

      # Annotation counter
      html.Div(id="annotation-counter", className="text-center mb-2 fw-bold text-primary"),

      # Timestamp display input box
      # The timestamp from one of the UI components (including a precise point in the plots) will be displayed here, which can be copied to the annotation input fields 
      html.Div([
        dbc.Input(
          id="selected-timestamp",
          type="text",
          placeholder="Click video/plot for timestamp",
          readonly=True,
          value="",
          size="sm"
        )
      ], className="mb-2"),

      html.Hr(className="my-2"),

      # Scrollable annotation area
      html.Div([
        # Container for existing annotations (will appear sorted)
        html.Div(id="annotations-container"),

        # New annotation block (stays at bottom as new annotations are added)
        dbc.Card([
          dbc.CardBody([
            # Label row
            html.Div([
              dcc.Dropdown(
                id="new-annotation-label",
                options=self._annotation_options,
                value="High-step",
                clearable=False,
                style={'width': '100%'},
                className="mb-2"
              ),
              html.Small("Press 1-9, 0 for quick selection", className="text-muted")
            ], className="mb-2"),

            # Input rows
            # Start transition
            html.Div([
              html.Small("Task Start Transition:", className="fw-bold"),
              dbc.Row([
                dbc.Col([
                  dbc.Button("S", id="task-start-start-btn", color="secondary", size="sm",
                            style={'width': '100%'})
                ], width=2),
                dbc.Col([
                  dbc.Input(
                    id="task-start-start-input",
                    type="text",
                    placeholder="Start time",
                    size="sm"
                  )
                ], width=4),
                dbc.Col([
                  dbc.Button("E", id="task-start-end-btn", color="secondary", size="sm",
                            style={'width': '100%'})
                ], width=2),
                dbc.Col([
                  dbc.Input(
                    id="task-start-end-input",
                    type="text",
                    placeholder="End time",
                    size="sm"
                  )
                ], width=4)
              ], className="mb-2", style={'marginLeft': '0', 'marginRight': '0'}),
            ]),

            # End transition
            html.Div([
              html.Small("Task End Transition:", className="fw-bold"),
              dbc.Row([
                dbc.Col([
                  dbc.Button("S", id="task-end-start-btn", color="secondary", size="sm",
                            style={'width': '100%'})
                ], width=2),
                dbc.Col([
                  dbc.Input(
                    id="task-end-start-input",
                    type="text",
                    placeholder="Start time",
                    size="sm"
                  )
                ], width=4),
                dbc.Col([
                  dbc.Button("E", id="task-end-end-btn", color="secondary", size="sm",
                            style={'width': '100%'})
                ], width=2),
                dbc.Col([
                  dbc.Input(
                    id="task-end-end-input",
                    type="text",
                    placeholder="End time",
                    size="sm"
                  )
                ], width=4)
              ], className="mb-2", style={'marginLeft': '0', 'marginRight': '0'}),
            ]),

            html.Small("Press 'N' to fill next empty field", className="text-muted d-block text-center mb-1"),

            # Add annotation button
            dbc.Button(
              "Add Annotation",
              id="add-annotation-btn",
              color="primary",
              className="w-100",
              size="sm"
            )
          ], className="p-2")
        ], className="mb-2"),
      ], style={
        'maxHeight': 'calc(100vh - 320px)',
        'overflowY': 'auto',
        'paddingRight': '5px'
      }),

      # Delete confirmation modal
      dbc.Modal([
        dbc.ModalHeader("Confirm Delete"),
        dbc.ModalBody("Are you sure you want to delete this annotation?"),
        dbc.ModalFooter([
          dbc.Button("Cancel", id="cancel-delete", className="ms-auto", n_clicks=0),
          dbc.Button("Delete", id="confirm-delete", color="danger", n_clicks=0)
        ])
      ], id="delete-modal", is_open=False)
    ])


  def _timestamp_to_frame(self, timestamp):
    """Convert timestamp to frame ID using reference camera"""
    try:
      if hasattr(app, 'reference_camera') and app.reference_camera:
        frame = app.reference_camera.get_frame_for_timestamp(float(timestamp))
        # Adjust for truncation
        adjusted_frame = frame - app.reference_camera._start_frame
        return adjusted_frame
      else:
        return None
    except:
      return None


  def _create_annotation_cards(self, annotations, expanded_state):
    """Helper function to create annotation cards"""
    annotation_cards = []

    for idx, ann in enumerate(annotations):
      ann_id_str = str(ann['id'])
      is_expanded = expanded_state.get(ann_id_str, False)

      if ann.get('edit_mode', False):
        # Edit mode - always expanded
        card = dbc.Card([
          dbc.CardBody([
            # Counter and Update/Cancel buttons
            html.Div([
              html.Span(f"#{idx + 1}", className="text-muted me-2"),
              html.Div([
                dbc.Button("Cancel", id={'type': 'cancel-annotation', 'index': ann['id']}, 
                          color="secondary", size="sm", className="me-2"),
                dbc.Button("Update", id={'type': 'update-annotation', 'index': ann['id']}, 
                          color="success", size="sm")
              ], className="d-flex")
            ], className="mb-2 d-flex justify-content-between align-items-center"),

            # Compact edit form
            dcc.Dropdown(
              id={'type': 'annotation-label-edit', 'index': ann['id']},
              options=self._annotation_options,
              value=ann['label'],
              clearable=False,
              className="mb-2"
            ),

            # Task Start Transition row
            html.Small("Task Start Transition:", className="fw-bold"),
            dbc.Row([
              dbc.Col([
                dbc.Button("S", id={'type': 'ts-start-btn', 'index': ann['id']},
                          color="secondary", size="sm", style={'width': '100%'})
              ], width=2),
              dbc.Col([
                dbc.Input(
                  id={'type': 'annotation-ts-start-edit', 'index': ann['id']},
                  value=ann['task_start_start'],
                  type="text",
                  size="sm"
                )
              ], width=4),
              dbc.Col([
                dbc.Button("E", id={'type': 'ts-end-btn', 'index': ann['id']},
                          color="secondary", size="sm", style={'width': '100%'})
              ], width=2),
              dbc.Col([
                dbc.Input(
                  id={'type': 'annotation-ts-end-edit', 'index': ann['id']},
                  value=ann['task_start_end'],
                  type="text",
                  size="sm"
                )
              ], width=4)
            ], className="mb-2", style={'marginLeft': '0', 'marginRight': '0'}),

            # Task End Transition row
            html.Small("Task End Transition:", className="fw-bold"),
            dbc.Row([
              dbc.Col([
                dbc.Button("S", id={'type': 'te-start-btn', 'index': ann['id']},
                          color="secondary", size="sm", style={'width': '100%'})
              ], width=2),
              dbc.Col([
                dbc.Input(
                  id={'type': 'annotation-te-start-edit', 'index': ann['id']},
                  value=ann['task_end_start'],
                  type="text",
                  size="sm"
                )
              ], width=4),
              dbc.Col([
                dbc.Button("E", id={'type': 'te-end-btn', 'index': ann['id']},
                          color="secondary", size="sm", style={'width': '100%'})
              ], width=2),
              dbc.Col([
                dbc.Input(
                  id={'type': 'annotation-te-end-edit', 'index': ann['id']},
                  value=ann['task_end_end'],
                  type="text",
                  size="sm"
                )
              ], width=4)
            ], style={'marginLeft': '0', 'marginRight': '0'})
          ], className="p-2")
        ], className="mb-2", style={'backgroundColor': '#f8f9fa'})
      else:
        # Display mode - collapsible
        try:
            # Duration calculation
            start_val = float(ann['task_start_start'])
            end_val = float(ann['task_end_end'])
            duration = end_val - start_val
            duration_str = f"{duration:.2f}s"
        except:
            duration_str = "N/A"

        # Get frame IDs
        ts_start_frame = self._timestamp_to_frame(ann['task_start_start'])

        # Collapsed view - just show counter, label, start time, and duration
        if not is_expanded:
          card = dbc.Card([
            dbc.CardBody([
              html.Div([
                # Left side: counter, expand button, label, start time
                html.Div([
                  html.Span(f"#{idx + 1}", className="fw-bold text-muted me-2"),
                  dbc.Button("▼" if is_expanded else "▶", 
                            id={'type': 'expand-annotation', 'index': ann['id']}, 
                            color="light", size="sm", className="me-2 border",
                            style={'width': '25px', 'height': '25px', 'padding': '0', 
                                   'lineHeight': '1', 'fontSize': '12px'}),
                  html.Span(f"{ann['label']}", className="fw-bold me-2"),
                  html.Small(f"@ {ann['task_start_start'][:10]}...", className="text-muted"),
                  html.Span(f" ({duration_str})", className="text-success ms-2")
                ], className="d-flex align-items-center"),
                # Right side: edit and delete buttons
                html.Div([
                  dbc.Button("✏", id={'type': 'edit-annotation', 'index': ann['id']}, 
                            color="secondary", size="sm",
                            style={'width': '25px', 'height': '25px', 'padding': '0',
                                  'marginRight': '5px'}),
                  dbc.Button("🗑", id={'type': 'delete-annotation', 'index': ann['id']}, 
                            color="danger", size="sm",
                            style={'width': '25px', 'height': '25px', 'padding': '0'})
                ])
              ], className="d-flex justify-content-between align-items-center")
            ], className="py-1 px-2")
          ], className="mb-1")
        else:
          # Get all frame IDs for expanded view
          ts_start_frame = self._timestamp_to_frame(ann['task_start_start'])
          ts_end_frame = self._timestamp_to_frame(ann['task_start_end'])
          te_start_frame = self._timestamp_to_frame(ann['task_end_start'])
          te_end_frame = self._timestamp_to_frame(ann['task_end_end'])

          # Expanded view - show all details
          card = dbc.Card([
            dbc.CardBody([
              # Header with counter and controls
              html.Div([
                html.Div([
                  html.Span(f"#{idx + 1}", className="fw-bold text-muted me-2"),
                  dbc.Button("▼", id={'type': 'expand-annotation', 'index': ann['id']}, 
                            color="light", size="sm", className="me-2 border",
                            style={'width': '25px', 'height': '25px', 'padding': '0', 
                                  'lineHeight': '1', 'fontSize': '12px'}),
                  html.Span(ann['label'], className="fw-bold")
                ], className="d-flex align-items-center"),
                html.Div([
                  dbc.Button("✏", id={'type': 'edit-annotation', 'index': ann['id']}, 
                            color="secondary", size="sm",
                            style={'width': '25px', 'height': '25px', 'padding': '0',
                                  'marginRight': '5px'}),
                  dbc.Button("🗑", id={'type': 'delete-annotation', 'index': ann['id']}, 
                            color="danger", size="sm",
                            style={'width': '25px', 'height': '25px', 'padding': '0'})
                ])
              ], className="d-flex justify-content-between align-items-center mb-2"),

              # Compact details with frame IDs
              html.Div([
                html.Small("Task Start Transition:", className="fw-bold text-muted"),
                html.Small(f" {ann['task_start_start']} → {ann['task_start_end']}", 
                          className="text-muted"),
                html.Small(f" (frames {ts_start_frame} → {ts_end_frame})" if ts_start_frame is not None and ts_end_frame is not None else "", 
                          className="text-info")
              ], className="mb-1"),

              html.Div([
                html.Small("Task End Transition:", className="fw-bold text-muted"),
                html.Small(f" {ann['task_end_start']} → {ann['task_end_end']}", 
                          className="text-muted"),
                html.Small(f" (frames {te_start_frame} → {te_end_frame})" if te_start_frame is not None and te_end_frame is not None else "", 
                          className="text-info")
              ], className="mb-1"),

              html.Div([
                html.Small("Duration:", className="fw-bold text-muted"),
                html.Small(f" {duration_str}", className="text-success fw-bold")
              ])
            ], className="p-2")
          ], className="mb-2")

      annotation_cards.append(card)

    return annotation_cards


  def _activate_callbacks(self):
    """Register all callbacks for this component."""
    # Handle keyboard shortcuts for annotations
    @app.callback(
      Output("new-annotation-label", "value", allow_duplicate=True),
      Output("active-input", "data"),
      Output("task-start-start-input", "value", allow_duplicate=True),
      Output("task-start-end-input", "value", allow_duplicate=True),
      Output("task-end-start-input", "value", allow_duplicate=True),
      Output("task-end-end-input", "value", allow_duplicate=True),
      Input("keyboard-event", "data"),
      State("new-annotation-label", "value"),
      State("active-input", "data"),
      State("task-start-start-input", "value"),
      State("task-start-end-input", "value"),
      State("task-end-start-input", "value"),
      State("task-end-end-input", "value"),
      State("sync-timestamp", "data"),
      prevent_initial_call=True
    )
    def handle_annotation_keyboard_shortcuts(keyboard_event, current_label, active_input,
                                            ts_start, ts_end, te_start, te_end, sync_timestamp):
      if not keyboard_event:
        return current_label, active_input, ts_start, ts_end, te_start, te_end

      event_type = keyboard_event.get('type')

      if event_type == 'labelSelect':
        # Handle number key for label selection
        key = keyboard_event.get('key')
        if key == '0':
          label_value = self._annotation_values[9]  # Bench
        else:
          idx = int(key) - 1
          if 0 <= idx < len(self._annotation_values):
            label_value = self._annotation_values[idx]
          else:
            label_value = current_label

        return label_value, active_input, ts_start, ts_end, te_start, te_end

      elif event_type == 'nextInput':
        # Handle N key for next input
        timestamp_str = str(sync_timestamp) if sync_timestamp else ""

        # Find the next empty input
        if not ts_start:
          return current_label, 'task-start-start', timestamp_str, ts_end, te_start, te_end
        elif not ts_end:
          return current_label, 'task-start-end', ts_start, timestamp_str, te_start, te_end
        elif not te_start:
          return current_label, 'task-end-start', ts_start, ts_end, timestamp_str, te_end
        elif not te_end:
          return current_label, 'task-end-end', ts_start, ts_end, te_start, timestamp_str
        else:
          # All fields filled, cycle back to start
          return current_label, 'task-start-start', ts_start, ts_end, te_start, te_end

      # No relevant keyboard event
      return current_label, active_input, ts_start, ts_end, te_start, te_end


    # Handle Start/End button clicks
    @app.callback(
      Output("task-start-start-input", "value"),
      Output("task-start-end-input", "value"),
      Output("task-end-start-input", "value"),
      Output("task-end-end-input", "value"),
      Output({'type': 'annotation-ts-start-edit', 'index': ALL}, 'value'),
      Output({'type': 'annotation-ts-end-edit', 'index': ALL}, 'value'),
      Output({'type': 'annotation-te-start-edit', 'index': ALL}, 'value'),
      Output({'type': 'annotation-te-end-edit', 'index': ALL}, 'value'),
      Input("task-start-start-btn", "n_clicks"),
      Input("task-start-end-btn", "n_clicks"),
      Input("task-end-start-btn", "n_clicks"),
      Input("task-end-end-btn", "n_clicks"),
      Input({'type': 'ts-start-btn', 'index': ALL}, 'n_clicks'),
      Input({'type': 'ts-end-btn', 'index': ALL}, 'n_clicks'),
      Input({'type': 'te-start-btn', 'index': ALL}, 'n_clicks'),
      Input({'type': 'te-end-btn', 'index': ALL}, 'n_clicks'),
      State("sync-timestamp", "data"),
      State("task-start-start-input", "value"),
      State("task-start-end-input", "value"),
      State("task-end-start-input", "value"),
      State("task-end-end-input", "value"),
      State({'type': 'annotation-ts-start-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-ts-end-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-te-start-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-te-end-edit', 'index': ALL}, 'value'),
      State("annotations-store", "data"),
      prevent_initial_call=True
    )
    def handle_time_buttons(ts_start_clicks, ts_end_clicks, te_start_clicks, te_end_clicks, 
                            edit_ts_start_clicks, edit_ts_end_clicks, edit_te_start_clicks, edit_te_end_clicks,
                            sync_timestamp, ts_start_val, ts_end_val, te_start_val, te_end_val,
                            edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals,
                            annotations):
      ctx = callback_context
      if not ctx.triggered:
        return (ts_start_val, ts_end_val, te_start_val, te_end_val, 
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)

      trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

      # Check if this was actually triggered by a button click (n_clicks changed)
      trigger_value = ctx.triggered[0]['value']
      if trigger_value is None or trigger_value == 0:
        # Not a real button click, just initialization
        return (ts_start_val, ts_end_val, te_start_val, te_end_val,
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)

      if sync_timestamp is None:
        return (ts_start_val, ts_end_val, te_start_val, te_end_val,
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)

      # Get the reference camera's current timestamp
      timestamp_value = str(sync_timestamp)

      # Handle main annotation buttons
      if trigger_id == "task-start-start-btn":
        return (timestamp_value, ts_end_val, te_start_val, te_end_val,
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)
      elif trigger_id == "task-start-end-btn":
        return (ts_start_val, timestamp_value, te_start_val, te_end_val,
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)
      elif trigger_id == "task-end-start-btn":
        return (ts_start_val, ts_end_val, timestamp_value, te_end_val,
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)
      elif trigger_id == "task-end-end-btn":
        return (ts_start_val, ts_end_val, te_start_val, timestamp_value,
                edit_ts_start_vals, edit_ts_end_vals, edit_te_start_vals, edit_te_end_vals)

      # Handle edit annotation buttons
      try:
        parsed_id = json.loads(trigger_id.replace("'", '"'))
        button_type = parsed_id['type']
        button_index = parsed_id['index']

        if button_type in ['ts-start-btn', 'ts-end-btn', 'te-start-btn', 'te-end-btn']:
          # Count annotations in edit mode that appear before the target
          target_position = None
          edit_position = 0

          for ann in annotations:
            if ann.get('edit_mode', False):
              if ann['id'] == button_index:
                target_position = edit_position
                break
              edit_position += 1

          if target_position is not None:
            # Create new lists from current values
            new_edit_ts_start_vals = list(edit_ts_start_vals) if edit_ts_start_vals else []
            new_edit_ts_end_vals = list(edit_ts_end_vals) if edit_ts_end_vals else []
            new_edit_te_start_vals = list(edit_te_start_vals) if edit_te_start_vals else []
            new_edit_te_end_vals = list(edit_te_end_vals) if edit_te_end_vals else []

            # Ensure lists are long enough
            while len(new_edit_ts_start_vals) <= target_position:
              new_edit_ts_start_vals.append("")
            while len(new_edit_ts_end_vals) <= target_position:
              new_edit_ts_end_vals.append("")
            while len(new_edit_te_start_vals) <= target_position:
              new_edit_te_start_vals.append("")
            while len(new_edit_te_end_vals) <= target_position:
              new_edit_te_end_vals.append("")

            # Update the appropriate field
            if button_type == 'ts-start-btn':
              new_edit_ts_start_vals[target_position] = timestamp_value
            elif button_type == 'ts-end-btn':
              new_edit_ts_end_vals[target_position] = timestamp_value
            elif button_type == 'te-start-btn':
              new_edit_te_start_vals[target_position] = timestamp_value
            elif button_type == 'te-end-btn':
              new_edit_te_end_vals[target_position] = timestamp_value

            return (ts_start_val, ts_end_val, te_start_val, te_end_val,
                    new_edit_ts_start_vals, new_edit_ts_end_vals,
                    new_edit_te_start_vals, new_edit_te_end_vals)
      except Exception as e:
        print(f"Error handling edit buttons: {e}")
        return (ts_start_val, ts_end_val, te_start_val, te_end_val,
                edit_ts_start_vals, edit_ts_end_vals,
                edit_te_start_vals, edit_te_end_vals)


    # Main annotation management callback
    @app.callback(
      Output("annotations-store", "data"),
      Output("annotations-container", "children"),
      Output("annotation-counter", "children"),
      Output("task-start-start-input", "value", allow_duplicate=True),
      Output("task-start-end-input", "value", allow_duplicate=True),
      Output("task-end-start-input", "value", allow_duplicate=True),
      Output("task-end-end-input", "value", allow_duplicate=True),
      Output("new-annotation-label", "value"),
      Output("delete-modal", "is_open"),
      Output("delete-target", "data"),
      Output("annotation-expanded", "data"),
      Input("add-annotation-btn", "n_clicks"),
      Input({'type': 'edit-annotation', 'index': ALL}, 'n_clicks'),
      Input({'type': 'update-annotation', 'index': ALL}, 'n_clicks'),
      Input({'type': 'cancel-annotation', 'index': ALL}, 'n_clicks'),
      Input({'type': 'delete-annotation', 'index': ALL}, 'n_clicks'),
      Input({'type': 'expand-annotation', 'index': ALL}, 'n_clicks'),
      Input("confirm-delete", "n_clicks"),
      Input("cancel-delete", "n_clicks"),
      State("task-start-start-input", "value"),
      State("task-start-end-input", "value"),
      State("task-end-start-input", "value"),
      State("task-end-end-input", "value"),
      State("new-annotation-label", "value"),
      State("annotations-store", "data"),
      State({'type': 'annotation-label-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-ts-start-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-ts-end-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-te-start-edit', 'index': ALL}, 'value'),
      State({'type': 'annotation-te-end-edit', 'index': ALL}, 'value'),
      State("delete-modal", "is_open"),
      State("delete-target", "data"),
      State("annotation-expanded", "data"),
      prevent_initial_call=True
    )
    def manage_annotations(add_clicks, edit_clicks, update_clicks, cancel_clicks, delete_clicks, expand_clicks,
                          confirm_delete, cancel_delete,
                          ts_start, ts_end, te_start, te_end, label, annotations, 
                          edit_labels, edit_ts_starts, edit_ts_ends, edit_te_starts, edit_te_ends,
                          modal_open, delete_target, expanded_state):
      ctx = callback_context

      # Get annotations from store_data
      if not annotations:
        annotations = []

      # Initialize expanded state if needed
      if expanded_state is None:
        expanded_state = {}

      if not ctx.triggered:
        annotation_cards = self._create_annotation_cards(annotations, expanded_state)
        counter_text = f"Total: {len(annotations)} annotations"
        return annotations, annotation_cards, counter_text, "", "", "", "", "High-step", False, None, expanded_state

      trigger = ctx.triggered[0]

      # Handle adding new annotation
      if trigger['prop_id'] == "add-annotation-btn.n_clicks" and ts_start and ts_end and te_start and te_end:
        # Find the maximum ID in existing annotations to ensure uniqueness
        max_id = 0
        for ann in annotations:
          if ann['id'] > max_id:
            max_id = ann['id']

        new_annotation = {
          'id': max_id + 1,  # Always one more than the highest existing ID
          'label': label,
          'task_start_start': ts_start,
          'task_start_end': ts_end,
          'task_end_start': te_start,
          'task_end_end': te_end,
          'edit_mode': False
        }
        annotations.append(new_annotation)

        # Sort annotations by task_start_start timestamp
        try:
          annotations.sort(key=lambda x: float(x['task_start_start']))
        except:
          pass  # If conversion fails, keep original order

        # After sorting, renumber all IDs sequentially
        old_to_new_id_map = {}
        for idx, ann in enumerate(annotations):
          old_id = ann['id']
          new_id = idx + 1
          old_to_new_id_map[str(old_id)] = str(new_id)
          ann['id'] = new_id

        # Update expanded state with new IDs
        new_expanded_state = {}
        for old_id_str, is_expanded in expanded_state.items():
          if old_id_str in old_to_new_id_map:
            new_expanded_state[old_to_new_id_map[old_id_str]] = is_expanded
        expanded_state = new_expanded_state

      # Handle delete confirmation
      elif trigger['prop_id'] == "confirm-delete.n_clicks" and delete_target is not None:
        # When deleting, also remove the annotation
        annotations = [ann for ann in annotations if ann['id'] != delete_target]
        modal_open = False
        # Remove from expanded state
        if str(delete_target) in expanded_state:
          del expanded_state[str(delete_target)]
        delete_target = None

        # After deletion, renumber all IDs sequentially
        old_to_new_id_map = {}
        for idx, ann in enumerate(annotations):
          old_id = ann['id']
          new_id = idx + 1
          old_to_new_id_map[str(old_id)] = str(new_id)
          ann['id'] = new_id

        # Update expanded state with new IDs
        new_expanded_state = {}
        for old_id_str, is_expanded in expanded_state.items():
          if old_id_str in old_to_new_id_map:
            new_expanded_state[old_to_new_id_map[old_id_str]] = is_expanded
        expanded_state = new_expanded_state

      # Handle delete cancellation
      elif trigger['prop_id'] == "cancel-delete.n_clicks":
        modal_open = False
        delete_target = None

      # Handle edit, update, cancel, delete, or expand button clicks
      else:
        prop_id = trigger['prop_id']
        if '.n_clicks' in prop_id:
          component_id = prop_id.replace('.n_clicks', '')
          try:
            parsed_id = json.loads(component_id.replace("'", '"'))

            if parsed_id['type'] == 'expand-annotation':
              # Toggle expansion state
              ann_id_str = str(parsed_id['index'])
              expanded_state[ann_id_str] = not expanded_state.get(ann_id_str, False)

            elif parsed_id['type'] == 'edit-annotation':
              for ann in annotations:
                if ann['id'] == parsed_id['index']:
                  ann['edit_mode'] = True
                  # Ensure expanded when editing
                  expanded_state[str(ann['id'])] = True
                  break

            elif parsed_id['type'] == 'cancel-annotation':
              # Cancel edit mode without updating
              for ann in annotations:
                if ann['id'] == parsed_id['index']:
                  ann['edit_mode'] = False
                  break

            elif parsed_id['type'] == 'update-annotation':
              target_id = parsed_id['index']
              # Find the annotation to update
              for ann in annotations:
                if ann['id'] == target_id and ann.get('edit_mode', False):
                  # Count annotations in edit mode that appear before this one
                  edit_position = 0
                  for other_ann in annotations:
                    if other_ann.get('edit_mode', False):
                      if other_ann['id'] == target_id:
                        break
                      edit_position += 1

                  # Update using the correct position
                  if edit_position < len(edit_labels):
                    ann['label'] = edit_labels[edit_position]
                  if edit_position < len(edit_ts_starts):
                    ann['task_start_start'] = edit_ts_starts[edit_position]
                  if edit_position < len(edit_ts_ends):
                    ann['task_start_end'] = edit_ts_ends[edit_position]
                  if edit_position < len(edit_te_starts):
                    ann['task_end_start'] = edit_te_starts[edit_position]
                  if edit_position < len(edit_te_ends):
                    ann['task_end_end'] = edit_te_ends[edit_position]
                  
                  ann['edit_mode'] = False
                  break

              # Re-sort after update
              try:
                annotations.sort(key=lambda x: float(x['task_start_start']))
                # After sorting, renumber all IDs sequentially
                old_to_new_id_map = {}
                for idx, ann in enumerate(annotations):
                  old_id = ann['id']
                  new_id = idx + 1
                  old_to_new_id_map[str(old_id)] = str(new_id)
                  ann['id'] = new_id

                # Update expanded state with new IDs
                new_expanded_state = {}
                for old_id_str, is_expanded in expanded_state.items():
                  if old_id_str in old_to_new_id_map:
                    new_expanded_state[old_to_new_id_map[old_id_str]] = is_expanded
                expanded_state = new_expanded_state
              except:
                pass

            elif parsed_id['type'] == 'delete-annotation':
              modal_open = True
              delete_target = parsed_id['index'] 
          except:
            pass

      # Create annotation cards
      annotation_cards = self._create_annotation_cards(annotations, expanded_state)

      # Counter text
      counter_text = f"Total: {len(annotations)} annotations"

      # Clear inputs after adding
      if trigger['prop_id'] == "add-annotation-btn.n_clicks":
        return (annotations, annotation_cards, counter_text, "", "", "", "", "High-step", 
                modal_open, delete_target, expanded_state)
      else:
        return (annotations, annotation_cards, counter_text, ts_start, ts_end, te_start, te_end, 
                label, modal_open, delete_target, expanded_state)
