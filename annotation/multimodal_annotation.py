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


from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc

from annotation.components import AnnotationComponent, GazeComponent, VideoComponent, SkeletonComponent, LinePlotComponent
from sync_utils import calculate_truncation_points, apply_truncation

from utils.gui_utils import app
import cv2


if __name__ == '__main__':

  base_path = 'data/subject_0/visit_1/trial_1'

  # Create the four camera components
  camera_1 = VideoComponent.VideoComponent(
    video_path=f'{base_path}/cameras_40478064.mkv',
    hdf5_path=f'{base_path}/cameras.hdf5',
    unique_id='40478064',
    legend_name='Camera 40478064 (Reference)',
    color_format=cv2.COLOR_YUV420P2RGB,
    col_width=3, # 3 to fit 4 videos in one row
    is_eye_camera=False,
    is_reference_camera=True  # We use the first camera as the reference
  )

  camera_2 = VideoComponent.VideoComponent(
    video_path=f'{base_path}/cameras_40549960.mkv',
    hdf5_path=f'{base_path}/cameras.hdf5',
    unique_id='40549960',
    legend_name='Camera 40549960',
    color_format=cv2.COLOR_YUV420P2RGB,
    col_width=3,
    is_eye_camera=False,
    is_reference_camera=False
  )
  
  camera_3 = VideoComponent.VideoComponent(
    video_path=f'{base_path}/cameras_40549975.mkv',
    hdf5_path=f'{base_path}/cameras.hdf5',
    unique_id='40549975',
    legend_name='Camera 40549975',
    color_format=cv2.COLOR_YUV420P2RGB,
    col_width=3,
    is_eye_camera=False,
    is_reference_camera=False
  )
  
  camera_4 = VideoComponent.VideoComponent(
    video_path=f'{base_path}/cameras_40549976.mkv',
    hdf5_path=f'{base_path}/cameras.hdf5',
    unique_id='40549976',
    legend_name='Camera 40549976',
    color_format=cv2.COLOR_YUV420P2RGB,
    col_width=3,
    is_eye_camera=False,
    is_reference_camera=False
  )

  eye_camera = VideoComponent.VideoComponent(
    video_path=f'{base_path}/eye_eye-video-world.mkv',
    hdf5_path=f'{base_path}/eye.hdf5',
    unique_id='eye_world',
    legend_name='Eye World Camera',
    color_format=cv2.COLOR_YUV420P2RGB,
    col_width=3,
    is_eye_camera=True,
    is_reference_camera=False
  )

  # Calculate synchronization truncation points using eye frame 100 as baseline
  camera_components = [camera_1, camera_2, camera_3, camera_4]
  truncation_points = calculate_truncation_points(camera_components, eye_camera, baseline_frame=100)
  
  # Apply truncation to all components
  all_components = camera_components + [eye_camera]
  apply_truncation(all_components, truncation_points)
  
  # Use camera 1's frame count as the reference for slider
  total_frames = camera_1.get_truncated_frame_count()
  fps = float(camera_1._fps)
  
  # Store reference camera globally
  app.reference_camera = camera_1
  app.all_components = all_components

  print("\nUsing Camera 1 as reference for synchronization")
  print(f"Total frames in reference camera: {total_frames}")

  app.layout = dbc.Container([
    # Hidden input to store the current frame value
    dbc.Input(id="frame-id", type="number", value=0, style={'display': 'none'}),
    
    # Store for sync timestamp
    dcc.Store(id="sync-timestamp", data=None),
    
    # Slider and buttons for frame selection
    dbc.Row([
      dbc.Col([
        html.H4("Video Frame Selection", className="text-center mb-3"),
        
        html.Div([
          html.Label("Drag slider to seek to frame:"),
          dbc.Row([
            dbc.Col([
              dbc.Button("-", id="decrement-btn", color="primary", size="sm", 
                        style={"width": "40px", "font-weight": "bold"})
            ], width="auto"),
            dbc.Col([
              dcc.Slider(
                id="frame-slider",
                min=0,
                max=total_frames-1,
                value=0,
                step=1,
                marks={
                  0: '0',
                  total_frames//4: f'{total_frames//4}',
                  total_frames//2: f'{total_frames//2}',
                  3*total_frames//4: f'{3*total_frames//4}',
                  total_frames-1: f'{total_frames-1}'
                },
                tooltip={"placement": "bottom", "always_visible": True}
              )
            ], width=True),
            dbc.Col([
              dbc.Button("+", id="increment-btn", color="primary", size="sm",
                        style={"width": "40px", "font-weight": "bold"})
            ], width="auto"),
          ], align="center", className="g-2")
        ], className="mb-3"),
        
        # Time and frame display
        html.Div(id="time-display", className="text-center pt-2")
        
      ], width=12)
    ], className="mb-4 p-3 border rounded"),

    # First row: Four cameras
    dbc.Row([
      camera_1.layout,
      camera_2.layout,
      camera_3.layout,
      camera_4.layout
    ], className="mb-3"),
    
    # Second row: Eye camera
    dbc.Row([
      eye_camera.layout
    ]),
  ], fluid=True)

  # Callback to handle slider and button inputs
  @app.callback(
    [Output("frame-id", "value"),
     Output("frame-slider", "value"),
     Output("time-display", "children"),
     Output("sync-timestamp", "data")],
    [Input("frame-slider", "value"),
     Input("decrement-btn", "n_clicks"),
     Input("increment-btn", "n_clicks")],
    [State("frame-id", "value")]
  )
  def update_frame(slider_value, dec_clicks, inc_clicks, current_frame):
    ctx = callback_context
    
    # Determine which input triggered the callback
    if not ctx.triggered:
      frame = 0
    else:
      trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
      
      if trigger_id == "frame-slider":
        frame = slider_value if slider_value is not None else 0
      elif trigger_id == "decrement-btn":
        frame = max(0, current_frame - 1)
      elif trigger_id == "increment-btn":
        frame = min(total_frames - 1, current_frame + 1)
      else:
        frame = current_frame
    
    # Get sync timestamp from reference camera
    sync_timestamp = app.reference_camera.get_timestamp_at_frame(
        app.reference_camera._start_frame + frame
    )
    
    # Calculate time display
    time_sec = frame / fps if fps > 0 else 0
    time_display = f"Reference Frame: {frame} / {total_frames-1} | Time: {int(time_sec//60)}:{int(time_sec%60):02d}.{int((time_sec%1)*1000):03d}"
    
    return frame, frame, time_display, sync_timestamp

  # Launch Dash GUI thread.
  app.run(debug=True)