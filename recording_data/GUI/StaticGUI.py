from dash import Dash, html, dash_table, dcc, callback, Output, Input, State, clientside_callback
import dash
import h5py
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

app = Dash()


h5_dir = "C:\\Users\\Owner\\Documents\\AidWear\\data\\test\\2025-01-22_S001_01\\2025-01-22_14-28-09_aidWear-wearables\\2025-01-22_14-28-11_streamLog_aidWear-wearables.hdf5"

with h5py.File(h5_dir, "r") as f:
  print("Keys: %s" % f.keys())
  data_acc_x = np.array(f['awinda-imu']['acceleration-x']['data'])[64000:64000+80000]
  data_acc_y = np.array(f['awinda-imu']['acceleration-y']['data'])[64000:64000+80000]
  data_acc_z = np.array(f['awinda-imu']['acceleration-z']['data'])[64000:64000+80000]

app.layout = [
  html.Div(children='Static data visualiser'),
]

awinda_list = [html.Div(children='Awinda Accelerometer'),]
# awinda viz

fig = make_subplots(rows=7, cols=1, shared_yaxes=True, shared_xaxes=True)

for id, (row_x, row_y, row_z) in enumerate(zip(data_acc_x.T, data_acc_y.T, data_acc_z.T)):
  # Create a DataFrame for the current set of rows
  df = pd.DataFrame({
      "time": range(len(row_x)),  # Assuming the x-axis is time, replace with your actual x-values if different
      "x_acc": row_x,
      "y_acc": row_y,
      "z_acc": row_z,
  })

  # Convert to long format
  #df_long = df.melt(id_vars="time", var_name="axis", value_name="value")

  # Create the line plot
  fig.add_trace(go.Scatter(x=df["time"], y=df["x_acc"], mode="lines", name=f"X acc {id + 1}", line=dict(color="red"), legendgroup=f'group{id}'), row=id + 1, col=1)
  fig.add_trace(go.Scatter(x=df["time"], y=df["y_acc"], mode="lines", name=f"Y acc {id + 1}", line=dict(color="green"), legendgroup=f'group{id}'), row=id + 1, col=1)
  fig.add_trace(go.Scatter(x=df["time"], y=df["z_acc"], mode="lines", name=f"Z acc {id + 1}", line=dict(color="blue"), legendgroup=f'group{id}'), row=id + 1, col=1)
fig.update_yaxes(matches='y')
fig.update_layout(height=7 * 150, margin=dict(l=0, r=0, t=40, b=40))
awinda_list.append(
    html.Div(dcc.Graph(figure=fig)))

app.layout.extend(awinda_list)

app.layout.append(html.Div(children='Video Visualisation'))

url = dash.get_asset_url("Rick Roll.mp4")

app.layout.append(html.Div([
    html.Video(
        src=url,  # Path to your video file
        controls=True,  # Show video controls (play, pause, etc.)
        autoPlay=True,  # Start playing automatically
        loop=True,      # Loop the video
        muted=True,     # Start muted
        style={"width": "auto", "height": "480px"}  # Set video size
    )
]))

app.layout.append(html.Div(children='Image Visualisation'))
url = dash.get_asset_url("cat.jpg")

app.layout.append(html.Div([
    html.Img(
        src=url,  # Replace with your image URL
        style={"width": "auto", "height": "500px"}  # Set image size
    )
]))

app.layout.append(html.Div(children='Live graph update'))

# Simulated time-series data
time_steps = 1000
data = pd.DataFrame({
    "time": np.arange(time_steps),
    "sin": np.sin(np.linspace(0, 10, time_steps)),  # Simulated wave
    "cos": np.cos(np.linspace(0, 10, time_steps)),
    "sin*cos": np.sin(np.linspace(0, 10, time_steps)) * np.cos(np.linspace(0, 10, time_steps))
})

# Initial time window
window_size = 100  # Number of points to display
initial_start = 0
initial_end = initial_start + window_size

# Layout
app.layout.append(html.Div([
  dcc.Graph(id="live-graph"),
  dcc.Interval(id="interval-update", interval=200, n_intervals=0),  # Updates 10 times per second
  dcc.Store(id="current-start", data=initial_start)  # Store the start index
]))


# Callback to update graph
@callback(
  Output("live-graph", "figure"),
  Output("current-start", "data"),  # Store updated start index
  Output("live-graph", "config"),
  Input("interval-update", "n_intervals"),
  State("current-start", "data")
)


def update_graph(n, current_start):
  # Shift the window by 10 points per update
  shift_size = 5
  new_start = current_start + shift_size
  new_end = new_start + window_size

  # Ensure we don't exceed data limits
  if new_end > len(data):
    new_start, new_end = 0, window_size  # Restart from the beginning

  # Filter data for the new window
  df_window = data.iloc[new_start:new_end]
  df_long = df_window.melt(id_vars="time", var_name="axis", value_name="value")

  # Create updated figure
  fig = px.line(df_long, x="time", y="value", color="axis", labels={"time": "Time", "value": "Value"})
  #fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
  for trace in fig.data:
    trace.update(mode='lines', line=dict(simplify=True))
  config = {'staticPlot': True}
  return fig, new_start, config  # Update graph & store new start index


if __name__ == '__main__':
  app.run(debug=True)
