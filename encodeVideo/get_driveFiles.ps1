# Define the destination folder (Desktop)
$desktopPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('Desktop'))

# Define the log file path
$logFilePath = [System.IO.Path]::Combine("C:\Users\AudioVisual\Documents\GitHub\Video", "filename.log")


# Function to append messages to the log file
function Write-Log {
    param (
        [string]$Message
    )
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    "$timestamp - $Message" | Out-File -FilePath $logFilePath -Append
}

# Get video length using ffprobe
function Get-VideoDuration {
    param (
        [string]$filePath
    )
    $ffprobePath = "ffprobe" # Ensure ffprobe is in your PATH
    $ffprobeArgs = @(
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        $filePath
    )
    try {
        $duration = & $ffprobePath $ffprobeArgs
        return [double]$duration
    } catch {
        Write-Log "Failed to get duration for '$filePath': $_"
        return $null
    }
}


# Function to get the latest Friday, Sunday, and Monday
function Get-LatestDays {
    # Get today's date
    $today = Get-Date
    
    # Calculate the last Friday
    $daysSinceFriday = ($today.DayOfWeek - [int][System.DayOfWeek]::Friday + 7) % 7
    $latestFriday = $today.AddDays(-$daysSinceFriday).Date

    # Calculate the last Sunday
    $daysSinceSunday = ($today.DayOfWeek - [int][System.DayOfWeek]::Sunday + 7) % 7
    $latestSunday = $today.AddDays(-$daysSinceSunday).Date

    # Calculate the last Monday
    $daysSinceMonday = ($today.DayOfWeek - [int][System.DayOfWeek]::Monday + 7) % 7
    $latestMonday = $today.AddDays(-$daysSinceMonday).Date

    # Log the dates
    Write-Log "Latest Friday: $latestFriday"
    Write-Log "Latest Sunday: $latestSunday"
    Write-Log "Latest Monday: $latestMonday"

    return @($latestFriday, $latestSunday, $latestMonday)
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
        $datesToCheck = Get-LatestDays  # Get the latest Friday, Sunday, and Monday
        foreach ($file in $movFiles) {
            # Check if the file's creation date (without time) is on one of the specified dates
            if ($datesToCheck -contains $file.CreationTime.Date) {
                # Get the duration of the video file
                $duration = Get-VideoDuration -filePath $file.FullName
                if ($duration) {
                    # Log the filename and its duration
                    Write-Log "File '$($file.Name)' duration: $([math]::Round($duration / 60, 2)) minutes."
                    
                    if ($duration -gt 1800) { # 1800 seconds = 30 minutes
                        $destinationPath = [System.IO.Path]::Combine($desktopPath, $file.Name)
                        Write-Log "Copying '$($file.FullName)' to '$destinationPath'"
                        try {
                            Copy-Item -Path $file.FullName -Destination $destinationPath -Force
                            Write-Log "Successfully copied '$($file.FullName)' to '$destinationPath'"
                        } catch {
                            Write-Log "Failed to copy '$($file.FullName)' to '$destinationPath': $_"
                        }
                    } else {
                        Write-Log "File '$($file.FullName)' is shorter than 30 minutes. Skipping."
                    }
                } else {
                    Write-Log "Could not determine the duration of '$($file.FullName)'. Skipping."
                }
            } else {
                Write-Log "File '$($file.FullName)' was not created on the latest Friday, Sunday, or Monday. Skipping."
            }
        }
        Write-Log "All .mov files have been processed."
    } else {
        Write-Log "No .mov files found on the drive."
    }
} else {
    Write-Log "No drive with label 'STUDIO20' found."
}
