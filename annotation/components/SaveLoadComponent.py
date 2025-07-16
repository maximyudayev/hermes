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
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import numpy as np
import h5py
import base64
import tempfile
import os
from datetime import datetime


class SaveLoadComponent(BaseComponent):
  """
  SaveLoadComponent: Load/save annotation component
  - Save annotations and offsets to HDF5
  - Load annotations and offsets from HDF5
  """
  def __init__(self):
    """Save/Load functionality component."""
    super().__init__(unique_id="save_load", col_width=12)
    self._create_layout()
    self._activate_callbacks()


  def _create_layout(self):
    """Create save/load buttons and feedback UI."""
    # File upload component for loading annotations
    upload_annotations = dcc.Upload(
      id='upload-annotations',
      children=html.Div([
        dbc.Button("Load", color="secondary", className="w-100", size="sm", style={'pointerEvents': 'none'})
      ]),
      style={
        'width': '100%',
        'cursor': 'pointer'
      },
      accept='.hdf5,.h5'
    )

    # Download component for saving annotations
    download_annotations = dcc.Download(id="download-annotations")

    # Toast notification for feedback
    feedback_toast = dbc.Toast(
      id="feedback-toast",
      header="Notification",
      is_open=False,
      dismissable=True,
      duration=4000,
      icon="success",
      style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
    )

    # Bottom buttons aligned with frame controls
    self._layout = html.Div([
      download_annotations,
      feedback_toast,

      # Bottom buttons
      html.Div([
        dbc.Row([
          dbc.Col([
            upload_annotations
          ], width=6, className="pe-1"),
          dbc.Col([
            dbc.Button("Save", id="save-annotations-btn", color="success", className="w-100", size="sm")
          ], width=6, className="ps-1")
        ], className="g-0")
      ], style={
        'position': 'absolute',
        'bottom': '0',
        'left': '0',
        'right': '0',
        'height': '50px',
        'padding': '10px',
        'backgroundColor': 'white',
        'borderTop': '1px solid #dee2e6'
      })
    ])


  def _save_to_hdf5(self, annotations, offsets):
    """Save annotations and offsets to HDF5 file."""
    tmp_file_path = None
    try:
      # Sort annotations before saving
      sorted_annotations = sorted(annotations, key=lambda x: float(x['task_start_start']))

      # Create a structured numpy array for annotations WITHOUT ID
      ann_dtype = np.dtype([
        ('label', 'S50'),  # String with max 50 chars
        ('task_start_start', np.float64),
        ('task_start_end', np.float64),
        ('task_end_start', np.float64),
        ('task_end_end', np.float64),
        ('duration', np.float64)
      ])

      # Create array
      ann_array = np.zeros(len(sorted_annotations), dtype=ann_dtype)

      # Fill the array (WITHOUT saving ID)
      for idx, ann in enumerate(sorted_annotations):
        ann_array[idx]['label'] = ann['label'].encode('utf-8')
        ann_array[idx]['task_start_start'] = float(ann['task_start_start'])
        ann_array[idx]['task_start_end'] = float(ann['task_start_end'])
        ann_array[idx]['task_end_start'] = float(ann['task_end_start'])
        ann_array[idx]['task_end_end'] = float(ann['task_end_end'])

        # Calculate duration
        try:
          duration = float(ann['task_end_end']) - float(ann['task_start_start'])
          ann_array[idx]['duration'] = duration
        except:
          ann_array[idx]['duration'] = -1

      # Create offset array if offsets exist
      if offsets:
        # Create a structured numpy array for offsets
        offset_dtype = np.dtype([
          ('component_id', 'S50'),
          ('offset_value', np.int32)
        ])

        offset_array = np.zeros(len(offsets), dtype=offset_dtype)

        # Fill the offset array
        for idx, (comp_id, offset_val) in enumerate(offsets.items()):
          offset_array[idx]['component_id'] = comp_id.encode('utf-8')
          offset_array[idx]['offset_value'] = offset_val

      # Create temporary file
      with tempfile.NamedTemporaryFile(delete=False, suffix='.hdf5') as tmp_file:
        tmp_file_path = tmp_file.name

      # Write HDF5 file
      with h5py.File(tmp_file_path, 'w') as hdf5:
        # Create annotations dataset
        ann_dataset = hdf5.create_dataset('annotations', data=ann_array)

        # Add metadata as attributes
        ann_dataset.attrs['total_annotations'] = len(sorted_annotations)
        ann_dataset.attrs['created_timestamp'] = datetime.now().isoformat()

        # Add label statistics as attributes
        labels_count = {}
        for ann in sorted_annotations:
          label = ann['label']
          labels_count[label] = labels_count.get(label, 0) + 1

        for label, count in labels_count.items():
          ann_dataset.attrs[f'count_{label}'] = count

        # Create offsets dataset if offsets exist
        if offsets:
          offset_dataset = hdf5.create_dataset('offsets', data=offset_array)
          offset_dataset.attrs['total_offsets'] = len(offsets)

      # Read the file for download
      with open(tmp_file_path, 'rb') as f:
        file_content = f.read()

      # Create filename with timestamp
      filename = f"annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.hdf5"

      message = f"Successfully saved {len(sorted_annotations)} annotations"
      if offsets:
        message += f" and {len(offsets)} offsets"

      print(message)
      print("Label distribution:")
      for label, count in sorted(labels_count.items()):
        print(f"  {label}: {count}")

      # Convert to base64 for download
      b64 = base64.b64encode(file_content).decode()

      return dict(content=b64, filename=filename, base64=True), {"message": message, "type": "success"}

    except Exception as e:
      message = f"Error saving annotations: {str(e)}"
      print(message)
      return None, {"message": message, "type": "danger"}
    finally:
      # Clean up temporary file
      if tmp_file_path and os.path.exists(tmp_file_path):
        os.unlink(tmp_file_path)


  def _load_from_hdf5(self, contents, filename):
    """Load annotations and offsets from HDF5 file."""
    tmp_file_path = None
    try:
      # Decode the uploaded file
      content_type, content_string = contents.split(',')
      decoded = base64.b64decode(content_string)

      # Create a temporary file to read with h5py
      with tempfile.NamedTemporaryFile(delete=False, suffix='.hdf5') as tmp_file:
        tmp_file.write(decoded)
        tmp_file_path = tmp_file.name

      annotations = []
      offsets = {}

      with h5py.File(tmp_file_path, 'r') as hdf5:
        # Debug info
        print(f"HDF5 file structure: {list(hdf5.keys())}")

        # Check if annotations dataset exists
        if 'annotations' in hdf5:
          ann_data = hdf5['annotations']

          # Check if this is an old file format with IDs
          has_id_field = False
          if len(ann_data) > 0:
            # Check the dtype to see if 'id' field exists
            field_names = ann_data.dtype.names
            has_id_field = 'id' in field_names
            if has_id_field:
              print("Note: Loading old format file with ID field (will be ignored)")

          # Read the structured array and assign fresh IDs
          for i in range(len(ann_data)):
            row = ann_data[i]
            # Handle label decoding
            label = row['label']
            if isinstance(label, bytes):
              label = label.decode('utf-8').rstrip('\x00')  # Remove null padding
            else:
              label = str(label).rstrip('\x00')

            # Try to read values (handle old files that might have 'id' field)
            try:
              task_start_start = str(row['task_start_start'])
              task_start_end = str(row['task_start_end'])
              task_end_start = str(row['task_end_start'])
              task_end_end = str(row['task_end_end'])
            except:
              # Handle potential missing fields
              print(f"Warning: Missing fields in annotation data")
              continue

            # Create annotation with fresh sequential ID
            annotation = {
              'id': i + 1,  # Simple sequential ID starting from 1
              'label': label,
              'task_start_start': task_start_start,
              'task_start_end': task_start_end,
              'task_end_start': task_end_start,
              'task_end_end': task_end_end,
              'edit_mode': False
            }
            annotations.append(annotation)

          # Sort annotations by task_start_start
          try:
            annotations.sort(key=lambda x: float(x['task_start_start']))
            # Re-assign IDs after sorting to maintain sequential order
            for idx, ann in enumerate(annotations):
              ann['id'] = idx + 1
          except:
            pass

          # Debug: Print loaded annotation IDs
          print(f"Loaded {len(annotations)} annotations with IDs: {[ann['id'] for ann in annotations]}")

        # Load offsets if they exist
        if 'offsets' in hdf5:
          offsets_data = hdf5['offsets']

          # Read offset values
          for i in range(len(offsets_data)):
            row = offsets_data[i]
            component_id = row['component_id']
            if isinstance(component_id, bytes):
              component_id = component_id.decode('utf-8').rstrip('\x00')
            else:
              component_id = str(component_id).rstrip('\x00')

            offset_value = int(row['offset_value'])
            offsets[component_id] = offset_value

          print(f"Loaded offsets: {offsets}")

        message = f"Successfully loaded {len(annotations)} annotations"
        if offsets:
          message += f" and {len(offsets)} offsets"
        message += f" from {filename}"

        print(message)
        return annotations, {}, offsets, {"message": message, "type": "success"}
  
    except Exception as e:
      message = f"Error loading annotations: {str(e)}"
      print(message)
      return [], {}, {}, {"message": message, "type": "danger"}
    finally:
      # Clean up temporary file
      if tmp_file_path and os.path.exists(tmp_file_path):
        os.unlink(tmp_file_path)


  def _activate_callbacks(self):
    """Register all callbacks for this component."""

    # Callback for Load Annotations from uploaded file
    @app.callback(
      Output("annotations-store", "data", allow_duplicate=True),
      Output("annotation-expanded", "data", allow_duplicate=True),
      Output("offsets-store", "data", allow_duplicate=True),
      Output("feedback-message", "data"),
      Input("upload-annotations", "contents"),
      Input("upload-annotations", "filename"),
      prevent_initial_call=True
    )
    def load_annotations(contents, filename):
      if contents is None:
          return [], {}, {}, None

      return self._load_from_hdf5(contents, filename)


    # Callback for Save Annotations button
    @app.callback(
      Output("download-annotations", "data"),
      Output("feedback-message", "data", allow_duplicate=True),
      Input("save-annotations-btn", "n_clicks"),
      State("annotations-store", "data"),
      State("offsets-store", "data"),
      prevent_initial_call=True
    )
    def save_annotations(n_clicks, annotations, offsets):
      if n_clicks and annotations:
        return self._save_to_hdf5(annotations, offsets)
      elif n_clicks and not annotations:
        return None, {"message": "No annotations to save", "type": "warning"}

      return None, None


    # Callback to display feedback toast
    @app.callback(
      Output("feedback-toast", "is_open"),
      Output("feedback-toast", "children"),
      Output("feedback-toast", "icon"),
      Output("feedback-toast", "header"),
      Input("feedback-message", "data"),
      prevent_initial_call=True
    )
    def show_feedback(feedback_data):
      if feedback_data:
        message = feedback_data.get("message", "")
        msg_type = feedback_data.get("type", "info")

        # Set icon and header based on type
        if msg_type == "success":
          icon = "success"
          header = "Success"
        elif msg_type == "warning":
          icon = "warning"
          header = "Warning"
        elif msg_type == "danger":
          icon = "danger"
          header = "Error"
        else:
          icon = "info"
          header = "Info"

        return True, message, icon, header

      return False, "", "info", "Info"
