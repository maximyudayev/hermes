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
from dash import html, dcc, Input, Output, State, callback_context
import dash_bootstrap_components as dbc


class FrameSliderComponent(BaseComponent):
  """
  FrameSliderComponent: Frame navigation and control component

  - Main frame slider with markers
  - Fine control slider with adjustable window
  - Frame increment/decrement buttons
  - Keyboard navigation (arrow keys, Page Up/Down)
  - Time display

  """
  def __init__(self, total_frames: int, fps: float, reference_camera):
    """
    Frame navigation control component.

    Args:
        total_frames: Total frames in reference camera
        fps: Frames per second
        reference_camera: Reference camera component for sync
    """
    super().__init__(unique_id="frame_slider", col_width=12)
    self._total_frames = total_frames
    self._fps = fps
    self._reference_camera = reference_camera
    self._create_layout()
    self._activate_callbacks()


  def _create_layout(self):
    """Create frame control UI with collapsible design."""
    # Frame controls - fixed at bottom with integrated toggle button
    self._layout = html.Div([
      # Toggle button - always visible
      html.Div([
        dbc.Button(
          "▼", # Down arrow when expanded
          id="toggle-controls-btn",
          color="primary",
          size="sm",
          style={
            "position": "absolute",
            "top": "-35px",
            "right": "10px",
            "width": "40px",
            "height": "35px",
            "fontSize": "16px",
            "padding": "0",
            "lineHeight": "35px",
            "borderRadius": "4px 4px 0 0",
            "border": "1px solid #0d6efd",
            "borderBottom": "none",
            "backgroundColor": "#0d6efd",
            "color": "white",
            "zIndex": "1001",
            "boxShadow": "0 -2px 5px rgba(0,0,0,0.1)"
          }
        )
      ]),
      # Collapsible frame controls content
      html.Div([
        dbc.Card([
          dbc.CardBody([
            # Frame slider with +/- buttons
            html.Div([
              html.Label("Drag slider to seek to frame (based on reference camera):"),
              dbc.Row([
                dbc.Col([
                  dbc.Button("-10", id="decrement-10-btn", color="secondary", size="sm", 
                            style={"width": "45px", "font-weight": "bold"})
                ], width="auto"),
                dbc.Col([
                  dbc.Button("-", id="decrement-btn", color="primary", size="sm", 
                            style={"width": "40px", "font-weight": "bold"})
                ], width="auto"),
                dbc.Col([
                  dcc.Slider(
                    id="frame-slider",
                    min=0,
                    max=self._total_frames-1,
                    value=0,
                    step=1,
                    marks={
                      0: '0',
                      self._total_frames//4: f'{self._total_frames//4}',
                      self._total_frames//2: f'{self._total_frames//2}',
                      3*self._total_frames//4: f'{3*self._total_frames//4}',
                      self._total_frames-1: f'{self._total_frames-1}'
                    },
                    tooltip={"placement": "bottom", "always_visible": True}
                  )
                ], width=True),
                dbc.Col([
                  dbc.Button("+", id="increment-btn", color="primary", size="sm",
                            style={"width": "40px", "font-weight": "bold"})
                ], width="auto"),
                dbc.Col([
                  dbc.Button("+10", id="increment-10-btn", color="secondary", size="sm",
                            style={"width": "45px", "font-weight": "bold"})
                ], width="auto"),
              ], align="center", className="g-2")
            ], className="mb-1"),
            
            # Fine control slider with window size dropdown
            html.Div([
              dbc.Row([
                dbc.Col([
                  dcc.Slider(
                    id="fine-frame-slider",
                    min=-250,
                    max=250,
                    value=0,
                    step=1,
                    marks={
                      -250: {'label': '-250', 'style': {'fontSize': '12px'}},
                      -125: {'label': '-125', 'style': {'fontSize': '12px'}},
                      0: {'label': '0', 'style': {'fontSize': '12px', 'fontWeight': 'bold'}},
                      125: {'label': '125', 'style': {'fontSize': '12px'}},
                      250: {'label': '250', 'style': {'fontSize': '12px'}}
                    },
                    tooltip={"placement": "top", "always_visible": True},
                    included=False,
                    updatemode='drag'
                  )
                ], width=True),
                dbc.Col([
                  dcc.Dropdown(
                    id="fine-slider-window-dropdown",
                    options=[
                      {"label": "±100", "value": 100},
                      {"label": "±250", "value": 250},
                      {"label": "±500", "value": 500},
                    ],
                    value=250,
                    clearable=False,
                    style={"width": "100px", "height": "36px"},
                    searchable=False
                  )
                ], width="auto"),
              ], align="center", className="g-2", style={"marginTop": "5px"})
            ], id="fine-slider-container"),
            # Time and frame display
            html.Div(id="time-display", className="text-center pt-2"),
          ])
        ])
      ], id="frame-controls-content")
    ], id="frame-controls-div", style={
      'position': 'fixed',
      'bottom': '0',
      'left': '0',
      'right': '20%',  # Stop where right block begins
      'backgroundColor': 'transparent',
      'zIndex': '1000',
      'padding': '0',
      'transition': 'transform 0.3s ease-in-out'
    })


  def _activate_callbacks(self):
    """Register all callbacks for this component."""
    # Toggle controls visibility
    @app.callback(
      Output("frame-controls-content", "style"),
      Output("main-content", "style", allow_duplicate=True),
      Output("controls-visible", "data"),
      Output("toggle-controls-btn", "children"),
      Output("toggle-controls-btn", "style"),
      Input("toggle-controls-btn", "n_clicks"),
      State("controls-visible", "data"),
      prevent_initial_call=True
    )
    def toggle_frame_controls(n_clicks, is_visible):
      if n_clicks is None:
        n_clicks = 0

      # Toggle visibility
      new_visibility = not is_visible if n_clicks > 0 else True

      # Base button style
      base_button_style = {
        "position": "absolute",
        "top": "-35px",
        "right": "10px",
        "width": "40px",
        "height": "35px",
        "fontSize": "16px",
        "padding": "0",
        "lineHeight": "35px",
        "borderRadius": "4px 4px 0 0",
        "border": "1px solid #0d6efd",
        "borderBottom": "none",
        "backgroundColor": "#0d6efd",
        "color": "white",
        "zIndex": "1001",
        "boxShadow": "0 -2px 5px rgba(0,0,0,0.1)"
      }

      # Update styles based on visibility
      if new_visibility:
        content_style = {
          'display': 'block',
          'backgroundColor': 'white',
          'padding': '10px',
          'boxShadow': '0 -2px 10px rgba(0,0,0,0.1)',
          'borderTop': '1px solid #dee2e6'
        }
        main_style = {
          'marginRight': '20%',
          'marginBottom': '180px',
          'padding': '10px',
          'transition': 'margin-bottom 0.3s ease-in-out'
        }
        button_text = "▼"  # Down arrow when expanded
      else:
        content_style = {
          'display': 'none'
        }
        main_style = {
          'marginRight': '20%',
          'marginBottom': '10px',
          'padding': '10px',
          'transition': 'margin-bottom 0.3s ease-in-out'
        }
        button_text = "▲"  # Up arrow when collapsed

      return content_style, main_style, new_visibility, button_text, base_button_style


    # Update fine slider window size
    @app.callback(
      Output("fine-slider-window", "data"),
      Output("fine-frame-slider", "min"),
      Output("fine-frame-slider", "max"),
      Output("fine-frame-slider", "marks"),
      Output("fine-frame-slider", "value", allow_duplicate=True),
      Input("fine-slider-window-dropdown", "value"),
      State("fine-frame-slider", "value"),
      prevent_initial_call=True
    )
    def update_fine_slider_window(window_size, current_fine_value):
      # Only show marks at 0%, 25%, 50%, 75%, and 100%
      marks = {
        -window_size: {'label': f'-{window_size}', 'style': {'fontSize': '12px'}},
        -window_size//2: {'label': f'-{window_size//2}', 'style': {'fontSize': '12px'}},
        0: {'label': '0', 'style': {'fontSize': '12px', 'fontWeight': 'bold'}},
        window_size//2: {'label': f'{window_size//2}', 'style': {'fontSize': '12px'}},
        window_size: {'label': f'{window_size}', 'style': {'fontSize': '12px'}}
      }

      # Keep the current fine value if it's within the new range, otherwise reset to 0
      new_fine_value = current_fine_value if current_fine_value and abs(current_fine_value) <= window_size else 0

      return window_size, -window_size, window_size, marks, new_fine_value


    # Main navigation callback
    @app.callback(
      Output("frame-id", "data"),
      Output("frame-slider", "value"),
      Output("fine-frame-slider", "value"),
      Output("time-display", "children"),
      Output("sync-timestamp", "data"),
      Output("fine-slider-center", "data"),
      Input("frame-slider", "value"),
      Input("fine-frame-slider", "value"),
      Input("decrement-btn", "n_clicks"),
      Input("increment-btn", "n_clicks"),
      Input("decrement-10-btn", "n_clicks"),
      Input("increment-10-btn", "n_clicks"),
      Input("keyboard-event", "data"),
      State("frame-id", "data"),
      State("fine-slider-window", "data"),
      State("fine-slider-center", "data"),
      State("sync-timestamp", "data"),
      prevent_initial_call=False
    )
    def update_frame_and_navigate(main_slider_value, fine_slider_value,
                                  dec_clicks, inc_clicks, dec_10_clicks, inc_10_clicks, 
                                  keyboard_event, current_frame, 
                                  window_size, fine_center, sync_timestamp):
      ctx = callback_context

      # Initialize with safe defaults
      if current_frame is None:
        current_frame = 0
      if fine_center is None:
        fine_center = 0
      if window_size is None:
        window_size = 250

      # Initialize values
      update_center = False

      # Determine which input triggered the callback
      if not ctx.triggered:
        frame = 0
        fine_value = 0
        new_center = 0
      else:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == "keyboard-event" and keyboard_event:
          event_type = keyboard_event.get('type')

          if event_type == 'navigation':
            # Handle navigation keys
            key = keyboard_event.get('key')
            shift = keyboard_event.get('shift', False)
            ctrl = keyboard_event.get('ctrl', False)

            if key == 'ArrowLeft':
              if ctrl:
                frame = max(0, current_frame - 100)
              elif shift:
                frame = max(0, current_frame - 10)
              else:
                frame = max(0, current_frame - 1)
            elif key == 'ArrowRight':
              if ctrl:
                frame = min(self._total_frames - 1, current_frame + 100)
              elif shift:
                frame = min(self._total_frames - 1, current_frame + 10)
              else:
                frame = min(self._total_frames - 1, current_frame + 1)
            elif key == 'PageUp':
              frame = max(0, current_frame - 1000)
            elif key == 'PageDown':
              frame = min(self._total_frames - 1, current_frame + 1000)
            else:
              frame = current_frame

            fine_value = 0
            new_center = frame
            update_center = True
          else:
            # Not a navigation event, keep current state
            frame = current_frame
            fine_value = fine_slider_value if fine_slider_value is not None else 0
            new_center = fine_center

        elif trigger_id == "frame-slider":
          # Main slider moved - update frame and center fine slider
          frame = main_slider_value if main_slider_value is not None else 0
          fine_value = 0  # Center the fine slider
          new_center = frame  # Update the center
          update_center = True
        elif trigger_id == "fine-frame-slider":
          # Fine slider moved - calculate frame based on stored center
          if fine_slider_value is not None and fine_center is not None:
            # Calculate actual frame based on the stored center
            frame = fine_center + fine_slider_value
            frame = max(0, min(self._total_frames - 1, frame))
            fine_value = fine_slider_value
            new_center = fine_center  # Keep the same center
          else:
            frame = current_frame
            fine_value = 0
            new_center = current_frame
        elif trigger_id in ["decrement-btn", "increment-btn", "decrement-10-btn", "increment-10-btn"]:
          # Button clicks - update frame and recenter
          if trigger_id == "decrement-btn":
            frame = max(0, current_frame - 1)
          elif trigger_id == "increment-btn":
            frame = min(self._total_frames - 1, current_frame + 1)
          elif trigger_id == "decrement-10-btn":
            frame = max(0, current_frame - 10)
          elif trigger_id == "increment-10-btn":
            frame = min(self._total_frames - 1, current_frame + 10)

          fine_value = 0
          new_center = frame
          update_center = True
        else:
          frame = current_frame
          fine_value = 0
          new_center = fine_center if fine_center is not None else current_frame

      # Get sync timestamp from reference camera
      sync_timestamp = self._reference_camera.get_timestamp_at_frame(
        self._reference_camera._start_frame + frame
      )

      # Calculate time display
      time_sec = frame / self._fps if self._fps > 0 else 0

      # Add fine slider window range info
      window_start = max(0, new_center - window_size)
      window_end = min(self._total_frames - 1, new_center + window_size)

      time_display = html.Div([
        html.Div(f"Reference Frame: {frame} / {self._total_frames-1} | Time: {int(time_sec//60)}:{int(time_sec%60):02d}.{int((time_sec%1)*1000):03d}"),
        html.Div(f"Fine Control Window: [{window_start} - {window_end}] (Center: {new_center})", 
                style={'fontSize': '11px', 'color': '#666'})
      ])

      return frame, frame, fine_value, time_display, sync_timestamp, new_center
