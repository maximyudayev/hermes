## NTP Synchronization

### Force sync
`w32tm /resync` - the Windows Time Service
`chronyc makestep` - Linux chrony

### Save and apply registry configs
`w32tm /config /update`
`w32tm /resync /force /nowait`

### (Linux) Manually set the date and time (YYYY-MM-DD HH:MM:SS)
`sudo timedatectl set-time '2026-04-10 10:15:00'`
`sudo date -s "10 APR 2026 10:15:00"`

### Manually set the local NTP server address of the 68 Class C private IP subnet
`w32tm /config /manualpeerlist:"192.168.68.100,0x9" /syncfromflags:manual /reliable:YES /update`

### Manually set the local NTP server address of the 220.25 Class A private IP subnet
`w32tm /config /manualpeerlist:"10.220.25.99,0x9" /syncfromflags:manual /reliable:YES /update`

### Verify configuration
`w32tm /query /configuration` - Windows
`timedatectl` - Linux

### Check the NTP peer list
`w32tm /query /peers` - Windows
`chronyc sources -v` - Linux

### Track the synchronization between devices
`chronyc tracking` - Linux

### Restart time service
`net stop w32time && net start w32time`
`sudo systemctl restart chrony`

### Windows Time Service manipulation
#### Export registry settings for NTP 
`reg export "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\W32Time" w32time_backup.reg`

#### Import registry settings
`reg import w32time_backup.reg`

### Launch a background sync logging process
#### PowerShell (Windows)
`Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = 'cmd.exe /c w32tm /stripchart /computer:10.220.25.99 /samples:720 /period:5 /dataonly > C:\Path\To\Your\Directory\ntp_sync_1hr.log'}`

#### Command Prompt (Windows)
`wmic process call create "cmd.exe /c w32tm /stripchart /computer:10.220.25.99 /samples:720 /period:5 /dataonly > C:\Path\To\Your\Directory\ntp_sync_1hr.log"`

#### Bash (Linux)
Launch over SSH a background process that persists even on tunnel disconnection.
`nohup bash -c 'for i in {1..720}; do echo "=== $(date +"%Y-%m-%d %H:%M:%S") ===" >> ntp_sync_1hr.log; chronyc tracking >> ntp_sync_1hr.log; echo "" >> ntp_sync_1hr.log; sleep 5; done' > /dev/null 2>&1 &`

Parse the log file for analysis and plotting.
`echo "\n\n\n" > ntp_parsed.log; awk '/===/ { ts = $2 " " $3 } /System time/ { print ts ", " $4 "s" }' ntp_sync_1hr.log >> ntp_parsed.log`

## Python Packaging
Update the changelog since previous tag
`git-changelog --bump <new_pypi_version> --filter-commits <previous_tag>..`

Update the changelog since previous tag, summarize all commit categories
`git-changelog --bump <new_pypi_version> --filter-commits <previous_tag>.. -c angular -s :all:`

Update the changelog with all commit categories
`git-changelog --bump <new_pypi_version> -c angular -s :all:`

Update the version of the Python package for release
`uv version --bump <[major,minor,patch]> [--dry-run] [--no-sync]`

Build the Python package
`uv build`

Release the Python package on PyPi
`uv publish --token <pypi_token>`


## HERMES Data Recovery
Dump the video into a new container, when device or experiment crashed, to recover playable video
`ffmpeg -i corrupted_video.mp4 -c copy fixed_video.mp4`


## ManGo
`for n in $(iron ls <mango_path> --columns name | sed 's/\x1b\[[0-9;]*m//g' | tail -n +2); do iron download <mango_path>/$n $n; done`

`echo $FILE | awk -F'_' '{print $2"_"$3"_"$4"/"$5"/"tolower($6)"/"$2"_"$3"_"$4"_"tolower($6)"_glasses.hdf5"}'`

`iron ls /gbiomed/home/AID-FOG/KUL/upload/to_review --columns name | awk '/glasses/' | awk -F'_' '{print $2"_"$3"_"$4"/"$5"/"tolower($6)"/"$2"_"$3"_"$4"_"tolower($6)"_glasses_temp.hdf5"}'`

`for n in $(iron ls /gbiomed/home/AID-FOG/KUL/upload/to_review --columns name | awk '/glasses/' | sed 's/\x1b\[[0-9;]*m//g'); do echo /gbiomed/home/AID-FOG/KUL/upload/to_review/$n && echo $(echo $n | awk -F'_' '{print $2"_"$3"_"$4"/"$5"/"tolower($6)"/"$2"_"$3"_"$4"_"tolower($6)"_glasses_temp.hdf5"}'); done`
