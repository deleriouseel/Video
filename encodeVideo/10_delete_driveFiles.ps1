$movDrive = Get-Volume | Where-Object { $_.FileSystemLabel -eq "STUDIO20" }
$logFilePath = [System.IO.Path]::Combine("C:\Users\AudioVisual\Documents\GitHub\Video", "filename.log")

function Write-Log {
    param (
        [string]$Message
    )
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$timestamp - $Message" | Out-File -FilePath $logFilePath -Append
}


function Get-LatestFriday {
    $today = Get-Date
    $latestFriday = $today.AddDays(-((7 + $today.DayOfWeek - [System.DayOfWeek]::Friday) % 7))

    return $latestFriday.Date 
}

if ($movDrive) {
    $driveLetter = $movDrive.DriveLetter
    Write-Log "Drive with label 'STUDIO' found: ${driveLetter}:"

    # Source path
    $sourcePath = "${driveLetter}:\"  

    # Get the latest Friday
    $latestFriday = Get-LatestFriday  
    Write-Log "Latest Friday: $latestFriday"

    # Get all files on the drive
    $allFiles = Get-ChildItem -Path $sourcePath -Recurse -File -ErrorAction SilentlyContinue

    if ($allFiles) {
        foreach ($file in $allFiles) {
    
            Write-Log "Checking file: '$($file.FullName)' with creation date: $($file.CreationTime)"

            # Compare creation date with latest Friday
            if ($file.CreationTime.Date -lt $latestFriday) {
                Write-Log "File '$($file.FullName)' is older than the latest Friday. Deleting..."

                # Delete the file
                try {
                    Remove-Item -Path $file.FullName -Force
                    Write-Log "Successfully deleted '$($file.FullName)'"
                } catch {
                    Write-Log "Failed to delete '$($file.FullName)': $_"
                }
            } else {
                Write-Log "File '$($file.FullName)' with creation date '$($file.CreationTime.Date)' is newer than the latest Friday. Skipping."
            }
        }
        Write-Log "All files have been processed."
    } else {
        Write-Log "No files found on the drive."
    }
} else {
    Write-Log "No drive with label 'STUDIO20' found."
}
