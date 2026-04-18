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
`nohup bash -c 'for i in {1..720}; do echo "=== $(date +"%Y-%m-%d %H:%M:%S") ===" >> ntp_sync_1hr.log; chronyc tracking >> ntp_sync_1hr.log; echo "" >> ntp_sync_1hr.log; sleep 5; done' > /dev/null 2>&1 &`
