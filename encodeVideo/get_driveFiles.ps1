# Define the destination folder (Desktop)
$desktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'))

# Define the log file path
$logFilePath = [System.IO.Path]::Combine($desktopPath, "filename.log")

# Function to append messages to the log file
function Write-Log {
    param (
        [string]$Message
    )
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$timestamp - $Message" | Out-File -FilePath $logFilePath -Append
}

# Find the drive with the volume label "STUDIO20"
$movDrive = Get-Volume | Where-Object { $_.FileSystemLabel -eq "STUDIO20" }

if ($movDrive) {
    $driveLetter = $movDrive.DriveLetter
    Write-Log "Drive with label 'STUDIO20' found: ${driveLetter}:"

    # Define the source path
    $sourcePath = "${driveLetter}:\"  # Ensure the path ends with a backslash

    # Find and copy .mov files to the Desktop
    $movFiles = Get-ChildItem -Path $sourcePath -Filter *.mov -Recurse -ErrorAction SilentlyContinue

    if ($movFiles) {
        foreach ($file in $movFiles) {
            $destinationPath = [System.IO.Path]::Combine($desktopPath, $file.Name)
            Write-Log "Copying '$($file.FullName)' to '$destinationPath'"
            try {
                Copy-Item -Path $file.FullName -Destination $destinationPath -Force
                Write-Log "Successfully copied '$($file.FullName)' to '$destinationPath'"
            } catch {
                Write-Log "Failed to copy '$($file.FullName)' to '$destinationPath': $_"
            }
        }
        Write-Log "All .mov files have been processed."
    } else {
        Write-Log "No .mov files found on the drive."
    }
} else {
    Write-Log "No drive with label 'STUDIO20' found."
}

