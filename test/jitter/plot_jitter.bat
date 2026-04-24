@echo on
call ..\..\.venv\Scripts\activate

python utils\gen_plot_jitter.py ^
    -o "C:\Users\maxim\Documents\Code\Frameworks\hermes\core\test\data\jitter" ^
    -g "Intel Core i7-9700TE" -n "Camera Eth1" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\cameras.hdf5" -d /cameras/40478064/toa_s -s /cameras/40478064/frame_index ^
    -g "Intel Core i7-9700TE" -n "Camera Eth2" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\cameras.hdf5" -d /cameras/40549960/toa_s -s /cameras/40549960/frame_index ^
    -g "Intel Core i7-9700TE" -n "Camera Eth3" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\cameras.hdf5" -d /cameras/40549975/toa_s -s /cameras/40549975/frame_index ^
    -g "Intel Core i7-9700TE" -n "Camera Eth4" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\cameras.hdf5" -d /cameras/40549976/toa_s -s /cameras/40549976/frame_index ^
    -g "LattePanda 3 Delta" -n "Ego Video" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\glasses.hdf5" -d /glasses/ego/toa_s -s /glasses/ego/frame_index ^
    -g "LattePanda 3 Delta" -n "Left Eye Video" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\glasses.hdf5" -d /glasses/left_eye/toa_s -s /glasses/left_eye/frame_index ^
    -g "LattePanda 3 Delta" -n "Right Eye Video" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\glasses.hdf5" -d /glasses/right_eye/toa_s -s /glasses/right_eye/frame_index ^
    -g "AMD Ryzen 7 PRO 8840U" -n "Xsens MVN" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\mvn-analyze.hdf5" -d /mvn-analyze/xsens-motion-trackers/process_time_s -s /mvn-analyze/xsens-motion-trackers/counter ^
    -g "Raspberry Pi 5" -n "Joint Motor" -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\revalexo.hdf5" -d /revalexo/motor_knee_right/timestamp -s ""
