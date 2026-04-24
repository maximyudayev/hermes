@echo on
call ..\..\.venv\Scripts\activate

python utils\calc_jitter.py ^
    -o "C:\Users\maxim\Documents\Code\Frameworks\hermes\core\test\data\jitter\revalexo_pilot\camera_1" ^
    -f "C:\Users\maxim\Documents\Code\Projects\kdd2026\data\project_Revalexo\type_Manual\trial_0\cameras.hdf5" ^
    -d /cameras/40478064/toa_s ^
    -s /cameras/40478064/frame_index
