# Define the name of the USB drive to monitor
$driveName = "STUDIO20"
$destinationFolder = "C:\Users\AudioVisual\Desktop\backup"
$files = Get-ChildItem -Path $destinationFolder -Filter "*.MOV" -File


function Copy-DriveContents {
    param (
        [string]$source,
        [string]$destination
    )

    try {
        $files = Get-ChildItem -Path $source -ErrorAction Stop
    }
    catch {
        Write-Host "Error: Failed to retrieve files from $source. $_"
        return
    }

    Write-Host "Found $($files.Count) file(s) in $source"

    # Copy files from source to destination if they don't exist in the destination
    foreach ($file in $files) {
        $fileExtension = $file.Extension
        # Generate modified date string in the format 'yyyyMMdd'
        $modifiedDate = $file.LastWriteTime.ToString("yyyyMMdd")
        $newFileName = "{0}_{1}{2}" -f $file.BaseName, $modifiedDate, $fileExtension

        # Build destination file path
        $destinationFile = Join-Path -Path $destination -ChildPath $newFileName

        Write-Host "Copying $($file.FullName) to $destinationFile"
        if (-not (Test-Path $destinationFile)) {
            try {
                Copy-Item -Path $file.FullName -Destination $destinationFile -Force
                Write-Host "File $($file.FullName) copied successfully."
            }
            catch {
                Write-Host "Error: Failed to copy $($file.FullName) to $destination. $_"
            }
        }
        else {
            Write-Host "File $($file.FullName) already exists in $destination. Skipping."
        }
    }
}

# Function to check for the USB drive
function Update-DriveCheck {
    $scsiDrives = Get-WmiObject -Class Win32_DiskDrive -Filter "InterfaceType='SCSI'"

    $foundDrive = $false

    foreach ($scsiDrive in $scsiDrives) {
        # Get logical disks associated with the SCSI drive
        $partitions = Get-WmiObject -Class Win32_DiskDriveToDiskPartition -Filter "DeviceID='$($scsiDrive.DeviceID)'"
        foreach ($partition in $partitions) {
            $logicalDisks = Get-WmiObject -Class Win32_LogicalDiskToPartition -Filter "DeviceID='$($partition.Dependent)'"
            foreach ($logicalDisk in $logicalDisks) {
                $disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='$($logicalDisk.Dependent)'"
                if ($disk.VolumeName -eq $driveName) {
                    Write-Host "Drive '$driveName' detected."
                    $sourcePath = Join-Path -Path $disk.DeviceID -ChildPath $sourceFolder
                    Copy-USBContents -source $sourcePath -destination $destinationFolder
                    Write-Host "Contents of Drive '$driveName' copied to '$destinationFolder'."
                    $foundDrive = $true
                    break
                }
            }
            if ($foundDrive) { break }
        }
        if ($foundDrive) { break }
    }

    if (-not $foundDrive) {
        Write-Host "No SCSI drive with label '$driveName' detected."
    }
    
    return $foundDrive
} 

Update-DriveCheck