Transcoding resulting 2K videos with the Tesla P4 GPU for a 10x compression.
```bash
ffmpeg -y -hwaccel cuda -hwaccel_output_format cuda -i cameras_40478064.mp4 -hwaccel cuda -hwaccel_output_format cuda -i cameras_40549960.mp4 -hwaccel cuda -hwaccel_output_format cuda -i cameras_40549975.mp4 -hwaccel cuda -hwaccel_output_format cuda -i cameras_40549976.mp4 -map 0:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp1.mp4 -map 1:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp2.mp4 -map 2:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp3.mp4 -map 3:0 -vf scale_cuda=1920:1080 -c:v h264_nvenc -b:v 6M -preset p7 temp4.mp4
```

Extract PTS from the recorded video.
```bash
ffprobe -loglevel error -select_streams v:0 -show_entries frame=pts -of csv=print_section=0 eye_eye-video-world.mkv > pts.txt
```
